from __future__ import annotations
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState


@dataclass
class Duct(Component):
    """
    Duct / diffuser / inter-component loss model.

    Assumptions:
    - Adiabatic, no shaft work.
    - Stagnation temperature constant.
    - Stagnation pressure reduced by PR: Pt_out = PR * Pt_in.

    Entropy increases due to pressure loss:
      Δs = -R ln(Pt_out/Pt_in) > 0 (for constant cp ideal-gas intuition),
    and in variable-cp form is captured via s(Tt,Pt).
    """
    pr: float  # Pt_out / Pt_in

    def process(self, inlet: FluidState) -> FluidState:
        out = inlet.copy_with()
        out.Pt = inlet.Pt * self.pr
        out.Tt = inlet.Tt
        out.set_static_equal_total()
        return out.update_thermo()
