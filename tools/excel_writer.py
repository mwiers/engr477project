from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from results_container import Results

@dataclass
class ExcelWriter:
    def write(self, results: Results, filepath: str | Path) -> Path:
        filepath = Path(filepath)
        stations = []
        for k, s in results.stations.items():
            stations.append({
                "station": k,
                "m_dot": s.m_dot,
                "T": s.T,
                "p": s.p,
                "M": s.M,
                "T0": s.T0,
                "p0": s.p0,
                "cp": s.cp,
                "gamma": s.gamma,
                "composition": s.composition,
            })
        df_st = pd.DataFrame(stations).sort_values("station")
        df_sc = pd.DataFrame([results.scalars]).T.reset_index()
        df_sc.columns = ["name", "value"]

        with pd.ExcelWriter(filepath, engine="openpyxl") as w:
            df_st.to_excel(w, index=False, sheet_name="stations")
            df_sc.to_excel(w, index=False, sheet_name="scalars")
        return filepath
