from __future__ import annotations
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState
from math import exp


@dataclass
class Turbine(Component):
    """
    Turbine model with variable cp(T), defined by required shaft power extraction.

    Inputs:
    - eta: turbine isentropic efficiency
    - mech_eta: mechanical efficiency from gas power -> shaft power

    Method:
    1) Required shaft power: W_shaft (W)
       Gas must provide: W_gas = W_shaft / mech_eta
    2) Specific work extracted from gas:
         w = W_gas / m_dot
       This corresponds to an enthalpy drop:
         h_out = h_in - w
    3) Solve Tt_out from h_out via T_from_h.
    4) Determine the isentropic reference endpoint Tt_out_s using entropy conservation:
         s(Tt_out_s, Pt_out_s) = s(Tt_in, Pt_in)
       But we don't know Pt_out yet. We use turbine efficiency definition:

         eta_t = (h_in - h_out_actual)/(h_in - h_out_s)
         => h_out_s = h_in - (h_in - h_out_actual)/eta_t

       Then:
         find Tt_out_s from h_out_s
         compute Pt_out by enforcing s(Tt_out_s, Pt_out) = s(Tt_in, Pt_in)
         i.e. solve Pt_out from:
            s(Tt_out_s, Pt_out) = s_in
         For ideal gas with variable cp, this is:
            ∫cp/T dT - R ln(Pt_out/p_ref) = s_in + R ln(Pt_in/p_ref) - ∫cp/T dT
         Numerically, easiest is to solve Pt_out by:
            Pt_out = p_ref * exp( (∫cp/T dT - s_target)/R )
         But since FluidModel.s(T,p) already includes -R ln(p/p_ref),
         we can rearrange directly.

    NOTE:
    - This turbine model is thermodynamically consistent with variable cp(T) on enthalpy.
    """
    eta: float
    mech_eta: float = 0.99

    def process(self, inlet: FluidState, shaft_power_required: float) -> tuple[FluidState, float]:
        if shaft_power_required < 0:
            raise ValueError("shaft_power_required must be >= 0")
        if inlet.m_dot <= 0:
            raise ValueError("Turbine requires m_dot > 0")

        h_in = inlet.model.h(inlet.Tt)

        # Gas power required before mechanical losses
        W_gas = shaft_power_required / max(self.mech_eta, 1e-9)
        w = W_gas / inlet.m_dot  # J/kg

        h_out = h_in - w
        Tt_out = inlet.model.T_from_h(h_out)

        # Isentropic reference enthalpy drop using turbine efficiency
        # eta = (h_in - h_out_actual)/(h_in - h_out_s)  => h_out_s = h_in - (h_in - h_out_actual)/eta
        dh_actual = h_in - h_out
        dh_s = dh_actual / max(self.eta, 1e-9)
        h_out_s = h_in - dh_s
        Tt_out_s = inlet.model.T_from_h(h_out_s)

        # Now determine Pt_out such that s(Tt_out_s, Pt_out) = s(Tt_in, Pt_in)
        # Using FluidModel.s definition:
        #   s(T,p) = I(T) - R ln(p/p_ref)
        # Solve for p_out:
        #   I(Tt_out_s) - R ln(Pt_out/p_ref) = s_in
        # => ln(Pt_out/p_ref) = (I(Tt_out_s) - s_in)/R
        # => Pt_out = p_ref * exp((I(Tt_out_s) - s_in)/R)
        s_in = inlet.model.s(inlet.Tt, inlet.Pt)
        I_out_s = inlet.model.s(Tt_out_s, inlet.model.p_ref)  # = I(Tt_out_s) - R ln(p_ref/p_ref) = I(Tt_out_s)
        Pt_out = inlet.model.p_ref * exp((I_out_s - s_in) / inlet.model.R)

        out = inlet.copy_with(Tt=Tt_out, Pt=Pt_out)
        out.set_static_equal_total()
        return out.update_thermo(), float(w)
