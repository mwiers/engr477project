from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import matplotlib.pyplot as plt

@dataclass
class Plotter:
    def plot_parametric(self, x, y, xlabel: str, ylabel: str, title: str, filepath: Optional[str] = None):
        plt.figure()
        plt.plot(x, y)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(title)
        plt.grid(True)
        if filepath:
            plt.savefig(filepath, dpi=200, bbox_inches="tight")
        return plt.gcf()
