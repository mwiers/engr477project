from __future__ import annotations

from dataclasses import is_dataclass, asdict
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
from results_container import Results


def _to_builtin(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Mapping):
        return {str(k): _to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_builtin(v) for v in obj]
    return obj


def _flatten_dict(d: Mapping[str, Any], prefix: str = "", sep: str = ".") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{sep}{k}" if prefix else str(k)
        if isinstance(v, Mapping):
            out.update(_flatten_dict(v, prefix=key, sep=sep))
        elif isinstance(v, (list, tuple)):
            out[key] = str(v)
        else:
            out[key] = v
    return out


def dump_results_to_excel(
    results: Results,
    filepath: str | Path,
    *,
    run_parameters: Any | None = None,
    extra_parameters: dict[str, Any] | None = None,
    baseline_station: str | None = None,
    sheet_prefix: str = "",
) -> Path:
    """
    Dump stations + scalars + parameters + thermo deltas to Excel.
    Includes ht/st and Δht/Δst relative to chosen baseline station (default results.baseline_station).
    """
    filepath = Path(filepath)
    base = baseline_station or results.baseline_station
    deltas = results.station_deltas(base)

    station_rows: list[dict[str, Any]] = []
    for station_name, st in results.stations.items():
        d = deltas[station_name]
        station_rows.append({
            "station": station_name,
            "m_dot": st.m_dot,
            "Tt": st.Tt,
            "Pt": st.Pt,
            "ht": st.ht,
            "st": st.st,
            "cp_t": st.cp_t,
            "gamma_t": st.gamma_t,
            "composition": st.composition,
            "model": type(st.model).__name__,
            "dTt_from_" + base: d["dTt"],
            "dPt_from_" + base: d["dPt"],
            "dht_from_" + base: d["dht"],
            "dst_from_" + base: d["dst"],
        })

    df_stations = pd.DataFrame(station_rows).sort_values("station") if station_rows else pd.DataFrame()

    scalar_rows = [{"name": k, "value": v} for k, v in results.scalars.items()]
    df_scalars = pd.DataFrame(scalar_rows).sort_values("name") if scalar_rows else pd.DataFrame(columns=["name", "value"])

    params: dict[str, Any] = {}
    if run_parameters is not None:
        rp = _to_builtin(run_parameters)
        if isinstance(rp, Mapping):
            params.update(rp)
        else:
            params["run_parameters"] = str(rp)
    if extra_parameters:
        ep = _to_builtin(extra_parameters)
        if isinstance(ep, Mapping):
            params.update(ep)
        else:
            params["extra_parameters"] = str(ep)

    flat_params = _flatten_dict(params)
    df_params = pd.DataFrame([{"name": k, "value": v} for k, v in flat_params.items()]).sort_values("name") if flat_params else pd.DataFrame(columns=["name", "value"])

    df_notes = pd.DataFrame([{"note": n} for n in results.notes]) if results.notes else pd.DataFrame(columns=["note"])

    def sname(base_name: str) -> str:
        return f"{sheet_prefix}{base_name}" if sheet_prefix else base_name

    with pd.ExcelWriter(filepath, engine="openpyxl") as w:
        df_stations.to_excel(w, index=False, sheet_name=sname("stations"))
        df_scalars.to_excel(w, index=False, sheet_name=sname("scalars"))
        df_params.to_excel(w, index=False, sheet_name=sname("parameters"))
        if not df_notes.empty:
            df_notes.to_excel(w, index=False, sheet_name=sname("notes"))

    return filepath
