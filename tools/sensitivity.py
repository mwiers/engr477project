from __future__ import annotations

from dataclasses import is_dataclass, replace
from typing import Any, Callable, Iterable, Optional, Tuple
import inspect

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from results_container import Results

from enginelogging import VERBOSE, ProgressBar

# ----------------------------
# Helpers: setting parameters
# ----------------------------

def _set_by_path(obj: Any, path: str, value: Any) -> Any:
    """
    Return a modified copy of a dataclass or dict-like object with `path` set to `value`.

    Supported:
    - Dataclasses (preferred): uses dataclasses.replace recursively.
    - Dicts: shallow / nested dict set.

    Path syntax:
      "fan_pr"
      "nozzle.exit_d"   (if your params are nested dataclasses/dicts)
    """
    parts = path.split(".")
    if len(parts) == 1:
        key = parts[0]
        if is_dataclass(obj):
            return replace(obj, **{key: value})
        if isinstance(obj, dict):
            new = dict(obj)
            new[key] = value
            return new
        raise TypeError(f"Unsupported object type for _set_by_path: {type(obj)}")

    head, tail = parts[0], ".".join(parts[1:])

    if is_dataclass(obj):
        current = getattr(obj, head)
        updated = _set_by_path(current, tail, value)
        return replace(obj, **{head: updated})

    if isinstance(obj, dict):
        new = dict(obj)
        child = new.get(head, {})
        new[head] = _set_by_path(child, tail, value)
        return new

    raise TypeError(f"Unsupported object type for _set_by_path: {type(obj)}")


def _split_target_path(path: str) -> Tuple[str, str]:
    """
    Returns (target, subpath)
      target: "params" or "ambient"
      subpath: path without "ambient." prefix if applicable
    """
    if path.startswith("ambient."):
        return "ambient", path[len("ambient.") :]
    return "params", path


# ----------------------------
# Helpers: reading outputs
# ----------------------------

def get_metric(results: Results, metric: str) -> float:
    """
    Extract a dependent variable from Results.

    Metric options:
    - Scalar: any key in results.scalars, e.g. "F_net_N", "TSFC_kg_per_Ns"
    - Station field: "stations.<station>.<field>", e.g.
        "stations.4.Tt"
        "stations.7.Pt"
        "stations.1.M"
    """
    if metric.startswith("stations."):
        parts = metric.split(".")
        if len(parts) != 3:
            raise ValueError(
                "Station metric must be 'stations.<station>.<field>', e.g. 'stations.4.Tt'"
            )
        _, station, field = parts
        if station not in results.stations:
            raise KeyError(f"Station '{station}' not found. Available: {list(results.stations.keys())}")
        st = results.stations[station]
        if not hasattr(st, field):
            raise KeyError(f"Field '{field}' not found on FluidState at station '{station}'.")
        val = getattr(st, field)
        if val is None:
            raise ValueError(f"Metric '{metric}' is None (station field not computed).")
        return float(val)

    if metric not in results.scalars:
        raise KeyError(f"Scalar '{metric}' not found. Available: {list(results.scalars.keys())}")
    return float(results.scalars[metric])


# ----------------------------
# Sensitivity runner
# ----------------------------

EngineFactory = Callable[[Any], Any]              # params -> engine instance
RunFunction1 = Callable[[Any], Results]           # run_engine(engine) -> Results
RunFunction2 = Callable[[Any, Any], Results]      # run_engine(engine, ambient) -> Results


