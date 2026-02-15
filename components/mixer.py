from __future__ import annotations
from dataclasses import dataclass

from .component import Component
from fluid_properties import FluidState, FluidModel


@dataclass
class Mixer(Component):
    """
    Mixer model combining two streams into one.

    Assumptions:
    - Perfect mixing at stagnation conditions (cycle deck assumption).
    - No shaft work, no heat transfer.
    - Stagnation enthalpy is conserved (mass-weighted).
    - Total pressure is approximated using a loss factor applied to the minimum inlet Pt:
         Pt_out = PR * min(Pt_core, Pt_bypass)

    Notes:
    - True mixing is irreversible even without explicit pressure loss; here we represent
      most of that irreversibility with the Pt loss model and enthalpy averaging.
    - Output uses a single chosen property model (mixed_model).
    """
    pr: float
    mixed_model: FluidModel

    def process(self, core: FluidState, bypass: FluidState) -> FluidState:
        """
        Mix the core and bypass streams, returning the mixed outlet state.
        """
        m = core.m_dot + bypass.m_dot
        if m <= 0:
            raise ValueError("Mixer requires positive total mass flow.")

        # Mass-weighted stagnation enthalpy (variable cp captured via h(T))
        h_mix = (core.m_dot * core.model.h(core.Tt) + bypass.m_dot * bypass.model.h(bypass.Tt)) / m

        # Solve mixed stagnation temperature from mixed model enthalpy
        Tt_mix = self.mixed_model.T_from_h(h_mix)

        Pt_in = min(core.Pt, bypass.Pt)
        Pt_out = Pt_in * self.pr

        out = core.copy_with(
            m_dot=m,
            Tt=Tt_mix,
            Pt=Pt_out,
            model=self.mixed_model,
            composition="products",
        )
        out.set_static_equal_total()
        return out.update_thermo()
