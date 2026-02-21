from __future__ import annotations
import os
import numpy as np
from dataclasses import replace as dc_replace
from typing import Literal

from engine import Ambient, AfterburnDesign, EngineDesign, TurbofanEngine
from fluid_properties import FluidModel
from tools.sensitivity import (
    SensitivityAnalyzer,
    plot_1d,
    plot_2d_heatmap,
    save_sweep_to_excel,
)
from tools.state_dump import dump_results_to_excel
from tools.ts_diagram import TSDiagram

from enginelogging import VERBOSE

MDOT_MODE: Literal['fixed', 'auto'] = 'fixed'

def build_f135_engine(**kwargs) -> TurbofanEngine:
    d = EngineDesign(
        m_dot=150.0,
        bypass_ratio=0.57,
        fuel_LHV=43_150_000.0,
        diffuser_pr=0.99,
        fan_pr=1.75,
        bypass_duct_pr=0.96,
        lpc_pr=1.25,
        lpc_duct_pr=0.99,
        hpc_pr=12.8,
        hpc_duct_pr=0.99,
        burner_pr=0.94,
        mixer_pr=0.97,
        nozzle_pr=0.98,
        eta_fan=0.89,
        eta_lpc=0.88,
        eta_hpc=0.86,
        eta_burner=0.99,
        eta_hpt=0.89,
        eta_lpt=0.91,
        eta_mech=0.99,
        eta_nozzle=0.98,
        TIT=2000.0,
        nozzle_throat_d=0.78,
        nozzle_exit_d=0.78,
    )
    ab = AfterburnDesign(
        enabled=True,
        m_dot=165.0,
        TAB=2450.0,
        ab_pr=0.95,
        eta_ab=0.99,
        nozzle_eta=0.97,
        throat_d=0.92,
        exit_d=1.15,
    )

    air = FluidModel(R=287.05287, composition="air", cp_mode="poly")
    products = FluidModel(R=287.05287, composition="products", cp_mode="poly")

    if kwargs:
        d_fields = set(d.__dataclass_fields__)
        ab_fields = set(ab.__dataclass_fields__)
        air_fields = set(air.__dataclass_fields__)
        products_fields = set(products.__dataclass_fields__)

        air_updates: dict[str, object] = {}
        products_updates: dict[str, object] = {}

        key_counts: dict[str, int] = {}
        for field_set in (d_fields, ab_fields, air_fields, products_fields):
            for name in field_set:
                key_counts[name] = key_counts.get(name, 0) + 1

        for key, value in kwargs.items():
            prefix = None
            field = key
            if "__" in key:
                prefix, field = key.split("__", 1)
            elif "." in key:
                prefix, field = key.split(".", 1)

            if prefix is not None:
                p = prefix.lower()
                if p in ("d", "design", "engine"):
                    if field not in d_fields:
                        raise KeyError(f"Unknown EngineDesign field: {field}")
                    setattr(d, field, value)
                elif p in ("ab", "afterburn", "afterburner"):
                    if field not in ab_fields:
                        raise KeyError(f"Unknown AfterburnDesign field: {field}")
                    setattr(ab, field, value)
                elif p in ("air", "air_model"):
                    if field not in air_fields:
                        raise KeyError(f"Unknown air FluidModel field: {field}")
                    air_updates[field] = value
                elif p in ("products", "product", "products_model", "prod"):
                    if field not in products_fields:
                        raise KeyError(f"Unknown products FluidModel field: {field}")
                    products_updates[field] = value
                else:
                    raise KeyError(f"Unknown kwargs target prefix: {prefix}")
                continue

            present = (
                (field in d_fields)
                + (field in ab_fields)
                + (field in air_fields)
                + (field in products_fields)
            )
            if present == 0:
                raise KeyError(f"Unknown kwarg: {field}")
            if present > 1:
                raise KeyError(
                    f"Ambiguous kwarg '{field}'. Use a prefix: design__, ab__, air__, or products__."
                )

            if field in d_fields:
                setattr(d, field, value)
            elif field in ab_fields:
                setattr(ab, field, value)
            elif field in air_fields:
                air_updates[field] = value
            else:
                products_updates[field] = value

        if air_updates:
            air = dc_replace(air, **air_updates)
        if products_updates:
            products = dc_replace(products, **products_updates)

    engine = TurbofanEngine(design=d, air_model=air, products_model=products, afterburner=ab)
    _ = print("F135 Engine Successfully Built") if VERBOSE else None
    return engine

