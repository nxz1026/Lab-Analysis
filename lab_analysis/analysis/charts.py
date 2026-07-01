"""lab_analysis.analysis.charts — 7 张统计图表"""

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from .. import _log

# 先导 _base 确保 matplotlib.use("Agg") 在 pyplot 导入前执行
from ._base import (
    INFLAMMATION_COLORS,
    REF_RANGES,
    save_fig,
    setup_chinese,
)

logger = _log.get_logger(__name__)

# 模块级一次性初始化中文字体，避免在每个图表函数中重复调用
setup_chinese()


def plot_trend_regression(df: pd.DataFrame, results: dict, output_path: Path):
    """① 趋势回归图：7个关键指标的时序折线 + 回归拟合线"""
    metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"]
    metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"]
    n = len(metrics)
    cols = 3
    rows = (n + cols - 1) // cols

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
        y_vals = series.values.astype(float)
        x_idx = np.arange(len(y_vals))

        ax.plot(x_idx, y_vals, "o-", color="#3498db", linewidth=2, markersize=7, label="实测值")

        reg = linear_results.get(metric, {})
        if reg.get("slope") is not None and len(y_vals) >= 2:
            slope = reg.get("slope", 0)
            intercept = reg.get("intercept", 0)
            r2 = reg.get("r2", 0)
            x_line = np.array([x_idx.min(), x_idx.max()])
            y_line = slope * x_line + intercept
            ax.plot(x_line, y_line, "--", color="#e74c3c", linewidth=1.8, label=f"拟合 R²={r2:.3f}")
            ax.text(
                0.05,
                0.95,
                f"slope={slope:.4f}\ntrend={reg.get('trend', '?')}",
                transform=ax.transAxes,
                fontsize=7,
                va="top",
                color="#2c3e50",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#ecf0f1", alpha=0.7),  # noqa: C408
            )

        ref_range = REF_RANGES.get(metric)
        if ref_range:
            low, high = ref_range
            ax.axhspan(low, high, alpha=0.15, color="green", label="参考范围")
            ax.axhline(low, color="green", linewidth=0.8, linestyle=":")
            ax.axhline(high, color="green", linewidth=0.8, linestyle=":")

        ax.set_xticks(x_idx)
        valid_dates = df[df[metric].notna()]["report_date"]
        ax.set_xticklabels([d.strftime("%m-%d") for d in pd.to_datetime(valid_dates)], fontsize=8)
        ax.set_title(f"{metric}", fontsize=11, fontweight="bold")
        ax.grid(True, alpha=0.3)
        if i == 0:
            ax.legend(fontsize=7, loc="upper right")

    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    fig.suptitle("关键指标趋势回归分析", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    save_fig(fig, output_path)


def plot_correlation_heatmap(df: pd.DataFrame, output_path: Path):
    """② 相关性热力图：8个关键指标的 Pearson 相关系数"""
    metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "PCT", "PLT"]
    cols = [m for m in metrics if m in df.columns]
    if len(cols) < 2:
        logger.warning("  [WARNING] 相关性指标不足，跳过热力图")
        return

    sub = df[cols].apply(pd.to_numeric, errors="coerce")
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
            ax.text(
                xi,
                yi,
                f"{val:.2f}",
                ha="center",
                va="center",
                fontsize=9,
                color="white" if abs(val) > 0.5 else "black",
                fontweight="bold",
            )
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Pearson r", fontsize=10)
    fig.suptitle("指标相关性热力图", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    save_fig(fig, output_path)


def plot_inflammation_status(df: pd.DataFrame, results: dict, output_path: Path):
    """③ 炎症分期柱状图：4次就诊的炎症状态颜色区分"""
    status_info = results.get("inflammation_classification", {})
    labels = status_info.get("labels", [])
    dates_s = status_info.get("report_dates", [])
    if not labels:
        logger.warning("  [WARNING] 无炎症分期数据，跳过")
        return

    fig, ax = plt.subplots(figsize=(len(labels) * 1.5 + 1, 5), facecolor="white")
    colors = [INFLAMMATION_COLORS.get(s, "#95a5a6") for s in labels]
    bars = ax.bar(
        range(len(labels)),
        [1] * len(labels),
        color=colors,
        width=0.55,
        edgecolor="white",
        linewidth=1.5,
    )
    for bar, label in zip(bars, labels, strict=True):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            0.5,
            label,
            ha="center",
            va="center",
            fontsize=12,
            fontweight="bold",
            color="white",
        )
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(dates_s, fontsize=11)
    ax.set_yticks([])
    ax.set_title("炎症分期演变", fontsize=14, fontweight="bold", pad=12)
    ax.set_ylabel("炎症状态", fontsize=10)
    ax.set_xlim(-0.7, len(labels) - 0.3)
    ax.set_ylim(0, 1.3)

    legend_patches = [
        mpatches.Patch(color=c, label=name)
        for name, c in INFLAMMATION_COLORS.items()
        if name in labels
    ]
    ax.legend(
        handles=legend_patches, loc="upper right", fontsize=9, title="分期标准", title_fontsize=9
    )
    if "hs-CRP" in df.columns:
        for i, (_idx, row) in enumerate(df.iterrows()):
            hs = row.get("hs-CRP")
            if pd.notna(hs):
                ax.text(
                    i,
                    1.1,
                    f"hs-CRP\n{hs:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color="#2c3e50",
                )
    plt.tight_layout()
    save_fig(fig, output_path)


