"""lab_analysis.analysis._base — 统计分析子包共享常量与工具"""

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from lab_analysis.utils import build_paths as build_paths_utils

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))


# ── 参考配置 ──────────────────────────────────────────────────────────

NUMERIC_METRICS = [
    "WBC", "RBC", "HGB", "HCT", "PLT", "PCT", "P-LCR",
    "MCV", "MCH", "MCHC",
    "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
    "NEUT#", "LYMPH#", "MONO#", "EO#", "BASO#",
    "RDW-SD", "RDW-CV", "MPV", "PDW",
    "CRP", "hs-CRP",
]

REF_RANGES = {
    "WBC": (3.5, 9.5),   "RBC": (4.3, 5.8),   "HGB": (130, 175),
    "HCT": (40, 50),      "PLT": (125, 350),   "PCT": (0.108, 0.272),
    "NEUT%": (40, 75),    "LYMPH%": (20, 50),  "MONO%": (2, 10),
    "EO%": (0.4, 8),      "BASO%": (0, 1),
    "NEUT#": (1.8, 6.3),  "LYMPH#": (1.1, 3.2),"MONO#": (0.1, 0.6),
    "RDW-SD": (37, 50),   "RDW-CV": (0, 15),   "CRP": (0, 10),
    "hs-CRP": (0, 1.0),
}

ACUTE_THRESHOLD    = 3.0
REMISSION_THRESHOLD = 1.0

INFLAMMATION_COLORS = {
    "急性期": "#e74c3c", "过渡期": "#f39c12",
    "缓解期": "#27ae60", "未知": "#95a5a6",
}


# ── 路径构建 ──────────────────────────────────────────────────────────

def build_paths(patient_id: str) -> dict:
    paths = build_paths_utils(patient_id)
    analyzed_dir = paths["data_dir"] / "02_analyzed"
    figures_dir = analyzed_dir / "figures"
    reports_dir = paths["data_dir"] / "04_reports"
    return {
        "data_dir": paths["data_dir"],
        "analyzed_dir": analyzed_dir,
        "figures_dir": figures_dir,
        "reports_dir": reports_dir,
        "metrics_csv": analyzed_dir / "lab_metrics.csv",
        "output_json": analyzed_dir / "analysis_results.json",
        "fig_trend":   figures_dir / "fig_01_trend_regression.png",
        "fig_corr":    figures_dir / "fig_02_correlation_heatmap.png",
        "fig_infl":    figures_dir / "fig_03_inflammation_status.png",
        "fig_abnorm":  figures_dir / "fig_04_abnormal_indicators.png",
        "fig_ma":      figures_dir / "fig_05_moving_average.png",
        "fig_cv":      figures_dir / "fig_06_cv_stability.png",
        "fig_zscore":  figures_dir / "fig_07_zscore_distribution.png",
        "report_md":   reports_dir / "analysis_results_report.md",
    }


# ── 绘图工具 ──────────────────────────────────────────────────────────

def setup_chinese():
    plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def save_fig(fig, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] 已保存: {path.name}")
