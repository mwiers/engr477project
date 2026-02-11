from __future__ import annotations

from dataclasses import is_dataclass, asdict
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from results_container import Results


def _to_builtin(obj: Any) -> Any:
    """
    Convert common objects (dataclasses, dicts, lists, tuples) to builtin Python types.
    Leaves primitives as-is.
    """
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Mapping):
        return {str(k): _to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_builtin(v) for v in obj]
    return obj


def _flatten_dict(d: Mapping[str, Any], prefix: str = "", sep: str = ".") -> dict[str, Any]:
    """
    Flatten nested dictionaries:
        {"a": {"b": 1}} -> {"a.b": 1}
    Lists/tuples are stringified (so the sheet stays tabular).
    """
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
    sheet_prefix: str = "",
) -> Path:
    """
    Dump Results (stations + scalars) and run/design parameters to an Excel file.

    This is intentionally configuration-agnostic:
    - It does not assume any particular engine architecture.
    - It dumps whatever stations/scalars are present.
    - It stores any run_parameters you pass (dataclass/dict/etc.), plus optional extras.

    Args:
        results: Results object from an engine run.
        filepath: Path to write .xlsx
        run_parameters: Typically EngineDesign or a dict containing design inputs.
        extra_parameters: Additional info (Ambient, notes, solver settings, etc.).
        sheet_prefix: Optional prefix to add to sheet names if you want to store multiple runs in one workbook.

    Sheets created:
        - "{prefix}stations"
        - "{prefix}scalars"
        - "{prefix}parameters"
        - "{prefix}notes" (if any)
    """
    filepath = Path(filepath)

    # ---- Stations table (one row per station key) ----
    station_rows: list[dict[str, Any]] = []
    for station_name, st in results.stations.items():
        row = {
            "station": station_name,
            "m_dot": getattr(st, "m_dot", None),
            "T": getattr(st, "T", None),
            "p": getattr(st, "p", None),
            "M": getattr(st, "M", None),
            "T0": getattr(st, "T0", None),
            "p0": getattr(st, "p0", None),
            "cp": getattr(st, "cp", None),
            "gamma": getattr(st, "gamma", None),
            "R": getattr(st, "R", None),
            "composition": getattr(st, "composition", None),
            "model": type(getattr(st, "model", None)).__name__ if getattr(st, "model", None) is not None else None,
        }
        station_rows.append(row)

    df_stations = pd.DataFrame(station_rows)
    if not df_stations.empty:
        df_stations = df_stations.sort_values("station")

    # ---- Scalars table ----
    scalar_rows = [{"name": k, "value": v} for k, v in results.scalars.items()]
    df_scalars = pd.DataFrame(scalar_rows).sort_values("name") if scalar_rows else pd.DataFrame(columns=["name", "value"])

    # ---- Parameters table (flattened key/value) ----
    params: dict[str, Any] = {}
    if run_parameters is not None:
        rp = _to_builtin(run_parameters)
        if isinstance(rp, Mapping):
            params.update(rp)
        else:
            # Allow arbitrary object; store as string
            params["run_parameters"] = str(rp)

    if extra_parameters:
        ep = _to_builtin(extra_parameters)
        if isinstance(ep, Mapping):
            params.update(ep)
        else:
            params["extra_parameters"] = str(ep)

    flat_params = _flatten_dict(params)
    df_params = pd.DataFrame(
        [{"name": k, "value": v} for k, v in flat_params.items()]
    ).sort_values("name") if flat_params else pd.DataFrame(columns=["name", "value"])

    # ---- Notes table ----
    df_notes = pd.DataFrame([{"note": n} for n in results.notes]) if results.notes else pd.DataFrame(columns=["note"])

    # ---- Write workbook ----
    def sname(base: str) -> str:
        return f"{sheet_prefix}{base}" if sheet_prefix else base

    with pd.ExcelWriter(filepath, engine="openpyxl") as w:
        df_stations.to_excel(w, index=False, sheet_name=sname("stations"))
        df_scalars.to_excel(w, index=False, sheet_name=sname("scalars"))
        df_params.to_excel(w, index=False, sheet_name=sname("parameters"))
        if not df_notes.empty:
            df_notes.to_excel(w, index=False, sheet_name=sname("notes"))

    return filepath
