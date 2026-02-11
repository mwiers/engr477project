from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from fluid_properties import FluidState

@dataclass
class Results:
    """Collect states and scalars produced during a run."""

    stations: Dict[str, FluidState] = field(default_factory=dict)
    scalars: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def add_state(self, key: str, state: FluidState) -> None:
        self.stations[key] = state

    def add_scalar(self, key: str, value: float) -> None:
        self.scalars[key] = float(value)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "stations": {k: vars(v) for k, v in self.stations.items()},
            "scalars": dict(self.scalars),
            "notes": list(self.notes),
        }
