import numpy as np
from tools.sensitivity import SensitivityAnalyzer, plot_1d, plot_2d_contour, save_sweep_to_excel
from engine import Ambient, TurbofanEngine
from main import build_f135_engine

eng = build_f135_engine()
amb = Ambient(T=288.15, p=101_325.0, M=0.0)

an = SensitivityAnalyzer(
    base_params=eng.d,
    engine_factory=lambda params: TurbofanEngine(params, eng.air, eng.products),
    run_engine=lambda e: e.run(amb),
)

Tt4_vals = np.linspace(1750, 2200, 10)
df, _ = an.sweep_1d("Tt4", Tt4_vals, "F_net_N")

plot_1d(df, "Tt4", "F_net_N", title="Sensitivity: Net Thrust vs Tt4", savepath="./data/thrust_vs_Tt4.png")
save_sweep_to_excel(df, "./data/thrust_vs_Tt4.xlsx", metadata={"ambient": "SLS", "metric": "F_net_N"})

# ----------------------------------------------------------------------------

import numpy as np
from tools.sensitivity import SensitivityAnalyzer, plot_2d_heatmap, save_sweep_to_excel
from engine import Ambient

eng = build_f135_engine()
amb = Ambient(T=288.15, p=101_325.0, M=0.0)

an = SensitivityAnalyzer(
    base_params=eng.d,
    engine_factory=lambda params: TurbofanEngine(params, eng.air, eng.products),
    run_engine=lambda e: e.run(amb),
)

fan_pr = np.linspace(1.4, 2.0, 13)
bpr = np.linspace(0.2, 1.2, 11)

df, grid, _ = an.sweep_2d("fan_pr", fan_pr, "bypass_ratio", bpr, "TSFC_kg_per_Ns")

plot_2d_heatmap(
    grid,
    x_values=fan_pr,
    y_values=bpr,
    xlabel="fan_pr",
    ylabel="bypass_ratio",
    cbar_label="TSFC_kg/(N·s)",
    title="TSFC Sensitivity Heatmap",
    savepath="./data/tsfc_heatmap.png",
)
save_sweep_to_excel(df, "./data/tsfc_heatmap.xlsx", metadata={"ambient": "SLS", "metric": "TSFC_kg_per_Ns"})


