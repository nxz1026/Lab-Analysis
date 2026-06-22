#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quant_eval_gate.py — 6 指标阈值检查, CI gate 用

读 data/{id}/{ts}/04_reports/quant_eval_report.json, 对 6 指标逐个判定 PASS/FAIL,
exit 0 = 全 PASS, exit 1 = 任一 FAIL.

阈值 (默认):
    entity_f1.f1             >= 0.70
    section_coverage.rate    >= 0.80
    failure_rate.is_failure  == False
    entity_recall.rate       >= 0.70
    confidence.dspy_conf     >= 0.60
    feedback_delta.avg       [-0.30, +0.30]  (可选, available=False 跳过)

用法:
    # CI 模式 (默认, 阈值不达标 exit 1)
    python scripts/quant_eval_gate.py \\
        --id-card 846552421134373347 --std-ts 20260620_175252

    # 显式传 report 路径
    python scripts/quant_eval_gate.py --report-path data/X/Y/04_reports/quant_eval_report.json

    # 调整阈值
    python scripts/quant_eval_gate.py --id-card X --std-ts Y \\
        --f1-min 0.6 --coverage-min 0.7 --confidence-min 0.5

    # 只看 (--dry-run): 打印判定结果但不 exit 1
    python scripts/quant_eval_gate.py --id-card X --std-ts Y --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lab_analysis.utils import WORK_ROOT  # noqa: E402


# ── 阈值默认值 ──────────────────────────────────────────────

DEFAULT_THRESHOLDS: dict[str, float] = {
    "f1_min": 0.70,                # entity_f1.f1 下限
    "coverage_min": 0.80,          # section_coverage.coverage_rate 下限
    "recall_min": 0.70,            # entity_recall.recall_rate 下限
    "confidence_min": 0.60,        # confidence.dspy_confidence 下限
    "feedback_delta_abs_max": 0.30,  # |feedback_delta.avg_delta_confidence| 上限
}


@dataclass
class GateResult:
    """单个 metric 的判定结果"""

    metric: str
    passed: bool
    actual: Any = None
    threshold: Any = None
    reason: str = ""
    skipped: bool = False  # 标记该 metric 数据不可用, 跳过不计入 FAIL

    def to_dict(self) -> dict:
        return {
            "metric": self.metric,
            "passed": self.passed,
            "actual": self.actual,
            "threshold": self.threshold,
            "reason": self.reason,
            "skipped": self.skipped,
        }


@dataclass
class GateReport:
    """gate 整体判定结果"""

    overall_pass: bool
    results: list[GateResult] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "overall_pass": self.overall_pass,
            "n_total": len(self.results),
            # n_passed 只算真正 pass (不含 skip), 否则 skip 也会抬高数字
            "n_passed": sum(1 for r in self.results if r.passed and not r.skipped),
            "n_failed": sum(1 for r in self.results if not r.passed and not r.skipped),
            "n_skipped": sum(1 for r in self.results if r.skipped),
            "source": self.source,
            "results": [r.to_dict() for r in self.results],
        }


# ── 纯函数 (CI 单元测试覆盖) ───────────────────────────────


def check_entity_f1(metric: dict, *, f1_min: float) -> GateResult:
    if not metric.get("available"):
        return GateResult(
            metric="entity_f1", passed=True, skipped=True, reason=metric.get("reason", "N/A")
        )
    f1 = metric.get("f1", 0.0)
    return GateResult(
        metric="entity_f1",
        passed=f1 >= f1_min,
        actual=f1,
        threshold=f1_min,
        reason=f"f1={f1:.4f} {'≥' if f1 >= f1_min else '<'} {f1_min}",
    )


def check_section_coverage(metric: dict, *, coverage_min: float) -> GateResult:
    if not metric.get("available"):
        return GateResult(
            metric="section_coverage",
            passed=True,
            skipped=True,
            reason=metric.get("reason", "N/A"),
        )
    rate = metric.get("coverage_rate", 0.0)
    return GateResult(
        metric="section_coverage",
        passed=rate >= coverage_min,
        actual=rate,
        threshold=coverage_min,
        reason=f"coverage={rate:.4f} {'≥' if rate >= coverage_min else '<'} {coverage_min}",
    )


def check_failure_rate(metric: dict) -> GateResult:
    if not metric.get("available"):
        return GateResult(
            metric="failure_rate", passed=True, skipped=True, reason=metric.get("reason", "N/A")
        )
    is_fail = metric.get("is_failure", True)
    return GateResult(
        metric="failure_rate",
        passed=not is_fail,
        actual=is_fail,
        threshold=False,
        reason="is_failure=True" if is_fail else "is_failure=False (PASS)",
    )


def check_entity_recall(metric: dict, *, recall_min: float) -> GateResult:
    if not metric.get("available"):
        return GateResult(
            metric="entity_recall",
            passed=True,
            skipped=True,
            reason=metric.get("reason", "N/A"),
        )
    rate = metric.get("recall_rate", 0.0)
    return GateResult(
        metric="entity_recall",
        passed=rate >= recall_min,
        actual=rate,
        threshold=recall_min,
        reason=f"recall={rate:.4f} {'≥' if rate >= recall_min else '<'} {recall_min}",
    )


