from __future__ import annotations

from dataclasses import dataclass
from .component import Component
from fluid_properties import FluidState, FluidModel

@dataclass
class Afterburner(Component):
    pr: float
    eta_b: float
    LHV: float
    Tt_out: float
    products_model: FluidModel

    def process(self, inlet: FluidState) -> tuple[FluidState, float]:
        st = inlet.update()
        Pt_out = st.p0 * self.pr

        cp_in = st.model.cp(st.T0)
        cp_out = self.products_model.cp(self.Tt_out)

        # fuel-air ratio relative to incoming *total* mass flow (already includes core fuel)
        num = cp_out * self.Tt_out - cp_in * st.T0
        den = self.eta_b * self.LHV - cp_out * self.Tt_out
        if den <= 0:
            raise ValueError("Invalid afterburner balance (denominator <= 0).")
        f_ab = num / den
        if f_ab < 0:
            f_ab = 0.0

        m_out = st.m_dot * (1.0 + f_ab)
        out = st.copy_with(
            m_dot=m_out,
            T=self.Tt_out,
            p=Pt_out,
            M=0.0,
            model=self.products_model,
            composition="products",
        )
        out.T0, out.p0 = self.Tt_out, Pt_out
        return out.update(), f_ab
