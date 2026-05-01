#!/home/bb/wiki/.venv/bin/python
# -*- coding: utf-8 -*-
"""
data_analyzer.py
数据分析：对 lab_metrics.csv 进行统计分析和建模。
依赖：~/wiki/.venv/bin/python (pandas, numpy, scipy, scikit-learn)
"""

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path
from datetime import datetime

WIKI_ROOT = Path.home() / "wiki"
DATA_DIR = WIKI_ROOT / "data"
METRICS_CSV = DATA_DIR / "lab_metrics.csv"
OUTPUT_JSON = DATA_DIR / "analysis_results.json"

# 图表输出路径
FIG_TREND    = DATA_DIR / "fig_01_trend_regression.png"    # ① 趋势回归图
FIG_CORR     = DATA_DIR / "fig_02_correlation_heatmap.png" # ② 相关性热力图
FIG_INFLA    = DATA_DIR / "fig_03_inflammation_status.png"  # ③ 炎症分期图
FIG_ABNORMAL = DATA_DIR / "fig_04_abnormal_indicators.png"  # ④ 异常指标标注图

# 数值型指标
NUMERIC_METRICS = [
    "WBC", "RBC", "HGB", "HCT", "PLT", "PCT", "P-LCR",
    "MCV", "MCH", "MCHC",
    "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
    "NEUT#", "LYMPH#", "MONO#", "EO#", "BASO#",
    "RDW-SD", "RDW-CV", "MPV", "PDW",
    "CRP", "hs-CRP",
]

# 参考范围
REF_RANGES = {
    "WBC": (3.5, 9.5),   "RBC": (4.3, 5.8),   "HGB": (130, 175),
    "HCT": (40, 50),      "PLT": (125, 350),   "PCT": (0.108, 0.272),
    "NEUT%": (40, 75),    "LYMPH%": (20, 50),  "MONO%": (2, 10),
    "EO%": (0.4, 8),      "BASO%": (0, 1),
    "NEUT#": (1.8, 6.3),  "LYMPH#": (1.1, 3.2),"MONO#": (0.1, 0.6),
    "RDW-SD": (37, 50),   "RDW-CV": (0, 15),   "CRP": (0, 10),
    "hs-CRP": (0, 1.0),
}

# 炎症分类阈值
ACUTE_THRESHOLD    = 3.0   # hs-CRP > 3 → 急性期
REMISSION_THRESHOLD = 1.0  # hs-CRP < 1 → 缓解期

INFLAMMATION_COLORS = {"急性期": "#e74c3c", "过渡期": "#f39c12", "缓解期": "#27ae60", "未知": "#95a5a6"}

# ────────────────────────────────────────────────────────────────
# 绘图函数
# ────────────────────────────────────────────────────────────────

