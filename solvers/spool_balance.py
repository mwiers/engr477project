from __future__ import annotations

from dataclasses import dataclass
from fluid_properties import FluidState


@dataclass(frozen=True)
class SpoolWork:
    lp: float
    hp: float


def power_required(inlet: FluidState, outlet: FluidState) -> float:
    """
    Component shaft power required (compressor/fan) from stagnation enthalpy rise:
      W = m_dot * (h_t,out - h_t,in)

    With variable cp, h_t is computed from integrated h(Tt).
    """
    h_in = inlet.model.h(inlet.Tt)
    h_out = outlet.model.h(outlet.Tt)
    return outlet.m_dot * (h_out - h_in)


def fan_power(inlet: FluidState, fan_exit: FluidState) -> float:
    """
    Fan power uses total inlet mass flow (inlet.m_dot) and fan exit enthalpy.
    Fan exit state should represent the fan outlet (same for core/bypass pre-split).
    """
    h_in = inlet.model.h(inlet.Tt)
    h_out = fan_exit.model.h(fan_exit.Tt)
    return inlet.m_dot * (h_out - h_in)
