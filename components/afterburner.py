from __future__ import annotations
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState, FluidModel


@dataclass
class Afterburner(Component):
    """
    Afterburner model (same structure as combustor) with variable cp(T) via enthalpy.

    Energy balance:
      m_in*h_in + m_f*eta_b*LHV = m_out*h_out
      m_out = m_in*(1+f_ab),  m_f = f_ab*m_in

    => f_ab = (h_out - h_in)/(eta_b*LHV - h_out)
    """
    pr: float
    eta_b: float
    LHV: float
    Tt_out: float
    products_model: FluidModel

    def process(self, inlet: FluidState) -> tuple[FluidState, float]:
        Pt_out = inlet.Pt * self.pr

        h_in = inlet.model.h(inlet.Tt)
        h_out = self.products_model.h(self.Tt_out)

        den = self.eta_b * self.LHV - h_out
        if den <= 0:
            raise ValueError("Afterburner energy balance invalid: eta_b*LHV - h_out <= 0.")

        f_ab = (h_out - h_in) / den
        if f_ab < 0:
            f_ab = 0.0

        m_out = inlet.m_dot * (1.0 + f_ab)

        out = inlet.copy_with(
            m_dot=m_out,
            Tt=self.Tt_out,
            Pt=Pt_out,
            model=self.products_model,
            composition="products",
        )
        out.set_static_equal_total()
        return out.update_thermo(), float(f_ab)