def plot_abnormal_indicators(df: pd.DataFrame, results: dict, output_path: Path):
    """④ 异常指标标注图：每次就诊各指标是否超出参考范围"""
    abnormal = results.get("abnormal_summary", {})
    if not abnormal:
        fig, ax = plt.subplots(figsize=(8, 4), facecolor="white")
        ax.text(
            0.5,
            0.5,
            "本次就诊无明显超出参考范围的指标",
            ha="center",
            va="center",
            fontsize=12,
            color="#27ae60",
        )
        ax.axis("off")
        save_fig(fig, output_path)
        return

    abnormal_metrics = sorted(abnormal.keys())
    n_metrics = len(abnormal_metrics)
    dates_s = results["inflammation_classification"]["report_dates"]
    fig, ax = plt.subplots(figsize=(len(dates_s) * 2 + 2, n_metrics * 0.7 + 2), facecolor="white")

    for xi, date_str in enumerate(dates_s):
        abnormal_on_date = [
            m for m in abnormal_metrics if date_str in abnormal[m].get("abnormal_dates", [])
        ]
        for yi, metric in enumerate(abnormal_metrics):
            ref_low, ref_high = REF_RANGES.get(metric, (None, None))
            color = "#e74c3c" if metric in abnormal_on_date else "#27ae60"
            ax.scatter(xi, yi, color=color, s=120, zorder=3)
            ax.text(
                xi + 0.12,
                yi,
                f"{metric}",
                va="center",
                fontsize=9,
                color=color if metric in abnormal_on_date else "#2c3e50",
            )
            if ref_low is not None:
                ax.text(
                    xi,
                    yi - 0.2,
                    f"ref:{ref_low}-{ref_high}",
                    ha="center",
                    va="top",
                    fontsize=7,
                    color="#7f8c8d",
                )

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
    save_fig(fig, output_path)


