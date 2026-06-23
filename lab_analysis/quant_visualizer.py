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
    "cross_modality_consistency": (0.70, "cross_modality ≥ 0.70"),
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
    if name == "cross_modality_consistency":
        # accuracy 0-1, 越高越好; 不达标返 0 不掩盖数据缺失
        return float(metric.get("accuracy", 0.0)), True
    return None, False


def render_metrics_chart(
    metrics: dict[str, dict],
    *,
    thresholds: dict[str, tuple[float, str]] | None = None,
    title: str = "DSPy 6-Metric Quant Eval",
    figsize: tuple[float, float] = (12, 6),
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

    # failure_rate 二元: 在主图右上角标注 OK/FAIL (避免 twinx 覆盖主图 X tick)
    if fr_ok and fr_val is not None:
        fail_text = "FAIL" if fr_val == 1 else "OK"
        fail_color = "#d62728" if fr_val == 1 else "#2ca02c"
        ax.text(
            0.98,
            0.96,
            f"failure_rate: {fail_text}",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=11,
            fontweight="bold",
            color=fail_color,
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=fail_color, alpha=0.9),  # noqa: C408
        )

    # 主条形图
    bars = ax.bar(names, values, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    for bar, thr_v, _label in zip(bars, threshold_lines, names, strict=False):
        ax.hlines(
            thr_v,
            bar.get_x(),
            bar.get_x() + bar.get_width(),
            colors="blue",
            linestyles="--",
            linewidth=1.2,
        )
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Metric Value (0~1)")
    ax.set_title(title, fontsize=12, pad=10)
    ax.grid(axis="y", alpha=0.3)
    ax.tick_params(axis="x", labelsize=10)
    for tick in ax.get_xticklabels():
        tick.set_rotation(15)
        tick.set_ha("right")  # type: ignore[attr-defined]

    # 数值标签
    for bar, v in zip(bars, values, strict=False):
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

    # 用 subplots_adjust 给 X label 留空间, 不用 bbox_inches="tight" 避免裁掉
    fig.subplots_adjust(left=0.08, right=0.92, top=0.92, bottom=0.25)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100)
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
        chart_bytes = render_metrics_chart(
            report.get("metrics", {}), title=f"量化评估: {report.get('deid', '?')}"
        )

    b64 = base64.b64encode(chart_bytes).decode("ascii")
    metrics = report.get("metrics", {})
    blocks: list[str] = []
    for name, m in metrics.items():
        if not m.get("available"):
            reason = m.get("reason", "?")
            blocks.append(
                f'<details><summary><span class="passed-skip">{name}</span> — '
                f'<span style="color:#888">N/A</span></summary>'
                f'<div class="detail-body">{reason}</div></details>'
            )
            continue
        if name == "entity_f1":
            tag = "OK" if m.get("f1", 0) >= 0.7 else "FAIL"
            detail = (
                f"tp={m.get('tp', '?')} fp={m.get('fp', '?')} fn={m.get('fn', '?')}  |  "
                f"prec={m.get('precision', 0):.2%}  rec={m.get('recall', 0):.2%}  f1={m.get('f1', 0):.4f}"
            )
        elif name == "section_coverage":
            cov = m.get("coverage_rate", 0)
            tag = "OK" if cov >= 0.8 else "FAIL"
            detail = f"non-empty={m.get('n_nonempty', '?')}/{m.get('n_expected', '?')}  |  rate={cov:.2%}"
        elif name == "failure_rate":
            tag = "FAIL" if m.get("is_failure") else "OK"
            detail = f"conf={m.get('confidence', '?')}  tag={tag}  reasons={m.get('reasons', [])}"
        elif name == "entity_recall":
            rec = m.get("recall_rate", 0)
            tag = "OK" if rec >= 0.7 else "FAIL"
            detail = f"recalled={m.get('n_recalled', '?')}/{m.get('n_std_entities', '?')}  |  rate={rec:.2%}"
        elif name == "confidence":
            conf = m.get("dspy_confidence", 0)
            tag = "OK" if conf >= 0.6 else "FAIL"
            detail = (
                f"std_top={m.get('std_top_confidence', '?')}  "
                f"abs_diff={m.get('abs_diff', '?')}  calibration={m.get('calibration', '?')}"
            )
        elif name == "feedback_delta":
            tag = "SKIP"
            detail = (
                f"n_corrections={m.get('n_corrections', 0)}  "
                f"avg_Δ={m.get('avg_delta_confidence', 0):+.4f}  "
                f"max_Δ={m.get('max_delta', 0):+.4f}"
            )
        elif name == "cross_modality_consistency":
            acc = m.get("accuracy", 0.0)
            tag = "OK" if acc >= 0.7 else "FAIL"
            detail = (
                f"accuracy={acc:.4f}  "
                f"mentions_top_hypo={m.get('mentions_top_hypothesis', False)}  "
                f"mentions_key_entity={m.get('mentions_key_entity', False)}  "
                f"matched={m.get('matched_entities', [])}"
            )
        else:
            tag = "?"
            detail = ""
        css_class = (
            "passed-ok" if tag == "OK" else "passed-fail" if tag == "FAIL" else "passed-skip"
        )
        blocks.append(
            f'<details><summary><span class="{css_class}">{tag}</span> '
            f"<strong>{name}</strong></summary>"
            f'<div class="detail-body">{detail}</div></details>'
        )

    page_title = title or f"Quant Eval — {report.get('deid', '?')}"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{page_title}</title>
