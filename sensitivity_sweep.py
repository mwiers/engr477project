from main import build_f135_engine
from engine import TurbofanEngine
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


# 
fan_pr = np.linspace(1.4, 2.0, 13)
bpr = np.linspace(0.2, 2.0, 11)

df, grid, _ = an.sweep_2d("fan_pr", fan_pr, "bypass_ratio", bpr, "F_net_N")

plot_2d_heatmap(
    grid,
    x_values=fan_pr,
    y_values=bpr,
    xlabel="fan_pr",
    ylabel="bypass_ratio",
    cbar_label="Thrust [N]",
    title="Thrust Sensitivity Heatmap",
    savepath="./data/thrust_heatmap.png",
)
save_sweep_to_excel(df, "./data/thrust_heatmap.xlsx", metadata={"ambient": "SLS", "metric": "F_net_N"})


