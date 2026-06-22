"""quant_visualizer.py — 6 指标量化结果可视化 (matplotlib + HTML)

设计:
- 纯函数为主 (便于 CI 单元测试, 不依赖磁盘)
- render_metrics_chart(metrics) -> bytes      PNG bytes (条形图 + 阈值线)
- render_metrics_html(report) -> str          单文件 HTML (内嵌 base64 PNG, 可邮件/IM 发送)
- render_trend_chart(reports) -> bytes        多 patient 趋势图 (折线)

不依赖外部 CSS/JS, 输出后可直接打开浏览器看.
"""

from __future__ import annotations

import base64
import io
import warnings
from typing import Any

import matplotlib
from matplotlib.figure import Figure

# 强制 Agg backend, 无 GUI 环境 (CI / Linux server) 也能跑
matplotlib.use("Agg")

# 抑制 matplotlib 中文字体缺失警告 (CI / Linux 默认无中文, 静态 PNG 仍能生成)
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
# 同上, 涵盖 glyph/font 警告
warnings.filterwarnings("ignore", message=".*missing from font.*")

# 默认阈值 (与 scripts/quant_eval_gate.py 一致)
DEFAULT_THRESHOLDS: dict[str, tuple[float, str]] = {
    "entity_f1": (0.70, "f1 ≥ 0.70"),
    "section_coverage": (0.80, "coverage ≥ 0.80"),
    "entity_recall": (0.70, "recall ≥ 0.70"),
    "confidence": (0.60, "dspy_conf ≥ 0.60"),
}


def _extract_metric_value(metric: dict, name: str) -> tuple[float | None, bool]:
    """从 metric dict 提取 (数值, available). 不可用返回 (None, False)."""
    if not metric or not metric.get("available"):
        return None, False
    if name == "entity_f1":
        return float(metric.get("f1", 0.0)), True
    if name == "section_coverage":
        return float(metric.get("coverage_rate", 0.0)), True
    if name == "entity_recall":
        return float(metric.get("recall_rate", 0.0)), True
    if name == "confidence":
        return float(metric.get("dspy_confidence", 0.0)), True
    if name == "failure_rate":
        # failure_rate 用 0/1 表示: 0=PASS, 1=FAIL (图上越低越好)
        return float(1 if metric.get("is_failure") else 0), True
    return None, False