def dry_solve(eng: TurbofanEngine, amb: Ambient):
    outdir = "./data/dry_solve"
    os.makedirs(outdir, exist_ok=True)
    dry = eng.run(
        amb, 
        afterburn=False,
        mdot_mode=MDOT_MODE)
    print("Dry net thrust:", dry.scalars["F_net_N"])
    print("Dry specific thrust:", dry.scalars["ST_Ns_per_kg"])
    print("Dry TSFC:", dry.scalars["TSFC_kg_per_Ns"])

    # dump_results_to_excel(
    #     dry,
    #     os.path.join(outdir, "run_dry.xlsx"),
    #     run_parameters=eng.d,
    #     extra_parameters={"ambient": amb},
    #     baseline_station="2",
    # )

    # ts = TSDiagram()
    # ts.plot(dry, savepath=os.path.join(outdir, "ts_dry.png"))

    _ = print("Dry Solve Complete") if VERBOSE else None
    return dry

def wet_solve(eng: TurbofanEngine, amb: Ambient):
    outdir = "./data/wet_solve"
    os.makedirs(outdir, exist_ok=True)

    wet = eng.run(
        amb, 
        afterburn=True,
        mdot_mode=MDOT_MODE)
    print("Wet net thrust:", wet.scalars["F_net_N"])
    print("Wet specific thrust:", wet.scalars["ST_Ns_per_kg"])
    print("Wet TSFC:", wet.scalars["TSFC_kg_per_Ns"])

    # dump_results_to_excel(
    #     wet,
    #     os.path.join(outdir, "run_ab.xlsx"),
    #     run_parameters=eng.d,
    #     extra_parameters={"ambient": amb, "afterburn": eng.afterburner},
    #     baseline_station="2",
    # )

    # ts = TSDiagram()
    # ts.plot(wet, title="T–s Diagram (Afterburn)", savepath=os.path.join(outdir, "ts_ab.png"))
    
    _ = print("Wet Solve Complete") if VERBOSE else None
    return wet

