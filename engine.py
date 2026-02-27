from __future__ import annotations

from dataclasses import dataclass, replace
from math import sqrt
from typing import Optional, Tuple

from fluid_properties import FluidModel, FluidState
from results_container import Results
from utils import stagnation_pressure, stagnation_temperature

from components.diffuser import Diffuser
from components.fan import Fan
from components.duct import Duct
from components.compressor import Compressor
from components.combustor import Combustor
from components.turbine import Turbine
from components.mixer import Mixer
from components.afterburner import Afterburner
from components.nozzle import Nozzle

from solvers.spool_balance import power_required, fan_power
from enginelogging import VERBOSE

@dataclass
class Ambient:
    T: float
    p: float
    M: float = 0.0


@dataclass
class EngineDesign:
    # Flow / cycle
    m_dot: float
    bypass_ratio: float
    fuel_LHV: float

    # Pressure ratios / losses (total pressure multipliers)
    diffuser_pr: float
    fan_pr: float
    bypass_duct_pr: float
    lpc_pr: float
    lpc_duct_pr: float
    hpc_pr: float
    hpc_duct_pr: float
    burner_pr: float
    mixer_pr: float
    nozzle_pr: float

    # Efficiencies
    eta_fan: float
    eta_lpc: float
    eta_hpc: float
    eta_burner: float
    eta_hpt: float
    eta_lpt: float
    eta_mech: float
    eta_nozzle: float

    # Temperatures
    TIT: float  # combustor exit

    # Nozzle geometry (dry)
    nozzle_throat_d: float = 0.78
    nozzle_exit_d: float = 0.78


@dataclass
class AfterburnDesign:
    enabled: bool
    m_dot: float
    TAB: float
    ab_pr: float
    eta_ab: float
    nozzle_eta: float
    throat_d: float
    exit_d: float


