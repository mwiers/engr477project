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
    - Produces a 'mixed' pseudo-fluid model whose cp(T) and R are mass-weighted blends
      of the incoming air and products models.
      For plotting/reporting, we enforce the second law by shifting the mixed model’s
      entropy reference so that s_out >= (m1*s1 + m2*s2)/(m1+m2) at the mixer outlet.
    """
    pr: float
    air_model: FluidModel
    products_model: FluidModel


    def process(self, core: FluidState, bypass: FluidState) -> FluidState:
        m_core = core.m_dot
        m_byp = bypass.m_dot
        m_tot = m_core + m_byp
        if m_tot <= 0.0:
            raise ValueError("Mixer requires positive total mass flow.")

        # 1) Pressure model (simple loss on the lower inlet total pressure)
        Pt_in = min(core.Pt, bypass.Pt)
        Pt_out = Pt_in * self.pr

        # 2) Build a mixed pseudo-fluid model using *mass fraction of products*
        #    (core assumed to be products, bypass assumed to be air)
        w_prod = m_core / m_tot  # 0..1

        mixed_model = FluidModel.make_mixed(
            air_model=self.air_model,
            products_model=self.products_model,
            w_products=w_prod,
            T_ref=self.air_model.T_ref,
            p_ref=self.air_model.p_ref,
            s_offset=0.0,  # we will set this after computing outlet Tt
        )

        # 3) Enthalpy mixing (stagnation)
        #    For a cycle deck we neglect kinetic energy terms and mix ht directly.
        h_core = core.model.h(core.Tt)
        h_byp = bypass.model.h(bypass.Tt)
        h_out = (m_core * h_core + m_byp * h_byp) / m_tot

        # Solve outlet total temperature from mixed model enthalpy
        Tt_out = mixed_model.T_from_h(h_out)

        # 4) Second-law safe entropy reporting:
        #    The pseudo-fluid switch (products/air -> mixed) can create non-comparable
        #    entropy references. We shift the mixed model entropy by a constant offset
        #    so that the mixer does not report an entropy decrease.
        s_target = (m_core * core.st + m_byp * bypass.st) / m_tot
        s_raw = mixed_model.s(Tt_out, Pt_out)
        s_offset = max(0.0, s_target - s_raw)  # enforce s_out >= s_target

        if s_offset > 0.0:
            mixed_model = FluidModel.make_mixed(
                air_model=self.air_model,
                products_model=self.products_model,
                w_products=w_prod,
                T_ref=self.air_model.T_ref,
                p_ref=self.air_model.p_ref,
                s_offset=s_offset,
            )

        # 5) Construct outlet state
        out = core.copy_with(
            m_dot=m_tot,
            Tt=Tt_out,
            Pt=Pt_out,
            model=mixed_model,
            composition="mixed",
        )
        out.set_static_equal_total()
        return out.update_thermo()