<style>
/* Print/PDF 按钮 (默认显示, 打印时隐藏) */
.print-btn {{
  position: fixed; top: 16px; right: 16px;
  padding: 8px 16px; font-size: 14px; font-weight: 600;
  background: #2ca02c; color: white; border: 0;
  border-radius: 4px; cursor: pointer;
  box-shadow: 0 2px 4px rgba(0,0,0,0.15);
  z-index: 999;
}}
.print-btn:hover {{ background: #228a22; }}
@media print {{
  .print-btn {{ display: none; }}
  body {{ max-width: none; padding: 0; }}
  details[open] {{ page-break-inside: avoid; }}
  details:not([open]) summary {{ display: block; }}
  details .detail-body {{ display: block !important; }}
}}

body {{ font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
       max-width: 1100px; margin: 24px auto; padding: 0 16px; color: #222; line-height: 1.5; }}
@media (max-width: 720px) {{
  body {{ font-size: 14px; padding: 0 10px; }}
  h1 {{ font-size: 20px; }}
  details .detail-body {{ font-size: 11px; }}
}}
@media (prefers-color-scheme: dark) {{
  body {{ background: #1a1a1a; color: #e0e0e0; }}
  .meta {{ color: #aaa; }}
  .meta code {{ background: #2a2a2a; color: #e0e0e0; }}
  th {{ background: #2a2a2a; }}
  th, td {{ border-color: #444; }}
  details {{ background: #222; border-color: #444; }}
  details[open] {{ background: #2a2a2a; }}
  details summary:hover {{ background: #333; }}
}}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 6px; }}
.meta {{ color: #666; font-size: 13px; margin: 6px 0 16px; }}
.meta code {{ background: #f5f5f5; padding: 1px 6px; border-radius: 3px; }}
img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px; display: block; margin: 12px 0; }}
/* 折叠详情: 初始噪音少, 点击展开 */
details {{ margin: 6px 0; border: 1px solid #e0e0e0; border-radius: 4px; background: #fafafa; }}
details[open] {{ background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
summary {{ padding: 8px 12px; cursor: pointer; font-weight: 600; user-select: none; list-style: none; }}
summary::-webkit-details-marker {{ display: none; }}
summary::before {{ content: "\\25B6  "; color: #888; font-size: 10px; margin-right: 6px; }}
details[open] summary::before {{ content: "\\25BC  "; }}
summary:hover {{ background: #f0f0f0; }}
.detail-body {{ padding: 0 12px 10px 28px; font-size: 12px; color: #555;
  font-family: ui-monospace, "Cascadia Code", Consolas, monospace; }}
.passed-ok {{ color: #2ca02c; font-weight: 600; }}
.passed-fail {{ color: #d62728; font-weight: 600; }}
.passed-skip {{ color: #888; font-style: italic; }}
</style>
</head>
<body>
<h1>{page_title}</h1>
<button class="print-btn" onclick="window.print()">Print / Save as PDF</button>
<div class="meta">
  <b>deid</b>: <code>{report.get("deid", "?")}</code> ·
  <b>std_ts</b>: <code>{report.get("std_ts", "?")}</code> ·
  <b>dspy_ts</b>: <code>{report.get("dspy_ts", "?")}</code> ·
  <b>generated</b>: {report.get("generated_at", "?")}
</div>
<h2>6 指标可视化</h2>
<img src="data:image/png;base64,{b64}" alt="metrics chart">
<h2>指标详情 (点击展开)</h2>
{"".join(blocks)}
</body>
</html>
"""


def render_trend_chart(
    reports: list[dict],
    *,
    title: str = "DSPy Metrics Trend (multi-run)",
    figsize: tuple[float, float] = (12, 6),
    x_key: str = "std_ts",
) -> bytes:
    """多 run 趋势图: 4 metric 折线 + 阈值参考线.

    Args:
        reports: list of quant_eval_report.json dict (按时间顺序)
        title: 图标题
        figsize: (宽, 高) 英寸
        x_key: X 轴 label 取哪个 key ('std_ts' / 'dspy_ts' / 'deid')

    Returns:
        PNG bytes
    """
    if not reports:
        raise ValueError("reports 不能为空")

    fig = Figure(figsize=figsize, dpi=100)
    ax = fig.add_subplot(111)
    xs: list[str] = []
    ys: dict[str, list[float]] = {"f1": [], "coverage": [], "recall": [], "conf": []}
    for r in reports:
        xs.append(str(r.get(x_key, "?")))
        m = r.get("metrics", {}) or {}
        ys["f1"].append(float((m.get("entity_f1") or {}).get("f1") or 0.0))
        ys["coverage"].append(float((m.get("section_coverage") or {}).get("coverage_rate") or 0.0))
        ys["recall"].append(float((m.get("entity_recall") or {}).get("recall_rate") or 0.0))
        ys["conf"].append(float((m.get("confidence") or {}).get("dspy_confidence") or 0.0))

    colors = {"f1": "#1f77b4", "coverage": "#2ca02c", "recall": "#ff7f0e", "conf": "#9467bd"}
    for name, y in ys.items():
        ax.plot(xs, y, marker="o", label=name, color=colors[name], linewidth=2, markersize=7)
        for i, yi in enumerate(y):
            if yi > 0:
                ax.annotate(
                    f"{yi:.2f}",
                    (i, yi),
                    textcoords="offset points",
                    xytext=(0, 6),
                    ha="center",
                    fontsize=7,
                    color=colors[name],
                )

    # 阈值参考线 (与 DEFAULT_THRESHOLDS 对齐)
    ax.axhline(0.70, color=colors["f1"], linestyle=":", alpha=0.4)
    ax.axhline(0.80, color=colors["coverage"], linestyle=":", alpha=0.4)

    ax.set_ylim(0, 1.10)
    ax.set_xlabel(x_key)
    ax.set_ylabel("Metric Value (0~1)")
    ax.set_title(title, fontsize=12, pad=10)
    ax.legend(loc="lower right", fontsize=9, ncol=4)
    ax.grid(alpha=0.3)
    for tick in ax.get_xticklabels():
        tick.set_rotation(20)
        tick.set_ha("right")  # type: ignore[attr-defined]

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    return buf.getvalue()
