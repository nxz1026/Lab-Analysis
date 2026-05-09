#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_analyzer.py
对指定病人的 lab_metrics.csv 进行统计分析和建模，输出 analysis_results.json + 4张图。

用法：python data_analyzer.py --patient-id YOUR_PATIENT_ID
依赖：~/wiki/.venv/bin/python (pandas, numpy, scipy, scikit-learn)
"""

import json
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path
from datetime import datetime
import os

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))


def build_paths(patient_id: str):
    """根据 patient_id 和 ANALYSIS_TS 环境变量构建路径字典。"""
    import os
    raw_ts = os.environ.get("ANALYSIS_TS", patient_id)
    # ANALYSIS_TS 可能是纯时间戳（run_analysis.py 传入），也可能是 "deid/ts"（直接传参）
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts
    data_dir = WORK_ROOT / "data" / patient_id / ts
    analyzed_dir = data_dir / "02_analyzed"
    figures_dir = analyzed_dir / "figures"
    reports_dir = data_dir / "04_reports"
    return {
        "data_dir": data_dir,
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
    """设置中文字体（优先使用Windows系统字体）"""
    plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False


def _save(fig, path: Path):
    """保存图表，自动创建父目录"""
    # 先检查并创建父目录
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] 已保存: {path.name}")


def plot_trend_regression(df: pd.DataFrame, results: dict, output_path: Path):
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
    _save(fig, output_path)


def plot_correlation_heatmap(df: pd.DataFrame, output_path: Path):
    """② 相关性热力图：8个关键指标的 Pearson 相关系数"""
    _setup_chinese()
    metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "PCT", "PLT"]
    cols    = [m for m in metrics if m in df.columns]
    if len(cols) < 2:
        print("  [WARNING] 相关性指标不足，跳过热力图")
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
    _save(fig, output_path)


def plot_inflammation_status(df: pd.DataFrame, results: dict, output_path: Path):
    """③ 炎症分期柱状图：4次就诊的炎症状态颜色区分"""
    _setup_chinese()
    status_info = results.get("inflammation_classification", {})
    labels  = status_info.get("labels", [])
    dates_s = status_info.get("report_dates", [])

    if not labels:
        print("  [WARNING] 无炎症分期数据，跳过")
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
    _save(fig, output_path)


def plot_abnormal_indicators(df: pd.DataFrame, results: dict, output_path: Path):
    """④ 异常指标标注图：每次就诊各指标是否超出参考范围"""
    _setup_chinese()
    abnormal = results.get("abnormal_summary", {})
    if not abnormal:
        print("  [INFO] 无异常指标数据，跳过异常标注图")
        # 画个空图
        fig, ax = plt.subplots(figsize=(8, 4), facecolor="white")
        ax.text(0.5, 0.5, "本次就诊无明显超出参考范围的指标",
                ha="center", va="center", fontsize=12, color="#27ae60")
        ax.axis("off")
        _save(fig, output_path)
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
    _save(fig, output_path)


def plot_moving_average(df: pd.DataFrame, results: dict, output_path: Path):
    """⑤ 移动平均趋势图：原始值 vs 平滑趋势"""
    _setup_chinese()
    ma_data = results.get("moving_average", {})
    
    if not ma_data:
        print("  [WARNING] 无移动平均数据，跳过")
        return
    
    # 选择前4个关键指标
    key_metrics = ["hs-CRP", "CRP", "WBC", "NEUT#"]
    metrics_to_plot = [m for m in key_metrics if m in ma_data]
    
    if not metrics_to_plot:
        print("  [WARNING] 无可用指标绘制移动平均图")
        return
    
    n = len(metrics_to_plot)
    cols = 2
    rows = (n + cols - 1) // cols
    
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows), facecolor="white")
    axes = axes.flatten() if n > 1 else [axes]
    
    dates = pd.to_datetime(df["report_date"])
    date_labels = dates.dt.strftime("%m-%d").tolist()
    
    for i, metric in enumerate(metrics_to_plot):
        ax = axes[i]
        ma_info = ma_data[metric]
        
        # 原始数据
        original = df[metric].dropna()
        valid_dates = dates[df[metric].notna()]
        x_idx = np.arange(len(original))
        
        ax.plot(x_idx, original.values, 'o-', color='#3498db', linewidth=2, 
                markersize=6, label='原始值', alpha=0.7)
        
        # 移动平均
        ma_values = [v for v in ma_info['moving_avg'] if v is not None]
        if len(ma_values) == len(x_idx):
            ax.plot(x_idx, ma_values, 's--', color='#e74c3c', linewidth=2.5, 
                    markersize=5, label=f'移动平均(窗口={ma_info["window"]})')
        
        # 填充滚动标准差区域
        std_values = [v for v in ma_info['rolling_std'] if v is not None]
        if len(std_values) == len(ma_values):
            ma_array = np.array(ma_values)
            std_array = np.array(std_values)
            ax.fill_between(x_idx, ma_array - std_array, ma_array + std_array, 
                           alpha=0.15, color='#e74c3c', label='±1标准差')
        
        ax.set_xticks(x_idx)
        ax.set_xticklabels(date_labels[:len(x_idx)], fontsize=9)
        ax.set_title(f"{metric}\n趋势: {ma_info['trend']}", fontsize=11, fontweight="bold")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc='best')
    
    # 隐藏多余的子图
    for j in range(i + 1, len(axes)):
        axes[j].axis('off')
    
    fig.suptitle("移动平均趋势分析", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    _save(fig, output_path)


def plot_cv_stability_heatmap(df: pd.DataFrame, results: dict, output_path: Path):
    """⑥ CV稳定性热力图：直观显示各指标稳定性等级"""
    _setup_chinese()
    cv_data = results.get("cv_stability", {})
    
    if not cv_data:
        print("  [WARNING] 无CV数据，跳过")
        return
    
    # 准备数据
    metrics = sorted(cv_data.keys())
    cv_values = [cv_data[m]['cv'] for m in metrics]
    risk_levels = [cv_data[m]['risk_level'] for m in metrics]
    
    # 颜色映射
    color_map = {'低': '#27ae60', '中': '#f39c12', '高': '#e74c3c'}
    colors = [color_map.get(level, '#95a5a6') for level in risk_levels]
    
    # 创建热力图
    fig, ax = plt.subplots(figsize=(10, len(metrics) * 0.6 + 2), facecolor="white")
    
    # 绘制水平条形图
    y_pos = np.arange(len(metrics))
    bars = ax.barh(y_pos, cv_values, color=colors, height=0.6, edgecolor='white', linewidth=1.5)
    
    # 添加数值标签
    for i, (bar, cv_val, risk) in enumerate(zip(bars, cv_values, risk_levels)):
        ax.text(cv_val + max(cv_values) * 0.02, i, f"CV={cv_val:.4f}", 
                va='center', fontsize=9, fontweight='bold')
        ax.text(max(cv_values) * 0.5, i, risk, 
                va='center', ha='center', fontsize=10, color='white', fontweight='bold')
    
    ax.set_yticks(y_pos)
    ax.set_yticklabels(metrics, fontsize=10)
    ax.set_xlabel('变异系数 (CV)', fontsize=11, fontweight='bold')
    ax.set_title('指标稳定性分析（变异系数CV）', fontsize=13, fontweight='bold', pad=12)
    ax.grid(True, axis='x', alpha=0.3)
    ax.set_xlim(0, max(cv_values) * 1.3)
    
    # 添加图例
    legend_patches = [
        mpatches.Patch(color='#27ae60', label='稳定 (CV<0.1)'),
        mpatches.Patch(color='#f39c12', label='中等变异 (0.1≤CV<0.2)'),
        mpatches.Patch(color='#e74c3c', label='高变异 (CV≥0.2)'),
    ]
    ax.legend(handles=legend_patches, loc='lower right', fontsize=9)
    
    plt.tight_layout()
    _save(fig, output_path)


def plot_zscore_distribution(df: pd.DataFrame, results: dict, output_path: Path):
    """⑦ Z-score分布图：Box plot + 异常值标记"""
    _setup_chinese()
    zscore_data = results.get("zscore_outliers", {})
    
    if not zscore_data:
        print("  [WARNING] 无Z-score数据，跳过")
        return
    
    # 选择有关键指标的Z-scores
    key_metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD"]
    metrics_with_data = [m for m in key_metrics if m in zscore_data]
    
    if not metrics_with_data:
        print("  [WARNING] 无可用指标绘制Z-score图")
        return
    
    # 准备数据
    zscore_lists = []
    labels = []
    outlier_info = []
    
    for metric in metrics_with_data:
        zscores = zscore_data[metric]['z_scores']
        valid_zscores = [z for z in zscores if z is not None]
        if valid_zscores:
            zscore_lists.append(valid_zscores)
            labels.append(metric)
            outlier_info.append(zscore_data[metric])
    
    if not zscore_lists:
        print("  [WARNING] 无有效Z-score数据")
        return
    
    # 创建箱线图
    fig, ax = plt.subplots(figsize=(len(labels) * 1.5 + 2, 6), facecolor="white")
    
    bp = ax.boxplot(zscore_lists, labels=labels, patch_artist=True, 
                    widths=0.6, showfliers=True)
    
    # 自定义颜色
    colors_box = ['#3498db' if all(abs(z) < 2 for z in zs) else '#e74c3c' 
                  for zs in zscore_lists]
    for patch, color in zip(bp['boxes'], colors_box):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    # 添加阈值线
    ax.axhline(y=2, color='#e74c3c', linestyle='--', linewidth=1.5, alpha=0.7, label='|Z|=2 (轻度异常)')
    ax.axhline(y=-2, color='#e74c3c', linestyle='--', linewidth=1.5, alpha=0.7)
    ax.axhline(y=3, color='#c0392b', linestyle=':', linewidth=2, alpha=0.7, label='|Z|=3 (严重异常)')
    ax.axhline(y=-3, color='#c0392b', linestyle=':', linewidth=2, alpha=0.7)
    
    # 填充正常区域
    ax.axhspan(-2, 2, alpha=0.1, color='green', label='正常范围 (|Z|<2)')
    
    ax.set_ylabel('Z-score', fontsize=11, fontweight='bold')
    ax.set_title('Z-score异常检测分布', fontsize=13, fontweight='bold', pad=12)
    ax.grid(True, axis='y', alpha=0.3)
    ax.legend(fontsize=9, loc='upper right')
    
    # 旋转x轴标签
    plt.xticks(rotation=45, ha='right')
    
    plt.tight_layout()
    _save(fig, output_path)


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


def moving_average_analysis(df: pd.DataFrame, window: int = 2) -> dict:
    """
    移动平均分析：计算滚动平均值和标准差，平滑短期波动
    
    Args:
        df: 数据框
        window: 滚动窗口大小（默认2次就诊）
    
    Returns:
        每个指标的移动平均结果
    """
    results = {}
    key_metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"]
    
    for metric in key_metrics:
        if metric not in df.columns:
            continue
        
        series = df[metric].dropna()
        if len(series) < window:
            continue
        
        # 计算滚动平均值和标准差
        ma = series.rolling(window=window, min_periods=1).mean()
        std = series.rolling(window=window, min_periods=1).std().fillna(0)
        
        # 计算移动平均的趋势
        if len(ma) >= 2:
            ma_values = ma.values
            trend = "上升" if ma_values[-1] > ma_values[0] * 1.05 else \
                    "下降" if ma_values[-1] < ma_values[0] * 0.95 else "平稳"
        else:
            trend = "数据不足"
        
        results[metric] = {
            "moving_avg": [round(v, 3) if pd.notna(v) else None for v in ma],
            "rolling_std": [round(v, 3) if pd.notna(v) else None for v in std],
            "trend": trend,
            "window": window,
        }
    
    return results


def cv_stability_analysis(df: pd.DataFrame) -> dict:
    """
    变异系数（CV）分析：评估指标稳定性和生物学变异
    
    CV = 标准差 / 均值
    - CV < 0.1: 稳定
    - 0.1 <= CV < 0.2: 中等变异
    - CV >= 0.2: 高变异（需关注）
    
    Args:
        df: 数据框
    
    Returns:
        每个指标的CV分析结果
    """
    results = {}
    
    for metric in NUMERIC_METRICS:
        if metric not in df.columns:
            continue
        
        series = df[metric].dropna().astype(float)
        if len(series) < 3:  # 至少需要3个数据点
            continue
        
        mean = series.mean()
        std = series.std(ddof=1)
        
        if mean == 0:
            continue
        
        cv = std / mean
        
        # 稳定性分类
        if cv < 0.1:
            stability = "稳定"
            risk_level = "低"
        elif cv < 0.2:
            stability = "中等变异"
            risk_level = "中"
        else:
            stability = "高变异"
            risk_level = "高"
        
        # 计算滑动CV（窗口=3）
        rolling_cv = series.rolling(window=3, min_periods=2).apply(
            lambda x: x.std() / x.mean() if x.mean() != 0 and len(x) >= 2 else np.nan
        )
        
        results[metric] = {
            "cv": round(cv, 4),
            "mean": round(mean, 3),
            "std": round(std, 3),
            "stability": stability,
            "risk_level": risk_level,
            "n_points": len(series),
            "rolling_cv": [round(v, 4) if pd.notna(v) else None for v in rolling_cv],
        }
    
    return results


def zscore_outlier_detection(df: pd.DataFrame, threshold: float = 2.0) -> dict:
    """
    Z-score异常检测：基于标准化分数的异常值识别
    
    Z = (x - μ) / σ
    - |Z| > 2: 轻度异常
    - |Z| > 3: 严重异常
    
    Args:
        df: 数据框
        threshold: Z-score阈值（默认2.0）
    
    Returns:
        每个指标的Z-score分析结果
    """
    results = {}
    
    for metric in NUMERIC_METRICS:
        if metric not in df.columns:
            continue
        
        series = df[metric].dropna().astype(float)
        if len(series) < 3:
            continue
        
        mean = series.mean()
        std = series.std(ddof=1)
        
        if std == 0:
            continue
        
        # 计算Z-scores
        zscores = (series - mean) / std
        
        # 识别异常值
        outliers_mild = zscores[zscores.abs() > threshold]
        outliers_severe = zscores[zscores.abs() > 3.0]
        
        # 获取异常值的日期
        outlier_dates_mild = df.loc[outliers_mild.index, "report_date"].dt.strftime("%Y-%m-%d").tolist()
        outlier_dates_severe = df.loc[outliers_severe.index, "report_date"].dt.strftime("%Y-%m-%d").tolist()
        
        # 最大偏离程度
        max_deviation_idx = zscores.abs().idxmax()
        max_deviation_value = series[max_deviation_idx]
        max_zscore = zscores[max_deviation_idx]
        
        results[metric] = {
            "z_scores": [round(v, 3) if pd.notna(v) else None for v in zscores],
            "outliers_mild": {
                "count": len(outliers_mild),
                "dates": outlier_dates_mild,
                "values": [round(series[idx], 3) for idx in outliers_mild.index],
            },
            "outliers_severe": {
                "count": len(outliers_severe),
                "dates": outlier_dates_severe,
                "values": [round(series[idx], 3) for idx in outliers_severe.index],
            },
            "max_deviation": {
                "date": df.loc[max_deviation_idx, "report_date"].strftime("%Y-%m-%d"),
                "value": round(max_deviation_value, 3),
                "z_score": round(max_zscore, 3),
            },
            "threshold": threshold,
        }
    
    return results


def run(patient_id: str):
    paths = build_paths(patient_id)
    print(f"[{datetime.now().isoformat()}] 开始数据分析...")
    print(f"  病人: {patient_id}")

    if not paths["metrics_csv"].exists():
        print(f"❌ 找不到前置文件: {paths['metrics_csv']}")
        print(f"   请先运行 data_loader.py --patient-id {patient_id}")
        sys.exit(1)

    df = pd.read_csv(paths["metrics_csv"])
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
            print(f"  {metric}: slope={reg['slope']:.4f}, R2={reg['r2']:.3f}, trend={reg['trend']}")
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

    # ── 6. 移动平均分析 ──────────────────────────────────────
    ma_results = moving_average_analysis(df, window=2)
    results["moving_average"] = ma_results
    print(f"\n移动平均分析完成: {len(ma_results)} 个指标")
    for metric, ma_data in list(ma_results.items())[:3]:  # 只显示前3个
        print(f"  {metric}: 趋势={ma_data['trend']}, 窗口={ma_data['window']}")

    # ── 7. 变异系数（CV）稳定性分析 ───────────────────────────
    cv_results = cv_stability_analysis(df)
    results["cv_stability"] = cv_results
    print(f"\nCV稳定性分析完成: {len(cv_results)} 个指标")
    high_cv = [(m, d) for m, d in cv_results.items() if d['risk_level'] == '高']
    if high_cv:
        print(f"  ⚠️  高变异指标: {', '.join([m for m, _ in high_cv])}")
    else:
        print(f"  ✅ 所有指标稳定性良好")

    # ── 8. Z-score异常检测 ───────────────────────────────────
    zscore_results = zscore_outlier_detection(df, threshold=2.0)
    results["zscore_outliers"] = zscore_results
    print(f"\nZ-score异常检测完成: {len(zscore_results)} 个指标")
    total_outliers = sum(d['outliers_mild']['count'] for d in zscore_results.values())
    severe_outliers = sum(d['outliers_severe']['count'] for d in zscore_results.values())
    if severe_outliers > 0:
        print(f"  🚨 发现 {severe_outliers} 个严重异常值 (|Z|>3)")
    if total_outliers > 0:
        print(f"  ⚠️  发现 {total_outliers} 个轻度异常值 (|Z|>2)")
    paths["analyzed_dir"].mkdir(parents=True, exist_ok=True)
    paths["reports_dir"].mkdir(parents=True, exist_ok=True)
    with open(paths["output_json"], "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON 已保存: {paths['output_json']}")

    # ── 生成人类可读 Markdown 报告 ──────────────────────────
    md_lines = ["# 统计分析报告\n"]
    md_lines.append(f"**患者**: {patient_id}  **报告数**: {results['n_reports']}  **日期范围**: {results['date_range']}\n")

    # 炎症分期
    infl = results.get("inflammation_classification", {})
    labels = infl.get("labels", []) if isinstance(infl, dict) else []
    dates = infl.get("report_dates", []) if isinstance(infl, dict) else []
    emoji_map = {"急性期":"[RED]","过渡期":"[YELLOW]","缓解期":"[GREEN]"}
    md_lines.append("## 炎症分期\n")
    for date, cls in zip(dates, labels):
        emoji = emoji_map.get(cls, "[GRAY]")
        md_lines.append(f"- {date}: {emoji} {cls}\n")

    # 异常指标
    md_lines.append("\n## 异常指标\n")
    for metric, info in results["abnormal_summary"].items():
        n = info.get("n_abnormal",0)
        dates = info.get("abnormal_dates",[])
        ref = info.get("ref_range","?")
        md_lines.append(f"- **{metric}**: 异常 {n} 次（{', '.join(dates)}），参考区间 {ref}\n")

    # 回归趋势
    md_lines.append("\n## 指标趋势（线性回归）\n")
    for metric, reg in results.get("linear_regression",{}).items():
        slope = reg.get("slope",0)
        r2 = reg.get("r2", reg.get("r_squared", 0))
        trend = reg.get("trend","平稳")
        arrow = "UP" if slope>0 else "DOWN" if slope<0 else "FLAT"
        md_lines.append(f"- {metric}: slope={slope:.4f}, R2={r2:.3f}, {arrow} {trend}\n")

    # 强相关对
    md_lines.append("\n## 强相关性（|r| ≥ 0.9）\n")
    corr = results.get("correlation_matrix",{})
    strong = [(p,r) for p,r in corr.items() if isinstance(r,(int,float)) and abs(r)>=0.9]
    strong.sort(key=lambda x:-abs(x[1]))
    for pair, r in strong:
        sign = "正" if r>0 else "负"
        md_lines.append(f"- {pair}: r={r:.3f}（{sign}相关）\n")

    # 移动平均趋势
    md_lines.append("\n## 移动平均趋势分析\n")
    ma_data = results.get("moving_average", {})
    for metric, ma_info in ma_data.items():
        trend = ma_info.get("trend", "?")
        window = ma_info.get("window", 2)
        arrow = "↑" if trend == "上升" else "↓" if trend == "下降" else "→"
        md_lines.append(f"- {metric}: {arrow} {trend}（窗口={window}次就诊）\n")

    # CV稳定性分析
    md_lines.append("\n## 指标稳定性分析（变异系数CV）\n")
    cv_data = results.get("cv_stability", {})
    high_risk = [(m, d) for m, d in cv_data.items() if d.get('risk_level') == '高']
    medium_risk = [(m, d) for m, d in cv_data.items() if d.get('risk_level') == '中']
    
    if high_risk:
        md_lines.append("### ⚠️  高变异指标（需关注）\n")
        for metric, info in high_risk:
            cv = info.get('cv', 0)
            md_lines.append(f"- **{metric}**: CV={cv:.4f}（波动较大）\n")
    
    if medium_risk:
        md_lines.append("\n### 🟡 中等变异指标\n")
        for metric, info in medium_risk:
            cv = info.get('cv', 0)
            md_lines.append(f"- {metric}: CV={cv:.4f}\n")
    
    stable = [(m, d) for m, d in cv_data.items() if d.get('risk_level') == '低']
    if stable:
        md_lines.append(f"\n### ✅ 稳定指标（{len(stable)}个）\n")
        metrics_list = ", ".join([m for m, _ in stable[:5]])
        if len(stable) > 5:
            metrics_list += f" 等{len(stable)}个"
        md_lines.append(f"- {metrics_list}\n")

    # Z-score异常检测
    md_lines.append("\n## Z-score异常检测结果\n")
    zscore_data = results.get("zscore_outliers", {})
    severe_outliers = []
    mild_outliers = []
    
    for metric, info in zscore_data.items():
        severe = info.get('outliers_severe', {})
        mild = info.get('outliers_mild', {})
        
        if severe.get('count', 0) > 0:
            severe_outliers.append((metric, severe))
        elif mild.get('count', 0) > 0:
            mild_outliers.append((metric, mild))
    
    if severe_outliers:
        md_lines.append("### 🚨 严重异常值（|Z| > 3）\n")
        for metric, info in severe_outliers:
            dates = ', '.join(info.get('dates', []))
            values = ', '.join([str(v) for v in info.get('values', [])])
            max_dev = info.get('max_deviation', {})
            md_lines.append(f"- **{metric}**: {info['count']}次异常\n")
            md_lines.append(f"  - 日期: {dates}\n")
            md_lines.append(f"  - 数值: {values}\n")
            md_lines.append(f"  - 最大偏离: Z={max_dev.get('z_score', 0):.2f} ({max_dev.get('date', '')})\n")
    
    if mild_outliers:
        md_lines.append("\n### ⚠️  轻度异常值（|Z| > 2）\n")
        for metric, info in mild_outliers:
            dates = ', '.join(info.get('dates', []))
            md_lines.append(f"- {metric}: {info['count']}次异常（{dates}）\n")
    
    if not severe_outliers and not mild_outliers:
        md_lines.append("- ✅ 未发现统计学异常值\n")

    md_report_path = paths["report_md"]
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.writelines(md_lines)
    print(f"Markdown 已保存: {md_report_path}")

    # ── 画图 ─────────────────────────────────────────────────
    print("\n[CHARTS] 开始绘图...")
    plot_trend_regression(df, results, paths["fig_trend"])
    plot_correlation_heatmap(df, paths["fig_corr"])
    plot_inflammation_status(df, results, paths["fig_infl"])
    plot_abnormal_indicators(df, results, paths["fig_abnorm"])
    
    # 新增高级分析图表
    print("\n[ADVANCED CHARTS] 绘制高级分析图表...")
    plot_moving_average(df, results, paths["fig_ma"])
    plot_cv_stability_heatmap(df, results, paths["fig_cv"])
    plot_zscore_distribution(df, results, paths["fig_zscore"])

    print(f"[{datetime.now().isoformat()}] 数据分析完成")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="统计分析：生成分析结果 + 4类图表")
    parser.add_argument("--patient-id", required=True, help="诊疗卡号，如 YOUR_PATIENT_ID")
    args = parser.parse_args()
    run(args.patient_id)
