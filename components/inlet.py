from __future__ import annotations
import math
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState


@dataclass
class Inlet(Component):
    """
    Diffuser / inlet model using total pressure recovery.

    Assumptions:
    - Adiabatic, no shaft work.
    - Total temperature is conserved from freestream stagnation (Tt0).
    - Total pressure decreases by a recovery factor: Pt2 = PR * Pt0.

    NOTE:
    - Ambient state should already have correct (Tt, Pt) computed externally (engine does this).
    """
    pr: float = 0.99  # Pt_out / Pt_in

    def process(self, inlet_total: FluidState) -> FluidState:
        out = inlet_total.copy_with()
        out.Pt = inlet_total.Pt * self.pr
        out.Tt = inlet_total.Tt
        out.set_static_equal_total()
        return out.update_thermo()
