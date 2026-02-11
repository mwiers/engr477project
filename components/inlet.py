from __future__ import annotations

from dataclasses import dataclass
from .component import Component
from fluid_properties import FluidState

@dataclass
class Inlet(Component):
    pr: float = 0.99  # Pt_out / Pt_in (loss)
    # Adiabatic diffuser: Tt constant (in absence of work/heat). We still compute from freestream M.
    def process(self, ambient: FluidState) -> FluidState:
        amb = ambient.update()
        Pt_in = amb.p0
        Tt_in = amb.T0
        out = amb.copy_with(M=0.0)  # stagnation conditions at engine face (assume M~0 inside)
        out.T0 = Tt_in
        out.p0 = Pt_in * self.pr
        # Set static equal to stagnation (M=0)
        out.T = out.T0
        out.p = out.p0
        return out.update()
