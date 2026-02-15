from __future__ import annotations
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState, FluidModel


@dataclass
class Combustor(Component):
    """
    Combustor model with variable cp(T) and enthalpy-based solve.

    Inputs:
    - Pressure ratio pr (Pt_out/Pt_in)
    - burner efficiency eta_b
    - LHV (J/kg fuel)
    - target exit Tt_out (turbine inlet temperature)
    - products_model used for post-combustion thermodynamics

    Assumptions:
    - Adiabatic walls, no shaft work
    - Single "products" property model after combustion
    - Fuel-air ratio f solved from energy balance on stagnation enthalpy:

        Let m_air be inlet mass flow (kg/s), m_f = f*m_air.
        Outlet mass flow: m_out = m_air*(1+f)

        Energy balance:
          m_air*h_in + m_f*eta_b*LHV = m_out*h_out
        where:
          h_in = h_air(Tt_in)
          h_out = h_prod(Tt_out_target)

        Solve for f:
          h_in + f*eta_b*LHV = (1+f)*h_out
          => f*(eta_b*LHV - h_out) = h_out - h_in
          => f = (h_out - h_in) / (eta_b*LHV - h_out)

    This is a standard variable-cp consistent form (since h(T) already integrates cp(T)).
    """
    pr: float
    eta_b: float
    LHV: float
    Tt_out: float
    products_model: FluidModel

    def process(self, inlet: FluidState) -> tuple[FluidState, float]:
        Pt_out = inlet.Pt * self.pr

        # Inlet enthalpy (air model), outlet enthalpy (products model at target Tt_out)
        h_in = inlet.model.h(inlet.Tt)
        h_out = self.products_model.h(self.Tt_out)

        den = self.eta_b * self.LHV - h_out
        if den <= 0:
            raise ValueError("Combustor energy balance invalid: eta_b*LHV - h_out <= 0. Check Tt_out/LHV.")

        f = (h_out - h_in) / den
        if f < 0:
            f = 0.0

        m_out = inlet.m_dot * (1.0 + f)

        out = inlet.copy_with(
            m_dot=m_out,
            Tt=self.Tt_out,
            Pt=Pt_out,
            model=self.products_model,
            composition="products",
        )
        out.set_static_equal_total()
        return out.update_thermo(), float(f)
