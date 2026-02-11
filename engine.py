from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fluid_properties import FluidModel, FluidState
from results_container import Results
from components.inlet import Inlet
from components.fan import Fan
from components.duct import Duct
from components.compressor import Compressor
from components.combustor import Combustor
from components.turbine import Turbine
from components.mixer import Mixer
from components.afterburner import Afterburner
from components.nozzle import Nozzle
from solvers.spool_balance import fan_power, compressor_power

@dataclass
class Ambient:
    T: float  # K
    p: float  # Pa
    M: float = 0.0

@dataclass
class EngineDesign:
    # Flow / cycle
    m_dot: float
    bypass_ratio: float
    fuel_LHV: float  # J/kg

    # Pressure ratios
    inlet_pr: float
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
    eta_diffuser: float  # (not used explicitly; inlet PR captures losses)
    eta_fan: float
    eta_lpc: float
    eta_hpc: float
    eta_burner: float
    eta_hpt: float
    eta_lpt: float
    eta_mech: float
    eta_nozzle: float

    # Temperatures
    Tt4: float  # turbine inlet temperature, K

    # Representative internal Mach numbers
    M_inlet: float = 0.5
    M_turb_exit: float = 0.5

    # Nozzle geometry
    nozzle_throat_d: float = 0.78
    nozzle_exit_d: float = 0.78

@dataclass
class AfterburnDesign:
    enabled: bool
    m_dot: float
    Tt7: float
    ab_pr: float
    eta_ab: float
    nozzle_eta: float
    throat_d: float
    exit_d: float

class TurbofanEngine:
    def __init__(
        self,
        design: EngineDesign,
        air_model: FluidModel,
        products_model: FluidModel,
    ) -> None:
        self.d = design
        self.air = air_model
        self.products = products_model

        # Components (dry)
        self.inlet = Inlet(name="inlet", pr=self.d.inlet_pr)
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
            Tt_out=self.d.Tt4,
            products_model=self.products,
        )
        self.hpt = Turbine(name="hpt", eta=self.d.eta_hpt, mech_eta=self.d.eta_mech)
        self.lpt = Turbine(name="lpt", eta=self.d.eta_lpt, mech_eta=self.d.eta_mech)
        self.mixer = Mixer(name="mixer", pr=self.d.mixer_pr, mixed_model=self.products)
        self.nozzle = Nozzle(
            name="nozzle",
            eta=self.d.eta_nozzle,
            pr=self.d.nozzle_pr,
            throat_d=self.d.nozzle_throat_d,
            exit_d=self.d.nozzle_exit_d,
        )

    def run(self, ambient: Ambient, afterburn: Optional[AfterburnDesign] = None) -> Results:
        res = Results()

        # Ambient/freestream state
        amb = FluidState(
            m_dot=self.d.m_dot,
            T=ambient.T,
            p=ambient.p,
            M=ambient.M,
            model=self.air,
            composition="air",
        ).update()
        res.add_state("a", amb)

        # Inlet/diffuser to engine face
        s2 = self.inlet.process(amb)
        res.add_state("2", s2)

        # Fan splits to core and bypass
        core_fan, byp_fan = self.fan.process(s2)
        res.add_state("21_core", core_fan)
        res.add_state("21_byp", byp_fan)

        # Bypass duct
        byp2 = self.bypass_duct.process(byp_fan)
        res.add_state("13", byp2)

        # LPC duct then LPC
        core2 = self.lpc_duct.process(core_fan)
        res.add_state("25", core2)
        core3 = self.lpc.process(core2)
        res.add_state("3", core3)

        # HPC duct then HPC
        core3d = self.hpc_duct.process(core3)
        res.add_state("3d", core3d)
        core4 = self.hpc.process(core3d)
        res.add_state("4", core4)

        # Combustor to Tt4
        core5, f_main = self.comb.process(core4)
        res.add_state("4.5", core5)
        res.add_scalar("f_main", f_main)

        # Shaft powers required (fan + LPC on LP spool, HPC on HP spool)
        P_fan = fan_power(s2, core_fan, byp_fan)
        P_lpc = compressor_power(core2, core3)
        P_hpc = compressor_power(core3d, core4)

        P_lp = P_fan + P_lpc
        P_hp = P_hpc
        res.add_scalar("P_fan_W", P_fan)
        res.add_scalar("P_lpc_W", P_lpc)
        res.add_scalar("P_hpc_W", P_hpc)

        # HP turbine drives HPC
        core6, w_hpt = self.hpt.process(core5, shaft_power_required=P_hp)
        res.add_state("5", core6)
        res.add_scalar("w_hpt_Jpkg", w_hpt)

        # LP turbine drives fan+LPC
        core7, w_lpt = self.lpt.process(core6, shaft_power_required=P_lp)
        res.add_state("6", core7)
        res.add_scalar("w_lpt_Jpkg", w_lpt)

        # Mix core + bypass
        mixed = self.mixer.process(core7, byp2)
        res.add_state("7", mixed)

        # Optional afterburner
        f_ab = 0.0
        nozzle = self.nozzle
        m_dot_in = mixed.m_dot

        if afterburn and afterburn.enabled:
            if afterburn.m_dot != m_dot_in:
                mixed = mixed.copy_with(m_dot=afterburn.m_dot)
                res.notes.append("Afterburn m_dot differs from dry; mixed stream m_dot overwritten (approx).")

            ab = Afterburner(
                name="afterburner",
                pr=afterburn.ab_pr,
                eta_b=afterburn.eta_ab,
                LHV=self.d.fuel_LHV,
                Tt_out=afterburn.Tt7,
                products_model=self.products,
            )
            mixed2, f_ab = ab.process(mixed)
            res.add_state("8", mixed2)
            res.add_scalar("f_ab", f_ab)

            nozzle = Nozzle(
                name="nozzle_ab",
                eta=afterburn.nozzle_eta,
                pr=self.d.nozzle_pr,
                throat_d=afterburn.throat_d,
                exit_d=afterburn.exit_d,
            )
            flow_to_noz = mixed2
        else:
            flow_to_noz = mixed

        # Nozzle / thrust
        noz = nozzle.process(flow_to_noz, p_ambient=ambient.p)
        res.add_scalar("V_exit_mps", noz["V"])
        res.add_scalar("Me_exit", noz["Me"])
        res.add_scalar("pe_exit_Pa", noz["pe"])
        res.add_scalar("choked", 1.0 if noz["choked"] else 0.0)

        # Ram drag: freestream momentum
        V0 = amb.M * (amb.gamma * amb.R * amb.T) ** 0.5
        F_net = noz["F_gross"] - self.d.m_dot * V0
        res.add_scalar("F_gross_N", noz["F_gross"])
        res.add_scalar("F_net_N", F_net)

        # Fuel flow & TSFC
        m_fuel_main = (self.d.m_dot / (1.0 + self.d.bypass_ratio)) * f_main
        m_fuel_ab = flow_to_noz.m_dot * f_ab if afterburn and afterburn.enabled else 0.0
        m_fuel = m_fuel_main + m_fuel_ab
        res.add_scalar("m_fuel_kgps", m_fuel)
        tsfc = m_fuel / max(F_net, 1e-9)
        res.add_scalar("TSFC_kg_per_Ns", tsfc)
        st = F_net / self.d.m_dot
        res.add_scalar("ST_Ns_per_kg", st)

        return res
