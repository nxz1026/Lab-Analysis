#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dspy_quant_eval.py — DSPy vs Standard 报告 6 指标量化评估

覆盖指标 (按 DSPy 量化评估规范):
    1. 关键实体 F1            (std 报告作为 ground truth, 看 dspy 召回率)
    2. 章节覆盖度             (9 个 section 哪些非空)
    3. DSPy 失败率            (confidence < 0.6 / 缺失 / 全空)
    4. 实体召回率细分         (dspy 召回了 std 报告的哪些关键实体)
    5. 置信度分布 & 校准      (dspy.confidence + std 评分卡一致性)
    6. 人工反馈 Δconfidence   (来自 feedback.json corrections 列表)

友好降级:
    - ground truth 缺失时 (如无 feedback.json) 标 N/A 而不是报错
    - dspy 报告 confidence 缺失时 (历史跑) 标 N/A

用法:
    # 被 dual_mode_pipeline 自动调用
    python examples/dual_mode_pipeline.py --id-card X --auto-pick --quant

    # 独立运行
    python examples/dspy_quant_eval.py \\
        --id-card 846552421134373347 --std-ts 20260620_175252 --dspy-ts 20260620_175730

    # 全患者批量 (扫描 data/{deid}/ 找最近 std+dspy)
    python examples/dspy_quant_eval.py --batch
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 6 个 metric 纯函数从 lab_analysis.quant_metrics 复用 (便于 CI 单元测试)
# 工具函数
from lab_analysis.quant_metrics import (  # noqa: E402
    metric_confidence,
    metric_entity_f1,
    metric_entity_recall_breakdown,
    metric_failure_rate,
    metric_feedback_delta,
    metric_section_coverage,
)
from lab_analysis.quant_visualizer import (  # noqa: E402
    render_metrics_chart,
    render_metrics_html,
)
from lab_analysis.utils import WORK_ROOT  # noqa: E402


