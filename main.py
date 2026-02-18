from __future__ import annotations
import os
import numpy as np

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

def build_f135_engine() -> TurbofanEngine:
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
        TAB=2450.0,
        ab_pr=0.95,
        eta_ab=0.99,
        nozzle_eta=0.97,
        throat_d=0.92,
        exit_d=1.15,
    )

    air = FluidModel(R=287.05287, composition="air", cp_mode="poly")
    products = FluidModel(R=287.05287, composition="products", cp_mode="poly")
    engine = TurbofanEngine(design=d, air_model=air, products_model=products, afterburner=ab)
    _ = print("F135 Engine Successfully Built") if VERBOSE else None
    return engine

def dry_solve(eng: TurbofanEngine, amb: Ambient):
    outdir = "./data/dry_solve"
    os.makedirs(outdir, exist_ok=True)
    dry = eng.run(
        amb, 
        afterburn=False,
        mdot_mode="auto")
    print("Dry net thrust:", dry.scalars["F_net_N"])

    dump_results_to_excel(
        dry,
        os.path.join(outdir, "run_dry.xlsx"),
        run_parameters=eng.d,
        extra_parameters={"ambient": amb},
        baseline_station="2",
    )

    ts = TSDiagram()
    ts.plot(dry, savepath=os.path.join(outdir, "ts_dry.png"))

    _ = print("Dry Solve Complete") if VERBOSE else None
    return dry

def wet_solve(eng: TurbofanEngine, amb: Ambient):
    outdir = "./data/wet_solve"
    os.makedirs(outdir, exist_ok=True)

    wet = eng.run(
        amb, 
        afterburn=True,
        mdot_mode="auto")
    print("Wet net thrust:", wet.scalars["F_net_N"])

    dump_results_to_excel(
        wet,
        os.path.join(outdir, "run_ab.xlsx"),
        run_parameters=eng.d,
        extra_parameters={"ambient": amb, "afterburn": eng.afterburner},
        baseline_station="2",
    )

    ts = TSDiagram()
    ts.plot(wet, title="T–s Diagram (Afterburn)", savepath=os.path.join(outdir, "ts_ab.png"))
    
    _ = print("Wet Solve Complete") if VERBOSE else None
    return wet

def parametric_analysis(
    eng: TurbofanEngine,
    amb: Ambient,
    *,
    metric: str,
    range1: np.ndarray,
    range2: np.ndarray | None = None,
    param1: str | None = None,
    param2: str | None = None,
) -> None:
    """
    Run ONE job:
      - If range2 is None: 1D sweep of (param1 over range1) for a given metric
      - If range2 is provided: 2D sweep of (param1 over range1) and (param2 over range2)

    Saves:
      - Excel table of results
      - 1D line plot OR 2D contour heatmap (contourf)

    Notes:
      - Forces dry mode (afterburner disabled) for Section 3.2.
      - Uses existing SensitivityAnalyzer + plotting utilities from tools/sensitivity.py.
    """
    # Output folder for this metric
    metric_dir = os.path.join("./data/parametric_analysis", metric)
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
        run_engine=lambda e, a: e.run(a, afterburn=True, mdot_mode="auto"),
    )
    _ = print(f"Starting Parametric Analysis for {metric} with axis {param1} and {param2}") if VERBOSE else None


    if range2 is None:
        # -------------------------
        # 1D sweep
        # -------------------------
        df, _ = sa.sweep_1d(param1, range1, metric)

        x_min, x_max = float(np.min(range1)), float(np.max(range1))
        tag = f"1D_{param1}_{x_min:g}_to_{x_max:g}"

        save_sweep_to_excel(
            df,
            os.path.join(metric_dir, f"{tag}_{metric}.xlsx"),
            metadata={
                "mode": "dry",
                "metric": metric,
                "param": param1,
                "range_min": x_min,
                "range_max": x_max,
                "ambient": str(amb),
            },
        )

        plot_1d(
            df,
            x_col=param1,
            y_col=metric,
            title=f"Dry sweep: {metric} vs {param1}",
            xlabel=param1,
            ylabel=metric,
            savepath=os.path.join(metric_dir, f"{tag}_{metric}.png"),
        )
        _ = print(f"1D sweep complete for {metric} over {param1}") if VERBOSE else None
        return

    # -------------------------
    # 2D sweep
    # -------------------------
    df2, grid, _ = sa.sweep_2d(param1, range1, param2, range2, metric)

    x_min, x_max = float(np.min(range1)), float(np.max(range1))
    y_min, y_max = float(np.min(range2)), float(np.max(range2))
    tag = f"2D_{param1}_{x_min:g}_to_{x_max:g}__{param2}_{y_min:g}_to_{y_max:g}"

    save_sweep_to_excel(
        df2,
        os.path.join(metric_dir, f"{tag}_{metric}.xlsx"),
        metadata={
            "mode": "dry",
            "metric": metric,
            "param_x": param1,
            "param_y": param2,
            "x_range_min": x_min,
            "x_range_max": x_max,
            "y_range_min": y_min,
            "y_range_max": y_max,
            "ambient": str(amb),
        },
    )

    plot_2d_heatmap(
        grid,
        x_values=range1,
        y_values=range2,
        title=f"Dry map: {metric} over {param1} and {param2}",
        xlabel=param1,
        ylabel=param2,
        cbar_label=metric,
        savepath=os.path.join(metric_dir, f"{tag}_{metric}.png"),
    )
    _ = print(f"2D sweep complete for {metric} with axis {param1} and {param2}") if VERBOSE else None

    return