def parametric_analysis(
    eng: TurbofanEngine,
    amb: Ambient,
    *,
    metric1: str | list[str],
    metric2: str | list[str] | None = None,
    range1: np.ndarray,
    range2: np.ndarray | None = None,
    param1: str | None = None,
    param2: str | None = None,
    tags: list[str] | str | None = None,
) -> None:
    """
    Run ONE job:
      - If range2 is None: 1D sweep of (param1 over range1) for one or more metrics.
          * metric1: str or list[str] plotted on LEFT axis
          * metric2: optional str or list[str] plotted on RIGHT axis
      - If range2 is provided: 2D sweep of (param1 over range1) and (param2 over range2)
          * Generates ONE heatmap per metric (for all metrics in metric1 + metric2)

    Saves:
      - Excel table of results
      - 1D line plot (with optional twin y-axis) OR 2D contour heatmap(s)

    Notes:
      - Uses existing SensitivityAnalyzer + plotting utilities from tools/sensitivity.py.
    """

    def _as_list(m: str | list[str] | None) -> list[str]:
        if m is None:
            return []
        return [m] if isinstance(m, str) else list(m)

    def _safe_name(s: str) -> str:
        # filesystem-safe-ish name
        bad = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']
        out = s
        for b in bad:
            out = out.replace(b, "_")
        return out

    metrics_left = _as_list(metric1)
    metrics_right = _as_list(metric2)
    all_metrics = metrics_left + metrics_right
    if len(all_metrics) == 0:
        raise ValueError("parametric_analysis: at least one metric must be provided in metric1 and/or metric2.")

    # Output folder: single metric keeps old behavior; multi-metric uses a combined folder
    if len(all_metrics) == 1:
        metric_dir = os.path.join("./data/parametric_analysis", _safe_name(all_metrics[0]))
    else:
        metric_dir = os.path.join("./data/parametric_analysis", _safe_name("MULTI__" + "__".join(all_metrics)))
    os.makedirs(metric_dir, exist_ok=True)

    # Build analyzer (pass base_ambient and allow run_engine(engine, ambient))
    sa = SensitivityAnalyzer(
        base_params=eng.d,
        base_ambient=amb,
        engine_factory=lambda params: TurbofanEngine(
            design=params,
            air_model=eng.air,
            products_model=eng.products,
            afterburner=eng.afterburner,
        ),
        run_engine=lambda e, a: e.run(a, afterburn=True, mdot_mode=MDOT_MODE),
    )

    _ = print(
        f"Starting Parametric Analysis for metrics={all_metrics} with axis {param1} and {param2}"
    ) if VERBOSE else None

    # Normalize tags
    tag_suffix = ""
    if tags is not None:
        if isinstance(tags, str):
            tags = [tags]
        for t in tags:
            tag_suffix += f"_{t}"

    if range2 is None:
        # -------------------------
        # 1D sweep (multi-metric supported)
        # -------------------------
        if param1 is None:
            raise ValueError("parametric_analysis (1D): param1 must be provided when range2 is None.")

        df = None
        for m in all_metrics:
            dfi, _ = sa.sweep_1d(param1, range1, m)
            if df is None:
                df = dfi
            else:
                # merge on the swept parameter column
                df = df.merge(dfi, on=param1, how="inner")

        assert df is not None

        x_min, x_max = float(np.min(range1)), float(np.max(range1))
        tag = f"1D_{_safe_name(param1)}_{x_min:g}_to_{x_max:g}{tag_suffix}"

        # Save combined Excel
        # save_sweep_to_excel(
        #     df,
        #     os.path.join(metric_dir, f"{tag}__{'__'.join(map(_safe_name, all_metrics))}.xlsx"),
        #     metadata={
        #         "mode": "dry",
        #         "metrics_left": ", ".join(metrics_left),
        #         "metrics_right": ", ".join(metrics_right) if metrics_right else "",
        #         "param": param1,
        #         "range_min": x_min,
        #         "range_max": x_max,
        #         "ambient": str(amb),
        #     },
        # )

        # Plot with optional right axis (implemented in tools/sensitivity.py via enhanced plot_1d)
        plot_1d(
            df,
            x_col=param1,
            y_col=metrics_left if len(metrics_left) > 1 else metrics_left[0],
            y2_col=(metrics_right if metrics_right else None),
            title=f"Sweep: ({', '.join(metrics_left)}) vs {param1}" + (f"  |  ({', '.join(metrics_right)})" if metrics_right else ""),
            xlabel=param1,
            ylabel=" / ".join(metrics_left) if metrics_left else None,
            y2label=" / ".join(metrics_right) if metrics_right else None,
            savepath=os.path.join(metric_dir, f"{tag}__{'__'.join(map(_safe_name, all_metrics))}.png"),
        )

        _ = print(f"1D sweep complete for metrics={all_metrics} over {param1}") if VERBOSE else None
        return

    # -------------------------
    # 2D sweep (one heatmap per metric)
    # -------------------------
    if param1 is None or param2 is None:
        raise ValueError("parametric_analysis (2D): param1 and param2 must be provided when range2 is not None.")

    x_min, x_max = float(np.min(range1)), float(np.max(range1))
    y_min, y_max = float(np.min(range2)), float(np.max(range2))
    base_tag = (
        f"2D_{_safe_name(param1)}_{x_min:g}_to_{x_max:g}__{_safe_name(param2)}_{y_min:g}_to_{y_max:g}{tag_suffix}"
    )

    for m in all_metrics:
        df2, grid, _ = sa.sweep_2d(param1, range1, param2, range2, m)

        # save_sweep_to_excel(
        #     df2,
        #     os.path.join(metric_dir, f"{base_tag}__{_safe_name(m)}.xlsx"),
        #     metadata={
        #         "mode": "dry",
        #         "metric": m,
        #         "param_x": param1,
        #         "param_y": param2,
        #         "x_range_min": x_min,
        #         "x_range_max": x_max,
        #         "y_range_min": y_min,
        #         "y_range_max": y_max,
        #         "ambient": str(amb),
        #     },
        # )

        plot_2d_heatmap(
            grid,
            x_values=range1,
            y_values=range2,
            title=f"Map: {m} over {param1} and {param2}",
            xlabel=param1,
            ylabel=param2,
            cbar_label=m,
            savepath=os.path.join(metric_dir, f"{base_tag}__{_safe_name(m)}.png"),
        )

    _ = print(
        f"2D sweep complete for metrics={all_metrics} with axis {param1} and {param2}"
    ) if VERBOSE else None
    return