# 工具函数 (本文件独有, quant_metrics.py 不提供)
def _load_text(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def _load_json(p: Path) -> dict:
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


# ── 编排 ──────────────────────────────────────────────────


def _load_run_artifacts(deid: str, std_ts: str, dspy_ts: str) -> dict[str, Any]:
    """加载 std + dspy 两次跑的所有可用产物。"""
    base = WORK_ROOT / "data" / deid

    std_md = base / std_ts / "04_reports" / "final_integrated_report.md"
    dspy_json = base / dspy_ts / "04_reports" / "final_integrated_report.json"
    std_scoring = base / std_ts / "04_reports" / "scoring_card.json"
    feedback = base / "feedback.json"

    dspy_data = _load_json(dspy_json)
    dspy_sections = dspy_data.get("sections", {}) if dspy_data else {}

    return {
        "deid": deid,
        "std_ts": std_ts,
        "dspy_ts": dspy_ts,
        "std_text": _load_text(std_md),
        "dspy_text": _load_text(dspy_json),  # 全文文本
        "dspy_data": dspy_data,
        "dspy_sections": dspy_sections,
        "std_scoring": _load_json(std_scoring),
        "feedback": _load_json(feedback),
    }


def _format_md(report: dict) -> str:
    """将量化报告渲染为 Markdown。"""
    lines: list[str] = [
        "# DSPy 量化评估报告",
        "",
        f"**患者**: `{report['deid']}`",
        f"**std 时间戳**: `{report['std_ts']}`",
        f"**dspy 时间戳**: `{report['dspy_ts']}`",
        f"**生成时间**: {report['generated_at']}",
        "",
        "## 1. 关键实体 F1",
        "",
    ]
    m1 = report["metrics"]["entity_f1"]
    if m1.get("available"):
        lines += [
            f"- TP/FP/FN: {m1['tp']}/{m1['fp']}/{m1['fn']}",
            f"- Precision: {m1['precision']:.2%}",
            f"- Recall:    {m1['recall']:.2%}",
            f"- F1:        {m1['f1']:.2%}",
            f"- 实体总数:  {m1['n_entities']}",
        ]
    else:
        lines.append(f"- 不可用: {m1.get('reason', '?')}")

    lines += ["", "## 2. 章节覆盖度", ""]
    m2 = report["metrics"]["section_coverage"]
    if m2.get("available"):
        lines += [
            f"- 非空章节: {m2['n_nonempty']}/{m2['n_expected']}",
            f"- 覆盖率:   {m2['coverage_rate']:.2%}",
            "",
            "| 章节 | 非空 | 字符数 |",
            "|------|------|--------|",
        ]
        for k, v in m2["per_section"].items():
            lines.append(f"| {k} | {'✓' if v['nonempty'] else '✗'} | {v['length']} |")
    else:
        lines.append(f"- 不可用: {m2.get('reason', '?')}")

    lines += ["", "## 3. DSPy 失败率", ""]
    m3 = report["metrics"]["failure_rate"]
    if m3.get("available"):
        lines += [
            f"- confidence: {m3['confidence']}",
            f"- 是否失败:   {'**是**' if m3['is_failure'] else '否'}",
            f"- 原因:       {', '.join(m3['reasons']) if m3['reasons'] else '(无)'}",
        ]

    lines += ["", "## 4. 实体召回细分", ""]
    m4 = report["metrics"]["entity_recall"]
    if m4.get("available"):
        lines += [
            f"- std 实体数: {m4['n_std_entities']}",
            f"- 召回数:     {m4['n_recalled']}",
            f"- 召回率:     {m4['recall_rate']:.2%}",
            f"- 召回: {', '.join(m4['recalled']) if m4['recalled'] else '(无)'}",
            f"- 漏掉: {', '.join(m4['missed']) if m4['missed'] else '(无)'}",
        ]
    else:
        lines.append(f"- 不可用: {m4.get('reason', '?')}")

    lines += ["", "## 5. 置信度校准", ""]
    m5 = report["metrics"]["confidence"]
    if m5.get("available"):
        lines += [
            f"- dspy.confidence:      {m5['dspy_confidence']}",
            f"- std 评分卡 top.conf:  {m5['std_top_confidence']}",
            f"- 绝对差:               {m5.get('abs_diff', 'N/A')}",
            f"- 校准评级:             {m5['calibration']}",
        ]
    else:
        lines.append(f"- 不可用: {m5.get('reason', '?')}")

    lines += ["", "## 6. 人工反馈 Δconfidence", ""]
    m6 = report["metrics"]["feedback_delta"]
    if m6.get("available"):
        lines += [
            f"- 纠错次数:        {m6['n_corrections']}",
            f"- 重写假设次数:    {m6['n_rewrites']}",
            f"- 平均 Δ:          {m6['avg_delta_confidence']:+.4f}",
            f"- 最大 Δ:          {m6['max_delta']:+.4f}",
            f"- 最小 Δ:          {m6['min_delta']:+.4f}",
        ]
        adj = m6.get("adjustments", {})
        if adj:
            lines += ["", "### 自动置信度调整", ""]
            for k, v in adj.items():
                lines.append(f"- `{k}`: {v:+.2f}")
    else:
        lines.append(f"- 不可用: {m6.get('reason', '?')}")

    return "\n".join(lines) + "\n"


def run(
    id_card: str,
    std_ts: str,
    dspy_ts: str,
    out_dir: Path | None = None,
) -> dict:
    """主入口: 跑 6 指标 → 写 JSON+MD → 返回 report dict。

    可被 dual_mode_pipeline.py 调用,也可 CLI 独立运行。
    """
    arts = _load_run_artifacts(id_card, std_ts, dspy_ts)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "deid": id_card,
        "std_ts": std_ts,
        "dspy_ts": dspy_ts,
        "metrics": {
            "entity_f1": metric_entity_f1(arts["std_text"], arts["dspy_text"]),
            "section_coverage": metric_section_coverage(arts["dspy_sections"]),
            "failure_rate": metric_failure_rate(arts["dspy_data"], arts["dspy_sections"]),
            "entity_recall": metric_entity_recall_breakdown(arts["std_text"], arts["dspy_text"]),
            "confidence": metric_confidence(arts["dspy_data"], arts["std_scoring"]),
            "feedback_delta": metric_feedback_delta(arts["feedback"]),
        },
    }

    if out_dir is None:
        out_dir = WORK_ROOT / "data" / id_card / std_ts / "04_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "quant_eval_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "quant_eval_report.md").write_text(_format_md(report), encoding="utf-8")

    # 可视化产物: PNG 条形图 + HTML 单文件报告
    try:
        chart_bytes = render_metrics_chart(report["metrics"])
        (out_dir / "quant_eval_chart.png").write_bytes(chart_bytes)
        html = render_metrics_html(report, chart_bytes=chart_bytes)
        (out_dir / "quant_eval_report.html").write_text(html, encoding="utf-8")
        print(f"  [visual] PNG={len(chart_bytes)}B + HTML={len(html)}B 已保存")
    except Exception as e:
        # 可视化失败不影响主报告 (md/json)
        print(f"  [visual-warn] 可视化失败: {e}")

    print(f"  [quant] 报告已保存: {out_dir}/quant_eval_report.{{json,md}}")
    return report


