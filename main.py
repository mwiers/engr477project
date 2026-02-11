from __future__ import annotations

from engine import Ambient, AfterburnDesign, EngineDesign, TurbofanEngine
from fluid_properties import FluidModel

def build_f135_engine() -> TurbofanEngine:
    # From project spec Table 1 (dry):
    d = EngineDesign(
        m_dot=150.0,
        bypass_ratio=0.57,
        fuel_LHV=43_150_000.0,  # J/kg (43150 kJ/kg)
        inlet_pr=0.99,
        fan_pr=1.75,
        bypass_duct_pr=0.96,
        lpc_pr=1.25,
        lpc_duct_pr=0.99,
        hpc_pr=12.8,
        hpc_duct_pr=0.99,
        burner_pr=0.94,
        mixer_pr=0.97,
        nozzle_pr=0.98,
        eta_diffuser=0.99,
        eta_fan=0.89,
        eta_lpc=0.88,
        eta_hpc=0.86,
        eta_burner=0.99,
        eta_hpt=0.89,
        eta_lpt=0.91,
        eta_mech=0.99,
        eta_nozzle=0.98,
        Tt4=2000.0,
        M_inlet=0.5,
        M_turb_exit=0.5,
        nozzle_throat_d=0.78,
        nozzle_exit_d=0.78,
    )

    air = FluidModel(R=287.05287, composition="air", cp_mode="poly", cp_const=1004.5)
    products = FluidModel(R=287.05287, composition="products", cp_mode="poly", cp_const=1150.0)
    return TurbofanEngine(design=d, air_model=air, products_model=products)

def main():
    eng = build_f135_engine()

    # Design point: sea-level static
    amb = Ambient(T=288.15, p=101_325.0, M=0.0)

    dry = eng.run(amb)
    print("=== F135 Dry ===")
    print(f"Net thrust: {dry.scalars['F_net_N']:.0f} N")
    print(f"Specific thrust: {dry.scalars['ST_Ns_per_kg']:.2f} N·s/kg")
    print(f"TSFC: {dry.scalars['TSFC_kg_per_Ns']:.3e} kg/(N·s)")

    ab = AfterburnDesign(
        enabled=True,
        m_dot=165.0,
        Tt7=2450.0,
        ab_pr=0.95,
        eta_ab=0.99,
        nozzle_eta=0.97,
        throat_d=0.92,
        exit_d=1.15,
    )
    wet = eng.run(amb, afterburn=ab)
    print("\n=== F135 Afterburning ===")
    print(f"Net thrust: {wet.scalars['F_net_N']:.0f} N")
    print(f"Specific thrust: {wet.scalars['ST_Ns_per_kg']:.2f} N·s/kg")
    print(f"TSFC: {wet.scalars['TSFC_kg_per_Ns']:.3e} kg/(N·s)")

if __name__ == "__main__":
    main()