class SensitivityAnalyzer:
    """
    Generic sensitivity analysis wrapper with optional ambient sweeps.

    You provide:
    - base_params: typically EngineDesign (dataclass)
    - engine_factory(params) -> engine instance (e.g., TurbofanEngine)
    - run_engine(engine) -> Results    OR    run_engine(engine, ambient) -> Results
    - base_ambient: an Ambient-like dataclass/dict (optional but required for ambient sweeps)

    Parameter path rules:
    - Paths like "bypass_ratio" or "hpc_pr" modify base_params.
    - Paths like "ambient.M" or "ambient.T" modify base_ambient.

    Then you can run:
    - sweep_1d(...)
    - sweep_2d(...)
    """

    def __init__(
        self,
        base_params: Any,
        engine_factory: EngineFactory,
        run_engine: RunFunction1 | RunFunction2,
        *,
        base_ambient: Any | None = None,
    ) -> None:
        self.base_params = base_params
        self.engine_factory = engine_factory
        self.run_engine = run_engine
        self.base_ambient = base_ambient

        # Detect whether run_engine expects (engine) or (engine, ambient)
        sig = inspect.signature(run_engine)
        self._run_takes_ambient = (len(sig.parameters) >= 2)

    def _run(self, eng: Any, ambient: Any | None) -> Results:
        if self._run_takes_ambient:
            if ambient is None:
                raise ValueError("run_engine expects ambient, but base_ambient/ambient was not provided.")
            return self.run_engine(eng, ambient)  # type: ignore[misc]
        return self.run_engine(eng)  # type: ignore[misc]

    def _eval(self, params: Any, ambient: Any | None, metric: str) -> float:
        eng = self.engine_factory(params)
        res = self._run(eng, ambient)
        return get_metric(res, metric)

    def _apply_change(self, params: Any, ambient: Any | None, path: str, value: Any) -> tuple[Any, Any | None]:
        target, subpath = _split_target_path(path)
        if target == "params":
            return _set_by_path(params, subpath, value), ambient
        # ambient
        if ambient is None:
            raise ValueError(
                f"Attempted to set '{path}' but no base_ambient was provided to SensitivityAnalyzer."
            )
        return params, _set_by_path(ambient, subpath, value)

    def sweep_1d(
        self,
        param: str,
        values: Iterable[float],
        metric: str,
        *,
        keep_runs: bool = False,
    ) -> tuple[pd.DataFrame, Optional[list[Results]]]:
        """
        Sweep one parameter (design or ambient) -> DataFrame with columns [param, metric].

        Examples:
          sweep_1d("bypass_ratio", np.linspace(0,1.5,16), "ST_Ns_per_kg")
          sweep_1d("ambient.M", np.linspace(0,1.2,13), "F_net_N")
        """
        vals = list(values)
        ys: list[float] = []
        runs: list[Results] = []

        n = len(vals)
        progress = ProgressBar(n)
        for i, v in enumerate(vals):
            p0 = self.base_params
            a0 = self.base_ambient
            p, a = self._apply_change(p0, a0, param, v)

            eng = self.engine_factory(p)
            res = self._run(eng, a)
            ys.append(get_metric(res, metric))
            if keep_runs:
                runs.append(res)
            if VERBOSE:
                progress.update()
            

        df = pd.DataFrame({param: vals, metric: ys})
        return df, (runs if keep_runs else None)

    def sweep_2d(
        self,
        param_x: str,
        values_x: Iterable[float],
        param_y: str,
        values_y: Iterable[float],
        metric: str,
        *,
        keep_runs: bool = False,
    ) -> tuple[pd.DataFrame, np.ndarray, Optional[list[list[Results]]]]:
        """
        Sweep two parameters (design and/or ambient) -> (long-form DataFrame, grid array, optional runs)

        - grid shape: (len(values_y), len(values_x)) so rows correspond to Y, cols to X.
        - param_x and param_y can be any combination of design/ambient paths.
        """
        xs = list(values_x)
        ys = list(values_y)

        grid = np.empty((len(ys), len(xs)), dtype=float)
        runs_grid: list[list[Results]] = [[None for _ in xs] for _ in ys]  # type: ignore

        n = len(xs) * len(ys)
        progress = ProgressBar(n)
        records = []
        for j, yv in enumerate(ys):
            for i, xv in enumerate(xs):
                p0 = self.base_params
                a0 = self.base_ambient

                p, a = self._apply_change(p0, a0, param_x, xv)
                p, a = self._apply_change(p, a, param_y, yv)

                eng = self.engine_factory(p)
                res = self._run(eng, a)
                z = get_metric(res, metric)

                grid[j, i] = z
                records.append({param_x: xv, param_y: yv, metric: z})

                if keep_runs:
                    runs_grid[j][i] = res
                
                if VERBOSE:
                    progress.update()

        df = pd.DataFrame.from_records(records)
        return df, grid, (runs_grid if keep_runs else None)


# ----------------------------
# Plotting utilities
# ----------------------------

def plot_1d(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    savepath: str | None = None,
):
    """
    1D line plot. Uses matplotlib defaults (no explicit colors).
    """
    fig, ax = plt.subplots()
    ax.plot(df[x_col].to_numpy(), df[y_col].to_numpy())
    ax.set_xlabel(xlabel or x_col)
    ax.set_ylabel(ylabel or y_col)
    ax.grid(True)
    if title:
        ax.set_title(title)
    if savepath:
        fig.savefig(savepath, dpi=200, bbox_inches="tight")
    return fig, ax


def save_sweep_to_excel(
    df: pd.DataFrame,
    filepath: str,
    *,
    sheet_name: str = "sweep",
    metadata: dict[str, Any] | None = None,
) -> str:
    """
    Save sweep results to Excel. Optionally include metadata on a second sheet.
    """
    with pd.ExcelWriter(filepath, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=sheet_name)
        if metadata:
            meta_df = pd.DataFrame([{"name": k, "value": v} for k, v in metadata.items()])
            meta_df.to_excel(w, index=False, sheet_name="metadata")
    return filepath


def plot_2d_heatmap(
    grid: np.ndarray,
    x_values: Iterable[float],
    y_values: Iterable[float],
    *,
    levels: int = 30,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    cbar_label: str | None = None,
    savepath: str | None = None,
):
    """
    Smooth filled contour plot using matplotlib contourf.
    """
    xs = np.asarray(list(x_values), dtype=float)
    ys = np.asarray(list(y_values), dtype=float)

    X, Y = np.meshgrid(xs, ys)

    fig, ax = plt.subplots()
    contour = ax.contourf(X, Y, grid, levels=levels)

    ax.set_xlabel(xlabel or "x")
    ax.set_ylabel(ylabel or "y")

    if title:
        ax.set_title(title)

    cbar = fig.colorbar(contour, ax=ax)
    if cbar_label:
        cbar.set_label(cbar_label)

    if savepath:
        fig.savefig(savepath, dpi=200, bbox_inches="tight")

    return fig, ax
