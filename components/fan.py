from __future__ import annotations
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState


@dataclass
class Fan(Component):
    """
    Fan model (compressor + split).

    Assumptions:
    - Single fan stage compresses total flow from Pt_in to Pt_out = PR*Pt_in.
    - Variable cp accounted via entropy-based isentropic endpoint + enthalpy efficiency.
    - Flow is then split by bypass ratio beta:
         m_core = m_total/(1+beta),  m_bypass = m_total - m_core
    - Both streams share the same exit stagnation state (Tt, Pt).

    Note:
    - This is a cycle-deck fan; no map matching or corrected flow.
    """
    pr: float
    eta: float
    bypass_ratio: float

    def process(self, inlet: FluidState) -> tuple[FluidState, FluidState]:
        Pt_in, Tt_in = inlet.Pt, inlet.Tt
        Pt_out = Pt_in * self.pr

        Tt_out_s = inlet.model.T_isentropic_from_p_ratio(Tt_in, Pt_in, Pt_out)

        h_in = inlet.model.h(Tt_in)
        h_out_s = inlet.model.h(Tt_out_s)
        dh_s = h_out_s - h_in
        dh_actual = dh_s / max(self.eta, 1e-9)

        h_out = h_in + dh_actual
        Tt_out = inlet.model.T_from_h(h_out)

        m_core = inlet.m_dot / (1.0 + self.bypass_ratio)
        m_byp = inlet.m_dot - m_core

        core = inlet.copy_with(m_dot=m_core, Tt=Tt_out, Pt=Pt_out)
        byp = inlet.copy_with(m_dot=m_byp, Tt=Tt_out, Pt=Pt_out)

        core.set_static_equal_total()
        byp.set_static_equal_total()
        return core.update_thermo(), byp.update_thermo()
