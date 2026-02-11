from __future__ import annotations

from dataclasses import dataclass

from fluid_properties import FluidState

@dataclass(frozen=True)
class SpoolWork:
    """Shaft power requirements for LP and HP spools (W)."""
    lp: float
    hp: float

def compressor_power(inlet: FluidState, outlet: FluidState) -> float:
    """Compute compressor power from stagnation enthalpy rise (W)."""
    st_in = inlet.update()
    st_out = outlet.update()
    h_in = st_in.model.h(st_in.T0)
    h_out = st_out.model.h(st_out.T0)
    return st_out.m_dot * (h_out - h_in)

def fan_power(inlet: FluidState, core_out: FluidState, bypass_out: FluidState) -> float:
    """Fan power is based on total mass flow and stagnation enthalpy rise."""
    st_in = inlet.update()
    st_out = core_out.update()  # fan exit Tt is same for both
    h_in = st_in.model.h(st_in.T0)
    h_out = st_out.model.h(st_out.T0)
    return (core_out.m_dot + bypass_out.m_dot) * (h_out - h_in)
