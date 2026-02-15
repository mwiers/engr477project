from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Component:
    """
    Base class for engine components.

    Convention:
    - Components accept and return FluidState(s) with stagnation properties (Tt, Pt).
    - Each component is responsible for applying its own assumptions (losses, efficiency, etc.)
      and for returning a thermodynamically-updated output state.
    """
    name: str

    def __call__(self, *args, **kwargs):
        return self.process(*args, **kwargs)

    def process(self, *args, **kwargs):
        raise NotImplementedError
