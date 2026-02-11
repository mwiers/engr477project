from __future__ import annotations

from dataclasses import is_dataclass, replace
from typing import Any, Callable, Iterable, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from results_container import Results


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
        raise TypeError(f"Unsupported params object type: {type(obj)}")

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

    raise TypeError(f"Unsupported params object type: {type(obj)}")


# ----------------------------
# Helpers: reading outputs
# ----------------------------

def get_metric(results: Results, metric: str) -> float:
    """
    Extract a dependent variable from Results.

    Metric options:
    - Scalar: "F_net_N" or any key in results.scalars
    - Station field: "stations.<station>.<field>", e.g.
        "stations.4.T0"
        "stations.7.p0"
        "stations.a.M"

    Fields available in a station are whatever exists on FluidState:
      m_dot, T, p, M, T0, p0, cp, gamma, R, composition, etc.
    """
    if metric.startswith("stations."):
        parts = metric.split(".")
        if len(parts) != 3:
            raise ValueError(
                "Station metric must be 'stations.<station>.<field>', e.g. 'stations.4.T0'"
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

EngineFactory = Callable[[Any], Any]  # takes params -> engine instance with .run(...)
RunFunction = Callable[[Any], Results]  # takes engine -> Results


class SensitivityAnalyzer:
    """
    Generic sensitivity analysis wrapper.

    You provide:
    - base_params: typically EngineDesign (dataclass)
    - engine_factory(params) -> engine instance (e.g., TurbofanEngine)
    - run_engine(engine) -> Results (usually lambda e: e.run(ambient, afterburn=...))

    Then you can run:
    - sweep_1d(...)
    - sweep_2d(...)
    """

    def __init__(
        self,
        base_params: Any,
        engine_factory: EngineFactory,
        run_engine: RunFunction,
    ) -> None:
        self.base_params = base_params
        self.engine_factory = engine_factory
        self.run_engine = run_engine

    def _eval(self, params: Any, metric: str) -> float:
        eng = self.engine_factory(params)
        res = self.run_engine(eng)
        return get_metric(res, metric)

    def sweep_1d(
        self,
        param: str,
        values: Iterable[float],
        metric: str,
        *,
        keep_runs: bool = False,
    ) -> tuple[pd.DataFrame, Optional[list[Results]]]:
        """
        Sweep one parameter -> DataFrame with columns [param, metric].
        """
        vals = list(values)
        ys: list[float] = []
        runs: list[Results] = []

        for v in vals:
            p = _set_by_path(self.base_params, param, v)
            eng = self.engine_factory(p)
            res = self.run_engine(eng)
            ys.append(get_metric(res, metric))
            if keep_runs:
                runs.append(res)

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
        Sweep two parameters -> (long-form DataFrame, grid array, optional runs)

        - grid shape: (len(values_y), len(values_x)) so rows correspond to Y, cols to X.
        """
        xs = list(values_x)
        ys = list(values_y)

        grid = np.empty((len(ys), len(xs)), dtype=float)
        runs_grid: list[list[Results]] = [[None for _ in xs] for _ in ys]  # type: ignore

        records = []
        for j, yv in enumerate(ys):
            for i, xv in enumerate(xs):
                p = _set_by_path(self.base_params, param_x, xv)
                p = _set_by_path(p, param_y, yv)

                eng = self.engine_factory(p)
                res = self.run_engine(eng)
                z = get_metric(res, metric)

                grid[j, i] = z
                records.append({param_x: xv, param_y: yv, metric: z})

                if keep_runs:
                    runs_grid[j][i] = res

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


def plot_2d_heatmap(
    grid: np.ndarray,
    x_values: Iterable[float],
    y_values: Iterable[float],
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    cbar_label: str | None = None,
    savepath: str | None = None,
):
    """
    2D heatmap using imshow with matplotlib defaults.
    Rows correspond to y_values, columns to x_values.
    """
    xs = np.asarray(list(x_values), dtype=float)
    ys = np.asarray(list(y_values), dtype=float)

    fig, ax = plt.subplots()

    # extent ensures axes show actual parameter values
    extent = [xs.min(), xs.max(), ys.min(), ys.max()]
    im = ax.imshow(
        grid,
        origin="lower",
        aspect="auto",
        extent=extent,
        interpolation="nearest",
    )
    ax.set_xlabel(xlabel or "x")
    ax.set_ylabel(ylabel or "y")
    if title:
        ax.set_title(title)

    cbar = fig.colorbar(im, ax=ax)
    if cbar_label:
        cbar.set_label(cbar_label)

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
