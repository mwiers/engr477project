from __future__ import annotations

from dataclasses import dataclass
from .component import Component
from fluid_properties import FluidState

@dataclass
class Duct(Component):
    pr: float  # Pt_out / Pt_in

    def process(self, inlet: FluidState) -> FluidState:
        st = inlet.update()
        out = st.copy_with(M=0.0)
        out.T0 = st.T0
        out.p0 = st.p0 * self.pr
        out.T = out.T0
        out.p = out.p0
        return out.update()
