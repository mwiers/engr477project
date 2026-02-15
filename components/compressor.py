from __future__ import annotations
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState


@dataclass
class Compressor(Component):
    """
    Generic compressor model with variable cp(T).

    Inputs:
    - Pressure ratio PR = Pt_out/Pt_in
    - Isentropic efficiency eta_c

    Method:
    1) Compute isentropic endpoint temperature Tt_out_s by enforcing:
         s(Tt_out_s, Pt_out) = s(Tt_in, Pt_in)
       using variable-cp entropy integration.
    2) Convert that to enthalpy rise for the isentropic process:
         Δh_s = h(Tt_out_s) - h(Tt_in)
    3) Apply compressor efficiency:
         eta_c = Δh_s / Δh_actual  =>  Δh_actual = Δh_s / eta_c
    4) Solve for Tt_out from enthalpy:
         h(Tt_out) = h(Tt_in) + Δh_actual
    """
    pr: float
    eta: float

    def process(self, inlet: FluidState) -> FluidState:
        """
        Computes and returns the compressor outlet state given the inlet state.
        """
        Pt_in, Tt_in = inlet.Pt, inlet.Tt
        Pt_out = Pt_in * self.pr

        # Isentropic temperature solve using variable-cp entropy definition
        Tt_out_s = inlet.model.T_isentropic_from_p_ratio(Tt_in, Pt_in, Pt_out)

        h_in = inlet.model.h(Tt_in)
        h_out_s = inlet.model.h(Tt_out_s)
        dh_s = h_out_s - h_in

        dh_actual = dh_s / max(self.eta, 1e-9)
        h_out = h_in + dh_actual

        Tt_out = inlet.model.T_from_h(h_out)

        out = inlet.copy_with(Tt=Tt_out, Pt=Pt_out)
        out.set_static_equal_total()
        return out.update_thermo()
