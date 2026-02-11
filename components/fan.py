from __future__ import annotations

from dataclasses import dataclass
from .component import Component
from fluid_properties import FluidState

@dataclass
class Fan(Component):
    pr: float  # pressure ratio
    eta: float  # isentropic efficiency
    bypass_ratio: float

    def process(self, inlet: FluidState) -> tuple[FluidState, FluidState]:
        st = inlet.update()
        if st.M != 0.0:
            st = st.copy_with(M=0.0)

        m_core = st.m_dot / (1.0 + self.bypass_ratio)
        m_byp = st.m_dot - m_core

        gm = st.model.gamma(st.T0)

        Pt_out = st.p0 * self.pr
        # Compressor (fan) temperature rise
        Tt_out_s = st.T0 * (self.pr) ** ((gm - 1.0) / gm)
        Tt_out = st.T0 + (Tt_out_s - st.T0) / self.eta

        core = st.copy_with(m_dot=m_core, T=Tt_out, p=Pt_out, M=0.0)
        byp = st.copy_with(m_dot=m_byp, T=Tt_out, p=Pt_out, M=0.0)
        # Store as stagnation=static since M=0
        core.T0, core.p0 = Tt_out, Pt_out
        byp.T0, byp.p0 = Tt_out, Pt_out
        return core.update(), byp.update()
