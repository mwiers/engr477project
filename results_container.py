from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from fluid_properties import FluidState


@dataclass
class Results:
    """
    Storage of run outputs.

    - stations: mapping station label -> FluidState
    - scalars: mapping name -> float
    - notes: list of human-readable notes

    New:
    - baseline_station: station label used for delta reporting (default "2")
    - derived: convenience deltas (computed on request)
    """
    stations: Dict[str, FluidState] = field(default_factory=dict)
    scalars: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    baseline_station: str = "2"

    def add_state(self, key: str, state: FluidState) -> None:
        self.stations[str(key)] = state

    def add_scalar(self, key: str, value: float) -> None:
        self.scalars[str(key)] = float(value)

    def get_baseline(self) -> FluidState:
        if self.baseline_station not in self.stations:
            raise KeyError(f"Baseline station '{self.baseline_station}' not found.")
        return self.stations[self.baseline_station]

    def station_deltas(self, baseline: Optional[str] = None) -> Dict[str, Dict[str, float]]:
        """
        Return per-station deltas relative to baseline station:
          Δht = ht - ht_baseline
          Δst = st - st_baseline
          ΔTt = Tt - Tt_baseline
          ΔPt = Pt - Pt_baseline
        """
        base_key = baseline or self.baseline_station
        if base_key not in self.stations:
            raise KeyError(f"Baseline station '{base_key}' not found.")
        b = self.stations[base_key]

        out: Dict[str, Dict[str, float]] = {}
        for k, s in self.stations.items():
            out[k] = {
                "dTt": float(s.Tt - b.Tt),
                "dPt": float(s.Pt - b.Pt),
                "dht": float(s.ht - b.ht),
                "dst": float(s.st - b.st),
            }
        return out

    def as_dict(self) -> Dict[str, Any]:
        return {
            "stations": {k: vars(v) for k, v in self.stations.items()},
            "scalars": dict(self.scalars),
            "notes": list(self.notes),
            "baseline_station": self.baseline_station,
        }
