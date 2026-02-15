from __future__ import annotations

from engine import Ambient, AfterburnDesign, EngineDesign, TurbofanEngine
from fluid_properties import FluidModel
from tools.state_dump import dump_results_to_excel
from tools.ts_diagram import TSDiagram


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

    air = FluidModel(R=287.05287, composition="air", cp_mode="poly")
    products = FluidModel(R=287.05287, composition="products", cp_mode="poly")
    return TurbofanEngine(design=d, air_model=air, products_model=products)


def main():
    eng = build_f135_engine()
    amb = Ambient(T=288.15, p=101_325.0, M=0.0)

    dry = eng.run(amb)
    print("Dry thrust:", dry.scalars["F_net_N"])

    dump_results_to_excel(
        dry,
        "./data/run_dry.xlsx",
        run_parameters=eng.d,
        extra_parameters={"ambient": amb},
        baseline_station="2",
    )

    ts = TSDiagram()
    ts.plot(dry, savepath="./data/ts_dry.png")

    ab = AfterburnDesign(
        enabled=True,
        TAB=2450.0,
        ab_pr=0.95,
        eta_ab=0.99,
        nozzle_eta=0.97,
        throat_d=0.92,
        exit_d=1.15,
    )
    wet = eng.run(amb, afterburn=ab)
    print("Wet thrust:", wet.scalars["F_net_N"])

    dump_results_to_excel(
        wet,
        "./data/run_ab.xlsx",
        run_parameters=eng.d,
        extra_parameters={"ambient": amb, "afterburn": ab},
        baseline_station="2",
    )
    ts.plot(wet, title="T–s Diagram (Afterburn)", savepath="./data/ts_ab.png")


if __name__ == "__main__":
    main()
