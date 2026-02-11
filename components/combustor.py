from __future__ import annotations

from dataclasses import dataclass
from .component import Component
from fluid_properties import FluidState, FluidModel

@dataclass
class Combustor(Component):
    pr: float  # Pt_out / Pt_in
    eta_b: float
    LHV: float  # J/kg
    Tt_out: float  # target turbine inlet temperature
    products_model: FluidModel

    def process(self, inlet: FluidState) -> tuple[FluidState, float]:
        st = inlet.update()
        Pt_out = st.p0 * self.pr

        cp_air = st.model.cp(st.T0)
        cp_g = self.products_model.cp(self.Tt_out)

        # Energy balance for fuel-air ratio f (kg_fuel/kg_air)
        # (1+f)*cp_g*Tt4 - cp_air*Tt3 = eta_b*f*LHV
        # => f = (cp_g*Tt4 - cp_air*Tt3) / (eta_b*LHV - cp_g*Tt4)
        num = cp_g * self.Tt_out - cp_air * st.T0
        den = self.eta_b * self.LHV - cp_g * self.Tt_out
        if den <= 0:
            raise ValueError("Invalid combustor balance (denominator <= 0). Check Tt_out/LHV.")
        f = num / den
        if f < 0:
            f = 0.0

        m_dot_g = st.m_dot * (1.0 + f)
        out = st.copy_with(
            m_dot=m_dot_g,
            T=self.Tt_out,
            p=Pt_out,
            M=0.0,
            model=self.products_model,
            composition="products",
        )
        out.T0, out.p0 = self.Tt_out, Pt_out
        return out.update(), f