def _setup_chinese():
    """设置中文字体（使用系统安装的文泉驿正黑）"""
    plt.rcParams["font.family"] = ["WenQuanYi Zen Hei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def _save(fig, path: Path):
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✅ 已保存: {path.name}")


def plot_trend_regression(df: pd.DataFrame, results: dict):
    """① 趋势回归图：7个关键指标的时序折线 + 回归拟合线"""
    _setup_chinese()
    metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"]
    dates   = pd.to_datetime(df["report_date"])
    n       = len(metrics)
    cols    = 3
    rows    = (n + cols - 1) // cols

    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 3.5 * rows), facecolor="white")
    axes = axes.flatten() if n > 1 else [axes]

    linear_results = results.get("linear_regression", {})

    for i, metric in enumerate(metrics):
        ax = axes[i]
        if metric not in df.columns:
            ax.set_title(metric)
            ax.axis("off")
            continue

        series = df[metric].dropna()
        valid_dates = dates[df[metric].notna()]
        y_vals = series.values.astype(float)
        x_idx  = np.arange(len(y_vals))

        ax.plot(x_idx, y_vals, "o-", color="#3498db", linewidth=2, markersize=7, label="实测值")

        reg = linear_results.get(metric, {})
        if reg.get("slope") is not None and len(y_vals) >= 2:
            slope, intercept, r2 = reg["slope"], reg["intercept"], reg["r2"]
            x_line = np.array([x_idx.min(), x_idx.max()])
            y_line = slope * x_line + intercept
            ax.plot(x_line, y_line, "--", color="#e74c3c", linewidth=1.8,
                    label=f"拟合 R²={r2:.3f}")
            ax.text(0.05, 0.95, f"slope={slope:.4f}\ntrend={reg.get('trend','?')}",
                    transform=ax.transAxes, fontsize=7, va="top",
                    color="#2c3e50",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="#ecf0f1", alpha=0.7))

        ref = REF_RANGES.get(metric)
        if ref:
            low, high = ref
            ax.axhspan(low, high, alpha=0.15, color="green", label="参考范围")
            ax.axhline(low,  color="green", linewidth=0.8, linestyle=":")
            ax.axhline(high, color="green", linewidth=0.8, linestyle=":")

        ax.set_xticks(x_idx)
        ax.set_xticklabels([d.strftime("%m-%d") for d in valid_dates], fontsize=8)
        ax.set_title(f"{metric}", fontsize=11, fontweight="bold")
        ax.grid(True, alpha=0.3)
        if i == 0:
            ax.legend(fontsize=7, loc="upper right")

    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    fig.suptitle("关键指标趋势回归分析", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    _save(fig, FIG_TREND)


def plot_correlation_heatmap(df: pd.DataFrame):
    """② 相关性热力图：8个关键指标的 Pearson 相关系数"""
    _setup_chinese()
    metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "PCT", "PLT"]
    cols    = [m for m in metrics if m in df.columns]
    if len(cols) < 2:
        print("  ⚠️  相关性指标不足，跳过热力图")
        return

    sub  = df[cols].apply(pd.to_numeric, errors="coerce")
    corr = sub.corr(method="pearson")

    fig, ax = plt.subplots(figsize=(len(cols) + 1, len(cols)), facecolor="white")
    cmap = LinearSegmentedColormap.from_list("rb", ["#e74c3c", "#f8f8f8", "#27ae60"])

    im = ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1, aspect="auto")

    ax.set_xticks(range(len(cols)))
    ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right", fontsize=10)
    ax.set_yticklabels(cols, fontsize=10)

    for xi in range(len(cols)):
        for yi in range(len(cols)):
            val = corr.values[yi, xi]
            color = "white" if abs(val) > 0.5 else "black"
            ax.text(xi, yi, f"{val:.2f}", ha="center", va="center",
                    fontsize=9, color=color, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Pearson r", fontsize=10)

    fig.suptitle("指标相关性热力图", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    _save(fig, FIG_CORR)


def plot_inflammation_status(df: pd.DataFrame, results: dict):
    """③ 炎症分期柱状图：4次就诊的炎症状态颜色区分"""
    _setup_chinese()
    status_info = results.get("inflammation_classification", {})
    labels  = status_info.get("labels", [])
    dates_s = status_info.get("report_dates", [])

    if not labels:
        print("  ⚠️  无炎症分期数据，跳过")
        return

    fig, ax = plt.subplots(figsize=(len(labels) * 1.5 + 1, 5), facecolor="white")

    colors = [INFLAMMATION_COLORS.get(s, "#95a5a6") for s in labels]
    bars   = ax.bar(range(len(labels)), [1] * len(labels), color=colors,
                    width=0.55, edgecolor="white", linewidth=1.5)

    for i, (bar, label) in enumerate(zip(bars, labels)):
        ax.text(bar.get_x() + bar.get_width() / 2, 0.5, label,
                ha="center", va="center", fontsize=12, fontweight="bold",
                color="white")

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(dates_s, fontsize=11)
    ax.set_yticks([])
    ax.set_title("炎症分期演变", fontsize=14, fontweight="bold", pad=12)
    ax.set_ylabel("炎症状态", fontsize=10)
    ax.set_xlim(-0.7, len(labels) - 0.3)
    ax.set_ylim(0, 1.3)

    legend_patches = [mpatches.Patch(color=c, label=l)
                      for l, c in INFLAMMATION_COLORS.items() if l in labels]
    ax.legend(handles=legend_patches, loc="upper right", fontsize=9,
              title="分期标准", title_fontsize=9)

    # 添加hs-CRP数值标注
    if "hs-CRP" in df.columns:
        for i, (idx, row) in enumerate(df.iterrows()):
            hs = row.get("hs-CRP")
            if pd.notna(hs):
                ax.text(i, 1.1, f"hs-CRP\n{hs:.2f}", ha="center", va="bottom", fontsize=8, color="#2c3e50")

    plt.tight_layout()
    _save(fig, FIG_INFLA)


def plot_abnormal_indicators(df: pd.DataFrame, results: dict):
    """④ 异常指标标注图：每次就诊各指标是否超出参考范围"""
    _setup_chinese()
    abnormal = results.get("abnormal_summary", {})
    if not abnormal:
        print("  ℹ️  无异常指标数据，跳过异常标注图")
        # 画个空图
        fig, ax = plt.subplots(figsize=(8, 4), facecolor="white")
        ax.text(0.5, 0.5, "本次就诊无明显超出参考范围的指标",
                ha="center", va="center", fontsize=12, color="#27ae60")
        ax.axis("off")
        _save(fig, FIG_ABNORMAL)
        return

    # 取所有异常指标名，按字母排序
    abnormal_metrics = sorted(abnormal.keys())
    n_metrics = len(abnormal_metrics)
    dates_s   = results["inflammation_classification"]["report_dates"]

    fig, ax = plt.subplots(figsize=(len(dates_s) * 2 + 2, n_metrics * 0.7 + 2), facecolor="white")

    for xi, date_str in enumerate(dates_s):
        abnormal_on_date = [m for m in abnormal_metrics
                           if date_str in abnormal[m].get("abnormal_dates", [])]
        for yi, metric in enumerate(abnormal_metrics):
            ref_low, ref_high = REF_RANGES.get(metric, (None, None))
            color = "#e74c3c" if metric in abnormal_on_date else "#27ae60"
            marker = "▲" if metric in abnormal_on_date else "●"
            ax.scatter(xi, yi, color=color, s=120, zorder=3)
            ax.text(xi + 0.12, yi, f"{metric}", va="center", fontsize=9,
                    color=color if metric in abnormal_on_date else "#2c3e50")
            if ref_low is not None:
                ax.text(xi, yi - 0.2, f"ref:{ref_low}-{ref_high}",
                        ha="center", va="top", fontsize=7, color="#7f8c8d")

    ax.set_xticks(range(len(dates_s)))
    ax.set_xticklabels(dates_s, fontsize=11)
    ax.set_yticks(range(n_metrics))
    ax.set_yticklabels([""] * n_metrics)
    ax.set_title("各指标异常标注（▲=异常  ●=正常）", fontsize=13, fontweight="bold", pad=10)
    ax.grid(True, axis="x", alpha=0.3)
    ax.set_xlim(-0.5, len(dates_s) - 0.3)

    legend_elements = [
        mpatches.Patch(color="#e74c3c", label="异常（超出参考范围）"),
        mpatches.Patch(color="#27ae60", label="正常"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9)

    plt.tight_layout()
    _save(fig, FIG_ABNORMAL)


# ────────────────────────────────────────────────────────────────
# 核心分析函数
# ────────────────────────────────────────────────────────────────

def classify_inflammation(hs_crp):
    if hs_crp is None:
        return "未知"
    if hs_crp > ACUTE_THRESHOLD:
        return "急性期"
    elif hs_crp < REMISSION_THRESHOLD:
        return "缓解期"
    else:
        return "过渡期"


def linear_regression_trend(series: pd.Series) -> dict:
    valid = series.dropna()
    if len(valid) < 2:
        return {"slope": None, "intercept": None, "r2": None,
                "trend": "数据不足", "slope_per_day": None}

    x = np.arange(len(valid))
    y = valid.values.astype(float)
    x_mean, y_mean = x.mean(), y.mean()

    numerator   = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)

    if denominator == 0:
        return {"slope": 0, "intercept": y_mean, "r2": 0,
                "trend": "无变化", "slope_per_day": 0}

    slope     = numerator / denominator
    intercept = y_mean - slope * x_mean
    ss_res    = np.sum((y - (slope * x + intercept)) ** 2)
    ss_tot    = np.sum((y - y_mean) ** 2)
    r2        = 1 - ss_res / ss_tot if ss_tot != 0 else 0

    if slope > 0.1:
        trend = "上升"
    elif slope < -0.1:
        trend = "下降"
    else:
        trend = "平稳"

    return {
        "slope": round(float(slope), 4),
        "intercept": round(float(intercept), 4),
        "r2": round(float(r2), 4),
        "trend": trend,
        "slope_per_day": round(float(slope), 4),
        "n_points": int(len(valid)),
    }


def correlation_matrix_calc(df: pd.DataFrame, metrics: list) -> dict:
    cols = [m for m in metrics if m in df.columns]
    sub  = df[cols].apply(pd.to_numeric, errors="coerce")
    corr = sub.corr(method="pearson")
    result = {}
    for col in cols:
        for row in cols:
            if col == row:
                continue
            val = corr.loc[row, col]
            if pd.notna(val) and abs(val) >= 0.1:
                result[f"{row}~{col}"] = round(float(val), 3)
    return result


def descriptive_stats(series: pd.Series) -> dict:
    valid = series.dropna().astype(float)
    if len(valid) == 0:
        return {"count": 0, "mean": None, "std": None,
                "min": None, "max": None, "cv": None}
    mean = float(valid.mean())
    std  = float(valid.std(ddof=1)) if len(valid) > 1 else 0
    cv   = round(std / mean, 4) if mean != 0 else None
    return {
        "count": int(len(valid)),
        "mean": round(mean, 3),
        "std": round(std, 3),
        "min": round(float(valid.min()), 3),
        "max": round(float(valid.max()), 3),
        "cv": cv,
    }


def run():
    print(f"[{datetime.now().isoformat()}] 开始数据分析...")

    if not METRICS_CSV.exists():
        print(f"找不到数据文件: {METRICS_CSV}")
        print("请先运行 data_loader.py")
        return

    df = pd.read_csv(METRICS_CSV)
    df["report_date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values("report_date").reset_index(drop=True)

    print(f"数据范围: {df['report_date'].min().date()} ~ {df['report_date'].max().date()}")
    print(f"共 {len(df)} 份报告")

    results = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_reports": len(df),
        "date_range": {
            "start": df["report_date"].min().strftime("%Y-%m-%d"),
            "end":   df["report_date"].max().strftime("%Y-%m-%d"),
        },
    }

    # ── 1. 炎症状态分类 ──────────────────────────────────────
    inflammation_status = [classify_inflammation(
        row["hs-CRP"] if pd.notna(row.get("hs-CRP")) else None)
        for _, row in df.iterrows()]
    df["inflammation_status"] = inflammation_status
    results["inflammation_classification"] = {
        "labels": inflammation_status,
        "report_dates": df["report_date"].dt.strftime("%Y-%m-%d").tolist(),
    }
    print(f"炎症分类: {dict(zip(df['report_date'].dt.strftime('%m-%d'), inflammation_status))}")

    # ── 2. 线性回归趋势 ──────────────────────────────────────
    trend_results = {}
    key_for_trend = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"]
    for metric in key_for_trend:
        if metric not in df.columns:
            continue
        reg = linear_regression_trend(df[metric])
        if reg["slope"] is not None:
            trend_results[metric] = reg
            print(f"  {metric}: slope={reg['slope']:.4f}, R²={reg['r2']:.3f}, trend={reg['trend']}")
    results["linear_regression"] = trend_results

    # ── 3. 相关性矩阵 ────────────────────────────────────────
    corr_metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "PCT", "PLT"]
    corr = correlation_matrix_calc(df, corr_metrics)
    results["correlation_matrix"] = corr
    print(f"相关性显著 pairs: {len(corr)} 个")
    for pair, val in corr.items():
        print(f"  {pair}: r={val:.3f}")

    # ── 4. 描述性统计 ────────────────────────────────────────
    desc_stats = {}
    for metric in NUMERIC_METRICS:
        if metric in df.columns:
            desc = descriptive_stats(df[metric])
            if desc["count"] > 0:
                desc_stats[metric] = desc
    results["descriptive_stats"] = desc_stats

    # ── 5. 异常指标汇总 ──────────────────────────────────────
    abnormal_summary = {}
    for metric, (low, high) in REF_RANGES.items():
        if metric not in df.columns:
            continue
        col = df[metric].dropna()
        if len(col) == 0:
            continue
        abnormal_dates = df.loc[
            df[metric].notna() & ((df[metric] < low) | (df[metric] > high)),
            "report_date"
        ].dt.strftime("%Y-%m-%d").tolist()
        if abnormal_dates:
            abnormal_summary[metric] = {
                "ref_range": f"{low}-{high}",
                "abnormal_dates": abnormal_dates,
                "n_abnormal": len(abnormal_dates),
            }
    results["abnormal_summary"] = abnormal_summary
    print(f"异常指标: {list(abnormal_summary.keys())}")

    # ── 保存 JSON ────────────────────────────────────────────
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON 已保存: {OUTPUT_JSON}")

    # ── 画图 ─────────────────────────────────────────────────
    print("\n📊 开始绘图...")
    plot_trend_regression(df, results)
    plot_correlation_heatmap(df)
    plot_inflammation_status(df, results)
    plot_abnormal_indicators(df, results)

    print(f"[{datetime.now().isoformat()}] 数据分析完成")
    return results


if __name__ == "__main__":
    run()