def main():

    eng = build_f135_engine()
    amb = Ambient(T=288.15, p=101_325.0, M=0.0)

    # Exploring the effects of Mach Number:
    mach_range = np.linspace(0.0, 1.5, 40)  # NOTE: Choking occurs at Mach 0.5
    

    # ------------------ 3.1: Static operation -------------------------
    print('\n--------- Original Values: -----------')
    # 3.1.1: Dry solve --------------------------
    # """
    eng.afterburner.enabled = False
    dry = dry_solve(eng, amb)

    # parametric_analysis(
    #     eng, amb,
    #     metric1=["F_net_N"],
    #     metric2=["thermal_efficiency", "propulsive_efficiency", "overall_efficiency"],
    #     range1=mach_range, param1="ambient.M",
    #     tags="dry"
    # )

    # """

    # 3.1.2: Wet solve --------------------------
    # """ 
    eng.afterburner.enabled = True
    wet = wet_solve(eng, amb)

    # parametric_analysis(
    #     eng, amb,
    #     metric1=["F_net_N"],
    #     metric2=["thermal_efficiency", "propulsive_efficiency", "overall_efficiency"],
    #     range1=mach_range, param1="ambient.M",
    #     tags="wet"
    # )


    # """

    # ---------------- 3.2: Dry Parametric Analysis -------------------
    print('\n--------- Parametric Analysis: -----------')
    eng.afterburner.enabled = False
    amb.M = 0.85  # Restore Mach for parametric sweeps

    BPR_range = np.linspace(0.0, 1.5, 16)
    TIT_range = np.linspace(1750.0, 2250.0, 11)
    hpcPR_range = np.linspace(10.0, 15.0, 11)
    

    """ # <- ADD A COMMENT HERE TO ENABLE THE SWEEPS, SINCE THEY TAKE A WHILE TO RUN
    parametric_analysis(
        eng, amb,
        metric1="ST_Ns_per_kg",
        range1=mach_range, param1="ambient.M"
    )
    parametric_analysis(
        eng, amb,
        metric1="TSFC_kg_per_Ns",
        range1=mach_range, param1="ambient.M"
    )
    parametric_analysis(
        eng, amb,
        metric1="thermal_efficiency",
        range1=mach_range, param1="ambient.M"
    )
    parametric_analysis(
        eng, amb,
        metric1="propulsive_efficiency",
        range1=mach_range, param1="ambient.M"
    )
    parametric_analysis(
        eng, amb,
        metric1="overall_efficiency",
        range1=mach_range, param1="ambient.M"
    )
    # """

    """ # <- ADD A COMMENT HERE TO ENABLE THE SWEEPS, SINCE THEY TAKE A WHILE TO RUN
    # 3.2.1: Specific Thrust
    parametric_analysis(
        eng, amb,
        metric1="ST_Ns_per_kg",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric1="ST_Ns_per_kg",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric1="ST_Ns_per_kg",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )

    # 3.2.2: TSFC
    parametric_analysis(
        eng, amb,
        metric1="TSFC_kg_per_Ns",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric1="TSFC_kg_per_Ns",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric1="TSFC_kg_per_Ns",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )

    # 3.2.3: Efficiency 
    parametric_analysis(
        eng, amb,
        metric1="thermal_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric1="thermal_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric1="thermal_efficiency",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )
    # ------
    parametric_analysis(
        eng, amb,
        metric1="propulsive_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric1="propulsive_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric1="propulsive_efficiency",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )
    # ------
    parametric_analysis(
        eng, amb,
        metric1="overall_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric1="overall_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric1="overall_efficiency",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )
    # """

    # 3.2.4: Emmissions -> IMPLEMENT WITH NASA CEA --------------------------
    
    # 3.3: Maximum ST Operation Condition --------------------------
    print('\n--------- Optimized Values: -----------')
    amb = Ambient(T=288.15, p=101_325.0, M=0.0)
    eng_new = build_f135_engine(bypass_ratio=1.5, hpc_pr=15, TIT=2100)

    optimized_dry = dry_solve(eng_new, amb)
    optimized_wet = wet_solve(eng_new, amb)


    


if __name__ == "__main__":
    main()
