from __future__ import annotations

from dataclasses import dataclass
from .component import Component
from fluid_properties import FluidState

@dataclass
class Compressor(Component):
    pr: float
    eta: float  # isentropic efficiency

    def process(self, inlet: FluidState) -> FluidState:
        st = inlet.update()
        gm = st.model.gamma(st.T0)
        Pt_out = st.p0 * self.pr
        Tt_out_s = st.T0 * (self.pr) ** ((gm - 1.0) / gm)
        Tt_out = st.T0 + (Tt_out_s - st.T0) / self.eta
        out = st.copy_with(T=Tt_out, p=Pt_out, M=0.0)
        out.T0, out.p0 = Tt_out, Pt_out
        return out.update()
