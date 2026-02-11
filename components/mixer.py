from __future__ import annotations

from dataclasses import dataclass
from .component import Component
from fluid_properties import FluidState, FluidModel

@dataclass
class Mixer(Component):
    pr: float  # Pt_out / min(Pt_in_core, Pt_in_byp) as a loss model
    mixed_model: FluidModel

    def process(self, core: FluidState, bypass: FluidState) -> FluidState:
        c = core.update()
        b = bypass.update()

        m = c.m_dot + b.m_dot
        if m <= 0:
            raise ValueError("Mixer requires positive total mass flow")

        # Simple stagnation mixing by mass-weighted total enthalpy using cp(T)
        # h_t = integral cp dT (approx)
        hc = c.model.h(c.T0)
        hb = b.model.h(b.T0)
        hmix = (c.m_dot * hc + b.m_dot * hb) / m

        # Invert h(T) approximately by iteration (monotonic)
        def h_of_T(T):
            return self.mixed_model.h(T)

        Tlo, Thi = 200.0, 4000.0
        for _ in range(60):
            Tmid = 0.5 * (Tlo + Thi)
            if h_of_T(Tmid) < hmix:
                Tlo = Tmid
            else:
                Thi = Tmid
        Tt_mix = 0.5 * (Tlo + Thi)

        Pt_in = min(c.p0, b.p0)
        Pt_out = Pt_in * self.pr

        out = c.copy_with(
            m_dot=m,
            T=Tt_mix,
            p=Pt_out,
            M=0.0,
            model=self.mixed_model,
            composition="products",  # treat as mixed hot/cold stream
        )
        out.T0, out.p0 = Tt_mix, Pt_out
        return out.update()
