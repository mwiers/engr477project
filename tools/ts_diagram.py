from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import matplotlib.pyplot as plt

from results_container import Results


@dataclass
class TSDiagram:
    """
    Utility to plot a T–s diagram from stored station stagnation states.

    Uses:
    - T axis: Tt (K)
    - s axis: st (J/kg-K) relative to model reference

    You can plot either:
    - the default station order 1..12 (if present), or
    - a custom sequence.
    """

    default_order: Sequence[str] = ("1", "2", "3", "4", "5", "6", "7", "8", "10", "11", "12")

    def plot(
        self,
        results: Results,
        *,
        station_order: Sequence[str] | None = None,
        title: str = "T–s Diagram (Stagnation States)",
        savepath: str | None = None,
    ):
        order = station_order or self.default_order

        xs = []
        ys = []
        labels = []

        for k in order:
            if k in results.stations:
                st = results.stations[k]
                xs.append(st.st)
                ys.append(st.Tt)
                labels.append(k)

        fig, ax = plt.subplots()
        ax.plot(xs, ys, marker="o")
        ax.set_xlabel("s_t  [J/(kg·K)]  (relative)")
        ax.set_ylabel("T_t  [K]")
        ax.grid(True)
        ax.set_title(title)

        # Station annotations
        for x, y, lab in zip(xs, ys, labels):
            ax.annotate(lab, (x, y), textcoords="offset points", xytext=(6, 6))

        if savepath:
            fig.savefig(savepath, dpi=200, bbox_inches="tight")
        return fig, ax