class TurbofanEngine:
    """Variable-cp two-spool turbofan cycle model.

    The model tracks stagnation states through each component, then expands through a nozzle.

    Mass flow behavior:
    - Default (legacy): use the provided EngineDesign.m_dot.
    - Optional: if the nozzle is choked, iterate m_dot so the engine's inlet mass flow matches
      the nozzle choked capacity (based on Pt, Tt, and throat area).
    """

    def __init__(
        self,
        design: EngineDesign,
        air_model: FluidModel,
        products_model: FluidModel,
        afterburner: AfterburnDesign | None = None,
    ) -> None:
        self.d = design
        self.air = air_model
        self.products = products_model
        self.afterburner = afterburner

        self.diffuser = Diffuser(name="diffuser", pr=self.d.diffuser_pr)
        self.fan = Fan(name="fan", pr=self.d.fan_pr, eta=self.d.eta_fan, bypass_ratio=self.d.bypass_ratio)

        self.bypass_duct = Duct(name="bypass_duct", pr=self.d.bypass_duct_pr)
        self.lpc_duct = Duct(name="lpc_duct", pr=self.d.lpc_duct_pr)
        self.hpc_duct = Duct(name="hpc_duct", pr=self.d.hpc_duct_pr)

        self.lpc = Compressor(name="lpc", pr=self.d.lpc_pr, eta=self.d.eta_lpc)
        self.hpc = Compressor(name="hpc", pr=self.d.hpc_pr, eta=self.d.eta_hpc)

        self.comb = Combustor(
            name="combustor",
            pr=self.d.burner_pr,
            eta_b=self.d.eta_burner,
            LHV=self.d.fuel_LHV,
            Tt_out=self.d.TIT,
            products_model=self.products,
        )

        self.hpt = Turbine(name="hpt", eta=self.d.eta_hpt, mech_eta=self.d.eta_mech)
        self.lpt = Turbine(name="lpt", eta=self.d.eta_lpt, mech_eta=self.d.eta_mech)

        self.mixer = Mixer(
            name="mixer",
            pr=self.d.mixer_pr,
            air_model=self.air,
            products_model=self.products,
        )

        self.nozzle_dry = Nozzle(
            name="nozzle",
            eta=self.d.eta_nozzle,
            pr=self.d.nozzle_pr,
            throat_d=self.d.nozzle_throat_d,
            exit_d=self.d.nozzle_exit_d,
        )

    @staticmethod
    def _select_afterburner(afterburn: bool | AfterburnDesign, default_ab: AfterburnDesign | None) -> AfterburnDesign | None:
        if isinstance(afterburn, AfterburnDesign):
            return afterburn
        if afterburn is True:
            return default_ab
        return None

    def _run_once(self, ambient: Ambient, m_dot: float, afterburn: AfterburnDesign | None) -> Tuple[Results, dict]:
        """Single-pass solve for a specified inlet mass flow."""
        d = replace(self.d, m_dot=float(m_dot))
        res = Results(baseline_station="2")

        # Station 1: ambient -> freestream stagnation
        gamma0 = self.air.gamma(ambient.T)
        Tt0 = stagnation_temperature(ambient.T, gamma0, ambient.M)
        Pt0 = stagnation_pressure(ambient.p, gamma0, ambient.M)
        
        s1 = (
            FluidState(
                m_dot=d.m_dot,
                model=self.air,
                composition="air",
                Tt=Tt0,
                Pt=Pt0,
                T=ambient.T,
                p=ambient.p,
                M=ambient.M,
            )
            .update_thermo()
        )
        res.add_state("1", s1)

        # Station 2: inlet/diffuser
        s2 = self.diffuser.process(s1)
        res.add_state("2", s2)

        # Station 3: fan exit (core + bypass)
        core3, byp3 = self.fan.process(s2)
        s3 = core3.copy_with(m_dot=s2.m_dot)  # conceptual "before split" fan exit
        s3.set_static_equal_total()
        res.add_state("3", s3)

        # Station 4: LPC exit
        core3_to_lpc = self.lpc_duct.process(core3)
        s4 = self.lpc.process(core3_to_lpc)
        res.add_state("4", s4)

        # Station 5: HPC exit
        s4_to_hpc = self.hpc_duct.process(s4)
        s5 = self.hpc.process(s4_to_hpc)
        res.add_state("5", s5)

        # Station 6: combustor exit
        s6, f_main = self.comb.process(s5)
        res.add_state("6", s6)
        res.add_scalar("f_main", f_main)

        # Spool power requirements (variable-cp enthalpy-based)
        W_fan = fan_power(s2, s3)
        W_lpc = power_required(core3_to_lpc, s4)
        W_hpc = power_required(s4_to_hpc, s5)
        W_lpt = W_fan + W_lpc
        W_hpt = W_hpc

        res.add_scalar("W_fan_W", W_fan)
        res.add_scalar("W_lpc_W", W_lpc)
        res.add_scalar("W_hpc_W", W_hpc)

        # Station 7: HPT exit (powers HPC)
        s7, w_hpt = self.hpt.process(s6, shaft_power_required=W_hpt)
        res.add_state("7", s7)
        res.add_scalar("w_hpt_Jpkg", w_hpt)

        # Station 8: LPT exit (powers fan + LPC)
        s8, w_lpt = self.lpt.process(s7, shaft_power_required=W_lpt)
        res.add_state("8", s8)
        res.add_scalar("w_lpt_Jpkg", w_lpt)

        # Station 9: bypass duct exit
        s9 = self.bypass_duct.process(byp3)
        res.add_state("9", s9)

        # Station 10: mixer exit
        s10 = self.mixer.process(s8, s9)
        res.add_state("10", s10)

        # Station 11: afterburner (optional)
        nozzle = self.nozzle_dry
        s_noz_in = s10
        f_ab = 0.0

        if afterburn and afterburn.enabled:
            ab = Afterburner(
                name="afterburner",
                pr=afterburn.ab_pr,
                eta_b=afterburn.eta_ab,
                LHV=d.fuel_LHV,
                Tt_out=afterburn.TAB,
                products_model=self.products,
            )
            s11, f_ab = ab.process(s10)
            res.add_state("11", s11)
            res.add_scalar("f_ab", f_ab)
            s_noz_in = s11

            nozzle = Nozzle(
                name="nozzle_ab",
                eta=afterburn.nozzle_eta,
                pr=d.nozzle_pr,
                throat_d=afterburn.throat_d,
                exit_d=afterburn.exit_d,
            )

        # Nozzle expansion
        noz = nozzle.process(s_noz_in, p_ambient=ambient.p)

        res.add_scalar("ue_exit_mps", noz["ue"])
        res.add_scalar("Me_exit", noz["Me"])
        res.add_scalar("pe_exit_Pa", noz["pe"])
        res.add_scalar("choked", 1.0 if noz["choked"] else 0.0)
        res.add_scalar("F_gross_N", noz["F_gross"])

        # Net thrust (ram drag)
        a0 = sqrt(gamma0 * self.air.R * ambient.T)
        u0 = ambient.M * a0
        F_net = noz["F_gross"] -  d.m_dot * u0
        res.add_scalar("F_net_N", F_net)
        res.add_scalar("u_freestream_mps", u0)

        # Fuel flow + TSFC
        m_air = d.m_dot
        m_core = m_air / (1.0 + d.bypass_ratio)
        m_f_main = m_core * f_main
        m_f_ab = s10.m_dot * f_ab
        m_f = m_f_main + m_f_ab
        m_total = m_air + m_f

        res.add_scalar("m_fuel_kgps", m_f)
        res.add_scalar("TSFC_kg_per_Ns", m_f / max(F_net, 1e-12))
        res.add_scalar("ST_Ns_per_kg", F_net / max(m_core, 1e-12))

        # Efficiencies (kept consistent with existing implementation)
        ue = noz["ue"]
        pe = noz["pe"]
        Ae = noz["Ae"]

        jet_power = m_total * ue * ue / 2 - m_air * u0 * u0 / 2 + Ae * ue * (pe - ambient.p)
        fuel_power = m_f * d.fuel_LHV
        thrust_power = F_net * u0
        
        eta_th = jet_power / fuel_power if fuel_power > 0 else 0.0
        eta_prop = thrust_power / jet_power if jet_power > 0 else 0.0
        res.add_scalar("thermal_efficiency", eta_th)
        res.add_scalar("propulsive_efficiency", eta_prop)
        res.add_scalar("overall_efficiency", eta_th * eta_prop)
        res.add_scalar("jet_power", jet_power)
        res.add_scalar("fuel_power", fuel_power)
        res.add_scalar("thrust_power", thrust_power)

        # Station 12: report nozzle exit as a state object
        s12 = s_noz_in.copy_with(Tt=noz["Tt"], Pt=noz["Pt"])
        s12.T = noz["Te"]
        s12.p = noz["pe"]
        s12.M = noz["Me"]
        s12.update_thermo()
        res.add_state("12", s12)

        # Bookkeeping
        res.add_scalar("m_dot_kgps", d.m_dot)
        res.add_scalar("mdot_nozzle_choked_kgps", float(noz.get("mdot_choked", 0.0)))

        return res, noz

    def run(
        self,
        ambient: Ambient,
        afterburn: bool | AfterburnDesign = False,
        *,
        mdot_mode: str = "fixed",
        mdot_tol: float = 1e-4,
        mdot_max_iter: int = 30,
        mdot_relax: float = 0.5,
        update_design: bool = False,
    ) -> Results:
        """Run the turbofan model.

        mdot_mode:
        - "fixed": use EngineDesign.m_dot
        - "auto":  if the nozzle is choked, iterate m_dot so inlet m_dot matches mdot_nozzle_choked
        """
        
        ab = self._select_afterburner(afterburn, self.afterburner)

        if ab and ab.enabled:
            m_dot = float(ab.m_dot)
        else:
            m_dot = float(self.d.m_dot)
        res, noz = self._run_once(ambient=ambient, m_dot=m_dot, afterburn=ab)

        if mdot_mode.lower() != "auto":
            res.add_scalar("mdot_solve_iterations", 0.0)
            res.add_scalar("mdot_solve_converged", 1.0)
            res.add_scalar("mdot_solve_used", 0.0)  # 0 = fixed
            return res

        # Only iterate if choked
        if not bool(noz.get("choked", False)):
            res.add_scalar("mdot_solve_iterations", 0.0)
            res.add_scalar("mdot_solve_converged", 1.0)
            res.add_scalar("mdot_solve_used", 0.0)  # 0 = not needed
            return res

        converged = False
        it = 0

        for it in range(1, mdot_max_iter + 1):
            mdot_target = float(noz.get("mdot_choked", 0.0))
            if mdot_target <= 0.0:
                break

            rel_err = (mdot_target - m_dot) / max(m_dot, 1e-12)
            if abs(rel_err) < mdot_tol:
                converged = True
                break

            # Relaxed fixed-point update
            m_dot = max(1e-9, m_dot + mdot_relax * (mdot_target - m_dot))
            res, noz = self._run_once(ambient=ambient, m_dot=m_dot, afterburn=ab)

            # If the cycle transitions to unchoked, stop: no unique mdot constraint.
            if not bool(noz.get("choked", False)):
                break

        res.add_scalar("mdot_solve_iterations", float(it))
        res.add_scalar("mdot_solve_converged", 1.0 if converged else 0.0)
        res.add_scalar("mdot_solve_used", 1.0)  # 1 = auto solve attempted

        if update_design and converged:
            self.d.m_dot = float(m_dot)

        return res