def main():
    eng = build_f135_engine()
    amb = Ambient(T=288.15, p=101_325.0, M=0.0)

    # ------------------ 3.1: Static operation -------------------------
    # 3.1.1: Dry solve
    dry = dry_solve(eng, amb)

    # 3.1.2: Wet solve 
    wet = wet_solve(eng, amb)

    # ---------------- 3.2: Dry Parametric Analysis -------------------
    eng.afterburner.enabled = False
    amb.M = 0.85  # Restore Mach for parametric sweeps

    BPR_range = np.linspace(0.0, 1.5, 16)
    TIT_range = np.linspace(1750.0, 2250.0, 11)
    hpcPR_range = np.linspace(10.0, 15.0, 11)
    
    # Exploring the effects of Mach Number:
    mach_range = np.linspace(0.0, 1.5, 16)  # NOTE: Choking occurs at Mach 0.5

    """ # <- ADD A COMMENT HERE TO ENABLE THE SWEEPS, SINCE THEY TAKE A WHILE TO RUN
    parametric_analysis(
        eng, amb,
        metric="ST_Ns_per_kg",
        range1=mach_range, param1="ambient.M"
    )
    parametric_analysis(
        eng, amb,
        metric="TSFC_kg_per_Ns",
        range1=mach_range, param1="ambient.M"
    )
    parametric_analysis(
        eng, amb,
        metric="thermal_efficiency",
        range1=mach_range, param1="ambient.M"
    )
    parametric_analysis(
        eng, amb,
        metric="propulsive_efficiency",
        range1=mach_range, param1="ambient.M"
    )
    parametric_analysis(
        eng, amb,
        metric="overall_efficiency",
        range1=mach_range, param1="ambient.M"
    )
    # """

    """ # <- ADD A COMMENT HERE TO ENABLE THE SWEEPS, SINCE THEY TAKE A WHILE TO RUN
    # 3.2.1: Specific Thrust
    parametric_analysis(
        eng, amb,
        metric="ST_Ns_per_kg",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric="ST_Ns_per_kg",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric="ST_Ns_per_kg",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )

    # 3.2.2: TSFC
    parametric_analysis(
        eng, amb,
        metric="TSFC_kg_per_Ns",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric="TSFC_kg_per_Ns",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric="TSFC_kg_per_Ns",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )

    # 3.2.3: Efficiency 
    parametric_analysis(
        eng, amb,
        metric="thermal_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric="thermal_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric="thermal_efficiency",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )
    # ------
    parametric_analysis(
        eng, amb,
        metric="propulsive_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric="propulsive_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric="propulsive_efficiency",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )
    # ------
    parametric_analysis(
        eng, amb,
        metric="overall_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=hpcPR_range, param2="hpc_pr",
    )
    parametric_analysis(
        eng, amb,
        metric="overall_efficiency",
        range1=BPR_range, param1="bypass_ratio",
        range2=TIT_range, param2="TIT",
    )
    parametric_analysis(
        eng, amb,
        metric="overall_efficiency",
        range1=hpcPR_range, param1="hpc_pr",
        range2=TIT_range, param2="TIT",
    )
    # """

    # 3.2.4: Emmissions -> IMPLEMENT WITH NASA CEA
    


if __name__ == "__main__":
    main()