def _print_summary(report: dict) -> None:
    print()
    print("=" * 72)
    print(f"  量化评估摘要: {report['deid']}")
    print("=" * 72)
    for name, m in report["metrics"].items():
        if not m.get("available"):
            print(f"  {name:25s}  N/A: {m.get('reason', '?')}")
            continue
        if name == "entity_f1":
            print(f"  {name:25s}  P={m['precision']:.2%} R={m['recall']:.2%} F1={m['f1']:.2%}")
        elif name == "section_coverage":
            print(f"  {name:25s}  {m['n_nonempty']}/{m['n_expected']} ({m['coverage_rate']:.2%})")
        elif name == "failure_rate":
            tag = "FAIL" if m["is_failure"] else "OK"
            print(f"  {name:25s}  {tag} (conf={m['confidence']})")
        elif name == "entity_recall":
            print(f"  {name:25s}  {m['n_recalled']}/{m['n_std_entities']} ({m['recall_rate']:.2%})")
        elif name == "confidence":
            print(f"  {name:25s}  {m['calibration']} (diff={m.get('abs_diff', '?')})")
        elif name == "feedback_delta":
            print(f"  {name:25s}  n={m['n_corrections']} avg_Δ={m['avg_delta_confidence']:+.4f}")


def main() -> int:
    parser = argparse.ArgumentParser(description="DSPy 6 指标量化评估")
    parser.add_argument("--id-card", required=True, help="脱敏患者 ID")
    parser.add_argument("--std-ts", help="std 模式时间戳")
    parser.add_argument("--dspy-ts", help="dspy 模式时间戳")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="扫描 data/{deid}/ 自动选最近 std+dspy (当前仅处理单个)",
    )
    args = parser.parse_args()

    if not args.std_ts or not args.dspy_ts:
        # 简化: 当前 batch 模式只处理第一个患者的最近两次
        if args.batch:
            from examples.dual_mode_pipeline import _auto_pick_runs

            std_ts, dspy_ts = _auto_pick_runs(args.id_card)
            if not std_ts or not dspy_ts:
                print(f"[错误] auto-pick 失败 std={std_ts} dspy={dspy_ts}")
                return 1
            print(f"[auto-pick] std={std_ts} dspy={dspy_ts}")
        else:
            parser.error("需要 --std-ts 和 --dspy-ts,或 --batch")

    report = run(args.id_card, args.std_ts, args.dspy_ts)
    _print_summary(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
