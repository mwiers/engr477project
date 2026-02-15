from __future__ import annotations

from math import sqrt
from dataclasses import dataclass
from typing import Optional

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
    TAB: float
    ab_pr: float
    eta_ab: float
    nozzle_eta: float
    throat_d: float
    exit_d: float


class TurbofanEngine:
    """
    Variable-cp turbofan cycle model with explicit stagnation state tracking.

    Station labeling:
      1 = ambient
      2 = after inlet/diffuser
      3 = after fan (core stream entering LPC + bypass stream entering bypass duct)
      4 = after LPC
      5 = after HPC
      6 = after combustor
      7 = after HPT (powers HPC)
      8 = after LPT (powers fan + LPC)
      9 = after bypass duct
      10 = after mixer (mixes 8 and 9)
      11 = after afterburner (if disabled, 11 is omitted; nozzle can take 11)
      12 = after nozzle (reported as a state with Pt/Tt from nozzle inlet; static exit in scalars)
    """

    def __init__(self, design: EngineDesign, air_model: FluidModel, products_model: FluidModel) -> None:
        self.d = design
        self.air = air_model
        self.products = products_model

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

        self.mixer = Mixer(name="mixer", pr=self.d.mixer_pr, mixed_model=self.products)

        self.nozzle_dry = Nozzle(
            name="nozzle",
            eta=self.d.eta_nozzle,
            pr=self.d.nozzle_pr,
            throat_d=self.d.nozzle_throat_d,
            exit_d=self.d.nozzle_exit_d,
        )

    def run(self, ambient: Ambient, afterburn: Optional[AfterburnDesign] = None) -> Results:
        res = Results(baseline_station="2")

        # ---------------------------
        # Station 1: ambient
        # ---------------------------
        # Compute freestream stagnation from static + Mach (cycle uses Pt/Tt).
        # We use gamma(T) at ambient temperature as an approximation for stagnation relation.
        gamma0 = self.air.gamma(ambient.T)
        Tt0 = stagnation_temperature(ambient.T, ambient.M, gamma0)
        Pt0 = stagnation_pressure(ambient.p, ambient.M, gamma0)
    
        s1 = FluidState(
            m_dot=self.d.m_dot,
            model=self.air,
            composition="air",
            Tt=Tt0,
            Pt=Pt0,
            T=ambient.T,
            p=ambient.p,
            M=ambient.M,
        ).update_thermo()
        res.add_state("1", s1)

        # ---------------------------
        # Station 2: inlet/diffuser
        # ---------------------------
        s2 = self.diffuser.process(s1)
        res.add_state("2", s2)

        # ---------------------------
        # Station 3: fan exit (core + bypass share same Tt/Pt)
        # ---------------------------
        core3, byp3 = self.fan.process(s2)
        # Store a representative "3" state as the fan exit total state (use core copy).
        s3 = core3.copy_with(m_dot=s2.m_dot)  # fan exit before split (conceptual)
        s3.set_static_equal_total()
        res.add_state("3", s3)

        # ---------------------------
        # Station 4: LPC exit (core stream)
        # ---------------------------
        core3_to_lpc = self.lpc_duct.process(core3)
        s4 = self.lpc.process(core3_to_lpc)
        res.add_state("4", s4)

        # ---------------------------
        # Station 5: HPC exit
        # ---------------------------
        s4_to_hpc = self.hpc_duct.process(s4)
        s5 = self.hpc.process(s4_to_hpc)
        res.add_state("5", s5)

        # ---------------------------
        # Station 6: combustor exit
        # ---------------------------
        s6, f_main = self.comb.process(s5)
        res.add_state("6", s6)
        res.add_scalar("f_main", f_main)

        # ---------------------------
        # Spool power requirements (enthalpy-based, variable-cp consistent)
        # ---------------------------
        # Fan: treat station 3 (pre-split) as fan exit for power
        W_fan = fan_power(s2, s3)

        # LPC power: from core3_to_lpc -> s4 with m_dot = core stream
        W_lpc = power_required(core3_to_lpc, s4)

        # HPC power: from s4_to_hpc -> s5
        W_hpc = power_required(s4_to_hpc, s5)

        W_lpt = W_fan + W_lpc
        W_hpt = W_hpc

        res.add_scalar("W_fan_W", W_fan)
        res.add_scalar("W_lpc_W", W_lpc)
        res.add_scalar("W_hpc_W", W_hpc)

        # ---------------------------
        # Station 7: HPT exit (powers HPC)
        # ---------------------------
        s7, w_hpt = self.hpt.process(s6, shaft_power_required=W_hpt)
        res.add_state("7", s7)
        res.add_scalar("w_hpt_Jpkg", w_hpt)

        # ---------------------------
        # Station 8: LPT exit (powers fan + LPC)
        # ---------------------------
        s8, w_lpt = self.lpt.process(s7, shaft_power_required=W_lpt)
        res.add_state("8", s8)
        res.add_scalar("w_lpt_Jpkg", w_lpt)

        # ---------------------------
        # Station 9: bypass duct exit
        # ---------------------------
        s9 = self.bypass_duct.process(byp3)
        res.add_state("9", s9)

        # ---------------------------
        # Station 10: mixer exit
        # ---------------------------
        s10 = self.mixer.process(s8, s9)
        res.add_state("10", s10)

        # ---------------------------
        # Station 11: afterburner (optional)
        # ---------------------------
        nozzle = self.nozzle_dry
        s_noz_in = s10
        f_ab = 0.0

        if afterburn and afterburn.enabled:
            ab = Afterburner(
                name="afterburner",
                pr=afterburn.ab_pr,
                eta_b=afterburn.eta_ab,
                LHV=self.d.fuel_LHV,
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
                pr=self.d.nozzle_pr,
                throat_d=afterburn.throat_d,
                exit_d=afterburn.exit_d,
            )

        # ---------------------------
        # Nozzle expansion & thrust
        # ---------------------------
        noz = nozzle.process(s_noz_in, p_ambient=ambient.p)

        res.add_scalar("V_exit_mps", noz["V"])
        res.add_scalar("Me_exit", noz["Me"])
        res.add_scalar("pe_exit_Pa", noz["pe"])
        res.add_scalar("choked", 1.0 if noz["choked"] else 0.0)
        res.add_scalar("F_gross_N", noz["F_gross"])

        # Ram drag from freestream velocity
        a0 = sqrt(gamma0 * self.air.R * ambient.T)
        V0 = ambient.M * a0
        F_net = noz["F_gross"] - self.d.m_dot * V0
        res.add_scalar("F_net_N", F_net)
        res.add_scalar("V_freestream_mps", V0)

        # Fuel flow and TSFC (using station definitions)
        m_core = self.d.m_dot / (1.0 + self.d.bypass_ratio)
        m_f_main = m_core * f_main
        m_f_ab = s10.m_dot * f_ab if (afterburn and afterburn.enabled) else 0.0
        m_f = m_f_main + m_f_ab

        res.add_scalar("m_fuel_kgps", m_f)
        res.add_scalar("TSFC_kg_per_Ns", m_f / max(F_net, 1e-12))
        res.add_scalar("ST_Ns_per_kg", F_net / max(m_core, 1e-12))

        # ---------------------------
        # Station 12: after nozzle (cycle reporting)
        # ---------------------------
        # In a cycle deck, station 12 is typically used for nozzle exit reporting.
        # Here we store a state with nozzle-inlet total conditions after nozzle-duct loss,
        # and we store exit static properties in scalars (Te, pe, Me, V).
        s12 = s_noz_in.copy_with(Tt=noz["Tt"], Pt=noz["Pt"])
        s12.T = noz["Te"]
        s12.p = noz["pe"]
        s12.M = noz["Me"]
        s12.update_thermo()
        res.add_state("12", s12)

        return res