def check_confidence(metric: dict, *, confidence_min: float) -> GateResult:
    if not metric.get("available"):
        return GateResult(
            metric="confidence", passed=True, skipped=True, reason=metric.get("reason", "N/A")
        )
    conf = metric.get("dspy_confidence", 0.0)
    return GateResult(
        metric="confidence",
        passed=conf >= confidence_min,
        actual=conf,
        threshold=confidence_min,
        reason=f"dspy_conf={conf:.4f} {'≥' if conf >= confidence_min else '<'} {confidence_min}",
    )


def check_feedback_delta(metric: dict, *, abs_max: float) -> GateResult:
    if not metric.get("available"):
        return GateResult(
            metric="feedback_delta",
            passed=True,
            skipped=True,
            reason=metric.get("reason", "N/A"),
        )
    avg = metric.get("avg_delta_confidence", 0.0)
    return GateResult(
        metric="feedback_delta",
        passed=abs(avg) <= abs_max,
        actual=avg,
        threshold=f"|x| ≤ {abs_max}",
        reason=f"|{avg:.4f}| {'≤' if abs(avg) <= abs_max else '>'} {abs_max}",
    )


def evaluate(report: dict, *, thresholds: dict[str, float] | None = None) -> GateReport:
    """对单个 quant_eval_report.json 跑全部 6 指标阈值检查.

    Args:
        report:  quant_eval_report.json 解析后的 dict
        thresholds: 阈值 dict (默认用 DEFAULT_THRESHOLDS)

    Returns:
        GateReport 对象
    """
    thr = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    metrics = report.get("metrics", {})

    results: list[GateResult] = []
    results.append(check_entity_f1(metrics.get("entity_f1", {}), f1_min=thr["f1_min"]))
    results.append(
        check_section_coverage(
            metrics.get("section_coverage", {}), coverage_min=thr["coverage_min"]
        )
    )
    results.append(check_failure_rate(metrics.get("failure_rate", {})))
    results.append(
        check_entity_recall(metrics.get("entity_recall", {}), recall_min=thr["recall_min"])
    )
    results.append(
        check_confidence(metrics.get("confidence", {}), confidence_min=thr["confidence_min"])
    )
    results.append(
        check_feedback_delta(
            metrics.get("feedback_delta", {}), abs_max=thr["feedback_delta_abs_max"]
        )
    )

    overall = all(r.passed for r in results)
    return GateReport(
        overall_pass=overall,
        results=results,
        source=report.get("deid", "") or "(unknown)",
    )


# ── 入口 ──────────────────────────────────────────────────


def _resolve_report_path(id_card: str | None, std_ts: str | None, report_path: str | None) -> Path:
    if report_path:
        p = Path(report_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p
    if not id_card or not std_ts:
        raise ValueError("需要 --id-card + --std-ts, 或 --report-path")
    return WORK_ROOT / "data" / id_card / std_ts / "04_reports" / "quant_eval_report.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="DSPy 6 指标阈值检查 (CI gate)")
    parser.add_argument("--id-card", help="脱敏患者 ID")
    parser.add_argument("--std-ts", help="std 模式时间戳")
    parser.add_argument("--report-path", help="直接指定 quant_eval_report.json 路径")
    parser.add_argument("--f1-min", type=float, default=DEFAULT_THRESHOLDS["f1_min"])
    parser.add_argument("--coverage-min", type=float, default=DEFAULT_THRESHOLDS["coverage_min"])
    parser.add_argument("--recall-min", type=float, default=DEFAULT_THRESHOLDS["recall_min"])
    parser.add_argument("--confidence-min", type=float, default=DEFAULT_THRESHOLDS["confidence_min"])
    parser.add_argument(
        "--feedback-delta-abs-max",
        type=float,
        default=DEFAULT_THRESHOLDS["feedback_delta_abs_max"],
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印判定结果, 不管 PASS/FAIL 都 exit 0 (用于 PR comment)",
    )
    args = parser.parse_args()

    thresholds = {
        "f1_min": args.f1_min,
        "coverage_min": args.coverage_min,
        "recall_min": args.recall_min,
        "confidence_min": args.confidence_min,
        "feedback_delta_abs_max": args.feedback_delta_abs_max,
    }

    try:
        rp = _resolve_report_path(args.id_card, args.std_ts, args.report_path)
    except ValueError as e:
        print(f"[错误] {e}")
        return 2

    if not rp.exists():
        print(f"[错误] report 不存在: {rp}")
        print("提示: 先跑 python examples/dspy_quant_eval.py --id-card X --std-ts Y --batch")
        return 2

    try:
        report = json.loads(rp.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[错误] report 解析失败: {e}")
        return 2

    gate = evaluate(report, thresholds=thresholds)
    out = gate.to_dict()

    print("=" * 72)
    print(f"  quant_eval_gate — {rp.name}")
    print(f"  source: {gate.source}")
    print("=" * 72)
    for r in gate.results:
        tag = "SKIP" if r.skipped else ("PASS" if r.passed else "FAIL")
        print(f"  [{tag:4s}] {r.metric:20s}  {r.reason}")
    print("-" * 72)
    summary = f"{out['n_passed']}/{out['n_total']} passed, {out['n_failed']} failed, {out['n_skipped']} skipped"
    tag = "✅ PASS" if gate.overall_pass else "❌ FAIL"
    print(f"  {tag}  {summary}")
    print("=" * 72)

    # 写 sidecar JSON (CI artifact)
    sidecar = rp.parent / "quant_eval_gate_result.json"
    sidecar.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dry_run:
        return 0
    return 0 if gate.overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