def plot_moving_average(df: pd.DataFrame, results: dict, output_path: Path):
    """⑤ 移动平均趋势图：原始值 vs 平滑趋势"""
    ma_data = results.get("moving_average", {})
    if not ma_data:
        logger.warning("  [WARNING] 无移动平均数据，跳过")
        return

    key_metrics = ["hs-CRP", "CRP", "WBC", "NEUT#"]
    metrics_to_plot = [m for m in key_metrics if m in ma_data]
    if not metrics_to_plot:
        logger.warning("  [WARNING] 无可用指标绘制移动平均图")
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
        original = df[metric].dropna()
        x_idx = np.arange(len(original))
        ax.plot(
            x_idx,
            original.values,
            "o-",
            color="#3498db",
            linewidth=2,
            markersize=6,
            label="原始值",
            alpha=0.7,
        )

        ma_values = [v for v in ma_info["moving_avg"] if v is not None]
        if len(ma_values) == len(x_idx):
            ax.plot(
                x_idx,
                ma_values,
                "s--",
                color="#e74c3c",
                linewidth=2.5,
                markersize=5,
                label=f"移动平均(窗口={ma_info['window']})",
            )

        std_values = [v for v in ma_info["rolling_std"] if v is not None]
        if len(std_values) == len(ma_values):
            ma_array, std_array = np.array(ma_values), np.array(std_values)
            ax.fill_between(
                x_idx,
                ma_array - std_array,
                ma_array + std_array,
                alpha=0.15,
                color="#e74c3c",
                label="±1标准差",
            )

        ax.set_xticks(x_idx)
        ax.set_xticklabels(date_labels[: len(x_idx)], fontsize=9)
        ax.set_title(f"{metric}\n趋势: {ma_info['trend']}", fontsize=11, fontweight="bold")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, loc="best")

    for j in range(i + 1, len(axes)):
        axes[j].axis("off")
    fig.suptitle("移动平均趋势分析", fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()
    save_fig(fig, output_path)


def plot_cv_stability_heatmap(df: pd.DataFrame, results: dict, output_path: Path):
    """⑥ CV稳定性热力图：各指标变异系数"""
    cv_data = results.get("cv_stability", {})
    if not cv_data:
        logger.warning("  [WARNING] 无CV数据，跳过")
        return

    metrics = sorted(cv_data.keys())
    cv_values = [cv_data[m]["cv"] for m in metrics]
    risk_levels = [cv_data[m]["risk_level"] for m in metrics]
    color_map = {"低": "#27ae60", "中": "#f39c12", "高": "#e74c3c"}
    colors = [color_map.get(level, "#95a5a6") for level in risk_levels]

    fig, ax = plt.subplots(figsize=(10, len(metrics) * 0.6 + 2), facecolor="white")
    y_pos = np.arange(len(metrics))
    bars = ax.barh(y_pos, cv_values, color=colors, height=0.6, edgecolor="white", linewidth=1.5)
    for bar, cv_val, risk in zip(bars, cv_values, risk_levels, strict=True):
        ax.text(
            cv_val + max(cv_values) * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"CV={cv_val:.4f}",
            va="center",
            fontsize=9,
            fontweight="bold",
        )
        ax.text(
            max(cv_values) * 0.5,
            bar.get_y() + bar.get_height() / 2,
            risk,
            va="center",
            ha="center",
            fontsize=10,
            color="white",
            fontweight="bold",
        )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(metrics, fontsize=10)
    ax.set_xlabel("变异系数 (CV)", fontsize=11, fontweight="bold")
    ax.set_title("指标稳定性分析（变异系数CV）", fontsize=13, fontweight="bold", pad=12)
    ax.grid(True, axis="x", alpha=0.3)
    ax.set_xlim(0, max(cv_values) * 1.3)
    legend_patches = [
        mpatches.Patch(color="#27ae60", label="稳定 (CV<0.1)"),
        mpatches.Patch(color="#f39c12", label="中等变异 (0.1≤CV<0.2)"),
        mpatches.Patch(color="#e74c3c", label="高变异 (CV≥0.2)"),
    ]
    ax.legend(handles=legend_patches, loc="lower right", fontsize=9)
    plt.tight_layout()
    save_fig(fig, output_path)


def plot_zscore_distribution(df: pd.DataFrame, results: dict, output_path: Path):
    """⑦ Z-score分布图：Box plot + 异常值标记"""
    zscore_data = results.get("zscore_outliers", {})
    if not zscore_data:
        logger.warning("  [WARNING] 无Z-score数据，跳过")
        return

    key_metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD"]
    metrics_with_data = [m for m in key_metrics if m in zscore_data]
    if not metrics_with_data:
        logger.warning("  [WARNING] 无可用指标绘制Z-score图")
        return

    zscore_lists, labels = [], []
    for metric in metrics_with_data:
        zs = [z for z in zscore_data[metric]["z_scores"] if z is not None]
        if zs:
            zscore_lists.append(zs)
            labels.append(metric)

    if not zscore_lists:
        logger.warning("  [WARNING] 无有效Z-score数据")
        return

    fig, ax = plt.subplots(figsize=(len(labels) * 1.5 + 2, 6), facecolor="white")
    bp = ax.boxplot(
        zscore_lists, tick_labels=labels, patch_artist=True, widths=0.6, showfliers=True
    )
    colors_box = ["#3498db" if all(abs(z) < 2 for z in zs) else "#e74c3c" for zs in zscore_lists]
    for patch, color in zip(bp["boxes"], colors_box, strict=True):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.axhline(
        y=2, color="#e74c3c", linestyle="--", linewidth=1.5, alpha=0.7, label="|Z|=2 (轻度异常)"
    )
    ax.axhline(y=-2, color="#e74c3c", linestyle="--", linewidth=1.5, alpha=0.7)
    ax.axhline(
        y=3, color="#c0392b", linestyle=":", linewidth=2, alpha=0.7, label="|Z|=3 (严重异常)"
    )
    ax.axhline(y=-3, color="#c0392b", linestyle=":", linewidth=2, alpha=0.7)
    ax.axhspan(-2, 2, alpha=0.1, color="green", label="正常范围 (|Z|<2)")
    ax.set_ylabel("Z-score", fontsize=11, fontweight="bold")
    ax.set_title("Z-score异常检测分布", fontsize=13, fontweight="bold", pad=12)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(fontsize=9, loc="upper right")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    save_fig(fig, output_path)
