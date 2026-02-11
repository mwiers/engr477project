from __future__ import annotations

from dataclasses import dataclass
from .component import Component
from fluid_properties import FluidState

@dataclass
class Turbine(Component):
    eta: float  # isentropic efficiency
    mech_eta: float = 0.99  # shaft mechanical efficiency

    def process(self, inlet: FluidState, shaft_power_required: float) -> tuple[FluidState, float]:
        """Extract shaft power from the flow.

        Args:
            inlet: turbine inlet stagnation state (M ~ 0)
            shaft_power_required: W required on the shaft (positive)
        Returns:
            (outlet_state, specific_work_extracted) where specific work is J/kg of turbine flow.
        """
        st = inlet.update()
        if shaft_power_required < 0:
            raise ValueError("shaft_power_required must be >= 0")

        m_dot = st.m_dot
        if m_dot <= 0:
            raise ValueError("turbine m_dot must be > 0")

        # Actual enthalpy drop needed in gas to supply shaft power considering mechanical efficiency
        power_from_gas = shaft_power_required / self.mech_eta  # W
        w = power_from_gas / m_dot  # J/kg

        cp = st.model.cp(st.T0)
        gm = st.model.gamma(st.T0)

        dT_actual = w / cp
        Tt_out = st.T0 - dT_actual
        if Tt_out <= 1.0:
            raise ValueError("Turbine outlet temperature became non-physical.")

        # Isentropic temperature drop would be smaller than actual for eta<1:
        # eta_t = (h_in - h_out_actual)/(h_in - h_out_isentropic)
        # => (T_in - T_out_s) = (T_in - T_out_actual)/eta
        Tt_out_s = st.T0 - (st.T0 - Tt_out) / self.eta

        # Pressure ratio from isentropic relation
        pr = (Tt_out_s / st.T0) ** (gm / (gm - 1.0))  # Pt_out / Pt_in (turbine < 1)
        Pt_out = st.p0 * pr

        out = st.copy_with(T=Tt_out, p=Pt_out, M=0.0)
        out.T0, out.p0 = Tt_out, Pt_out
        return out.update(), w