def render_metrics_chart(
    metrics: dict[str, dict],
    *,
    thresholds: dict[str, tuple[float, str]] | None = None,
    title: str = "DSPy 6-Metric Quant Eval",
    figsize: tuple[float, float] = (10, 5),
) -> bytes:
    """生成 6 指标条形图 PNG (含阈值线).

    Args:
        metrics: {"entity_f1": {...}, "section_coverage": {...}, ...}
        thresholds: {"entity_f1": (0.70, "f1 ≥ 0.70"), ...}
            不传则用 DEFAULT_THRESHOLDS.
        title: 图标题
        figsize: (宽, 高) 英寸

    Returns:
        PNG bytes
    """
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    # 6 个 metric: 4 个有阈值 (条形图) + failure_rate (二元) + feedback_delta (可选)
    ordered = [
        ("entity_f1", "F1", "f1"),
        ("section_coverage", "Coverage", "rate"),
        ("entity_recall", "Entity Recall", "rate"),
        ("confidence", "DSPy Conf", "conf"),
    ]
    fr_val, fr_ok = _extract_metric_value(metrics.get("failure_rate", {}), "failure_rate")
    fd = metrics.get("feedback_delta", {})
    fd_ok = bool(fd and fd.get("available"))
    fd_avg = float(fd.get("avg_delta_confidence", 0.0)) if fd_ok else None

    fig = Figure(figsize=figsize, dpi=100)
    ax = fig.add_subplot(111)

    names: list[str] = []
    values: list[float] = []
    threshold_lines: list[float] = []
    colors: list[str] = []

    for key, label, _hint in ordered:
        v, ok = _extract_metric_value(metrics.get(key, {}), key)
        names.append(label)
        threshold = thr.get(key, (0.0, ""))[0]
        threshold_lines.append(threshold)
        if not ok or v is None:
            values.append(0.0)
            colors.append("#cccccc")  # 灰 = 不可用
        else:
            values.append(v)
            colors.append("#2ca02c" if v >= threshold else "#d62728")  # 绿=PASS, 红=FAIL

    # failure_rate 二元: 单独画在右 Y 轴
    ax2 = ax.twinx()
    if fr_ok and fr_val is not None:
        ax2.barh(
            ["failure_rate"],
            [fr_val],
            color="#d62728" if fr_val == 1 else "#2ca02c",
            alpha=0.6,
            height=0.4,
        )
        ax2.set_xlim(0, 1.2)
        ax2.set_yticks([])
        ax2.set_xticks([0, 1])
        ax2.set_xticklabels(["OK", "FAIL"], fontsize=8)
        ax2.set_title("Failure (0=OK, 1=FAIL)", fontsize=8, loc="right", pad=2)

    # 主条形图
    bars = ax.bar(names, values, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    for bar, thr_v, label in zip(bars, threshold_lines, names):
        ax.hlines(thr_v, bar.get_x(), bar.get_x() + bar.get_width(), colors="blue", linestyles="--", linewidth=1.2)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Metric Value (0~1)")
    ax.set_title(title, fontsize=12, pad=10)
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", labelsize=9)

    # 数值标签
    for bar, v in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{v:.2f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    # feedback_delta subtitle (英文以避免中文字体警告)
    subtitle = ""
    if fd_ok and fd_avg is not None:
        subtitle = f"  |  feedback_delta avg={fd_avg:+.3f}  (n={fd.get('n_corrections', 0)})"
    elif fd:
        subtitle = "  |  feedback_delta N/A"
    if subtitle:
        fig.text(0.5, 0.01, subtitle, ha="center", fontsize=9, color="#555555")

    fig.tight_layout(rect=(0, 0.04, 1, 1))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    return buf.getvalue()


def render_metrics_html(
    report: dict,
    *,
    chart_bytes: bytes | None = None,
    title: str | None = None,
) -> str:
    """生成单文件 HTML, 内嵌 base64 PNG, 浏览器可直接打开.

    Args:
        report: quant_eval_report.json dict
        chart_bytes: 不传则自动 render_metrics_chart()
        title: HTML 标题, 默认用 report["deid"]

    Returns:
        HTML 字符串
    """
    if chart_bytes is None:
        chart_bytes = render_metrics_chart(report.get("metrics", {}), title=f"量化评估: {report.get('deid', '?')}")

    b64 = base64.b64encode(chart_bytes).decode("ascii")
    metrics = report.get("metrics", {})
    rows: list[str] = []
    for name, m in metrics.items():
        if not m.get("available"):
            rows.append(
                f"<tr><td>{name}</td><td colspan='3' style='color:#999'>N/A: {m.get('reason', '?')}</td></tr>"
            )
            continue
        if name == "entity_f1":
            detail = f"tp={m.get('tp', '?')} fp={m.get('fp', '?')} fn={m.get('fn', '?')} prec={m.get('precision', 0):.2%} rec={m.get('recall', 0):.2%}"
        elif name == "section_coverage":
            detail = f"non-empty={m.get('n_nonempty', '?')}/{m.get('n_expected', '?')}"
        elif name == "failure_rate":
            tag = "FAIL" if m.get("is_failure") else "OK"
            detail = f"conf={m.get('confidence', '?')} tag={tag} reasons={m.get('reasons', [])}"
        elif name == "entity_recall":
            detail = f"recalled={m.get('n_recalled', '?')}/{m.get('n_std_entities', '?')}"
        elif name == "confidence":
            detail = f"std_top={m.get('std_top_confidence', '?')} abs_diff={m.get('abs_diff', '?')} calibration={m.get('calibration', '?')}"
        elif name == "feedback_delta":
            detail = f"n_corrections={m.get('n_corrections', 0)} avg_Δ={m.get('avg_delta_confidence', 0):+.4f} max_Δ={m.get('max_delta', 0):+.4f}"
        else:
            detail = ""
        rows.append(f"<tr><td>{name}</td><td colspan='3'>{detail}</td></tr>")

    page_title = title or f"Quant Eval — {report.get('deid', '?')}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{page_title}</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", sans-serif; max-width: 1100px; margin: 24px auto; padding: 0 16px; color: #222; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 6px; }}
.meta {{ color: #666; font-size: 13px; margin: 6px 0 16px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ padding: 6px 10px; border: 1px solid #ddd; text-align: left; }}
th {{ background: #f5f5f5; }}
img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
</style>
</head>
<body>
<h1>{page_title}</h1>
<div class="meta">
  <b>deid</b>: <code>{report.get('deid', '?')}</code> ·
  <b>std_ts</b>: <code>{report.get('std_ts', '?')}</code> ·
  <b>dspy_ts</b>: <code>{report.get('dspy_ts', '?')}</code> ·
  <b>generated</b>: {report.get('generated_at', '?')}
</div>
<h2>6 指标可视化</h2>
<img src="data:image/png;base64,{b64}" alt="metrics chart">
<h2>指标详情</h2>
<table>
<thead><tr><th>metric</th><th colspan="3">value / detail</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</body>
</html>
"""


def render_trend_chart(reports: list[dict], *, title: str = "DSPy Metrics Trend") -> bytes:
    """Trend chart placeholder (multi-patient line chart, to be expanded later)."""
    fig = Figure(figsize=(10, 5), dpi=100)
    ax = fig.add_subplot(111)
    xs: list[str] = []
    ys: dict[str, list[float]] = {"f1": [], "coverage": [], "recall": [], "conf": []}
    for r in reports:
        xs.append(str(r.get("std_ts", "?")))
        m = r.get("metrics", {})
        ys["f1"].append((m.get("entity_f1") or {}).get("f1", 0.0))
        ys["coverage"].append((m.get("section_coverage") or {}).get("coverage_rate", 0.0))
        ys["recall"].append((m.get("entity_recall") or {}).get("recall_rate", 0.0))
        ys["conf"].append((m.get("confidence") or {}).get("dspy_confidence", 0.0))
    for name, y in ys.items():
        ax.plot(xs, y, marker="o", label=name)
    ax.set_ylim(0, 1.05)
    ax.set_title(title)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    return buf.getvalue()
