"""scoring_card.hypotheses — 诊断假设推理引擎。

维护 DIAGNOSTIC_RULES 表 + 评估 + 信号收集。
"""

from __future__ import annotations

from collections.abc import Callable

from .dimensions import score_imaging_consistency, score_literature_support
from .types import DimensionScores, Hypothesis


def _is_acute(labels: list[str]) -> bool:
    return "急性期" in labels[-3:] if labels else False


def _has_trend(results: dict, metric: str, direction: str = "上升") -> bool:
    reg = results.get("linear_regression", {})
    m = reg.get(metric, {})
    return m.get("trend") == direction and m.get("r2", 0) >= 0.6


# 诊断规则： (名称, 条件函数, 假设文本, 建议动作, 置信度增量)
DIAGNOSTIC_RULES: list[tuple[str, Callable, str, list[str], float]] = [
    (
        "chronic_pancreatitis_active",
        lambda r, a, l, m: (
            _is_acute(r.get("inflammation_classification", {}).get("labels", []))
            and _has_trend(r, "hs-CRP", "上升")
        ),
        "慢性胰腺炎（活动期）",
        ["建议复查淀粉酶/脂肪酶", "影像学随访评估胰腺形态变化", "考虑抗炎治疗或胰酶替代治疗"],
        0.30,
    ),
    (
        "chronic_pancreatitis_remission",
        lambda r, a, l, m: (
            "缓解期" in r.get("inflammation_classification", {}).get("labels", [])
            and len(r.get("inflammation_classification", {}).get("labels", [])) >= 3
        ),
        "慢性胰腺炎（缓解期）",
        ["继续目前维持治疗方案", "定期监测 hs-CRP 及炎症指标"],
        0.20,
    ),
    (
        "systemic_inflammation_infection",
        lambda r, a, l, m: (
            _is_acute(r.get("inflammation_classification", {}).get("labels", []))
            and ("WBC" in r.get("abnormal_summary", {}) or "NEUT#" in r.get("abnormal_summary", {}))
        ),
        "系统性炎症/感染",
        ["建议 PCT 检测鉴别细菌感染", "血培养 + 感染灶筛查", "根据病原学结果调整抗生素"],
        0.25,
    ),
    (
        "high_variability_risk",
        lambda r, a, l, m: (
            sum(1 for v in r.get("cv_stability", {}).values() if v.get("risk_level") == "高") >= 3
        ),
        "指标波动显著（需关注稳定性）",
        ["增加复查频率", "排查影响指标波动的干扰因素", "考虑短期固定时间点复查以减少变异"],
        0.10,
    ),
    (
        "imaging_lab_conflict",
        lambda r, a, l, m: score_imaging_consistency(m) < 40,
        "影像-检验结论不一致",
        ["建议复核影像资料与原始检验报告", "多学科会诊评估一致性"],
        0.0,
    ),
    (
        "literature_well_supported",
        lambda r, a, l, m: score_literature_support(l) >= 70,
        "文献证据充分支持当前诊疗方向",
        ["继续遵循循证指南制定治疗方案"],
        0.15,
    ),
    (
        "rdw_elevated_only",
        lambda r, a, l, m: (
            "RDW-SD" in r.get("abnormal_summary", {})
            and "hs-CRP" not in r.get("abnormal_summary", {})
            and "CRP" not in r.get("abnormal_summary", {})
            and "WBC" not in r.get("abnormal_summary", {})
        ),
        "非炎症性血液系统异常",
        ["建议完善贫血相关检查（铁蛋白、VitB12、叶酸）", "排查慢性病贫血或骨髓造血功能"],
        0.10,
    ),
]


def _collect_supporting_signals(results: dict, alerts: list[dict], rule_name: str) -> list[str]:
    """收集支持假设的信号。"""
    signals: list[str] = []

    # 来自 alerts
    for a in alerts[:5]:
        signals.append(a.get("message", ""))

    # 来自 inflammation
    inflam = results.get("inflammation_classification", {})
    labels = inflam.get("labels", [])
    dates = inflam.get("report_dates", [])
    for d, lbl in zip(dates, labels, strict=True):
        signals.append(f"{d}: {lbl}")

    # 来自 trend
    reg = results.get("linear_regression", {})
    for metric, info in reg.items():
        if info.get("r2", 0) >= 0.7:
            signals.append(f"{metric} {info['trend']}（slope={info['slope']:.3f}）")

    return signals[:8]


def _collect_contradicting_signals(results: dict, rule_name: str) -> list[str]:
    """收集与假设矛盾的信号。"""
    signals: list[str] = []

    reg = results.get("linear_regression", {})
    for metric, info in reg.items():
        if info.get("trend") == "下降" and info.get("r2", 0) >= 0.7:
            signals.append(f"{metric} 呈下降趋势，炎症可能缓解")

    return signals[:4]


def evaluate_hypotheses(
    results: dict,
    alerts: list[dict],
    lit_filtered: dict,
    mri_results: dict,
    dim_scores: DimensionScores,
    confidence_adjustments: dict[str, float] | None = None,
) -> list[Hypothesis]:
    """运行诊断规则，返回按置信度排序的假设列表。

    Args:
        confidence_adjustments: 可选，来自 feedback.py 的规则置信度调整表。
            ``{rule_name: delta}``，正值上调，负值下调。
    """
    hypotheses: list[Hypothesis] = []
    adjustments = confidence_adjustments or {}

    for rule_name, condition_fn, hypothesis_text, actions, base_confidence in DIAGNOSTIC_RULES:
        try:
            matched = condition_fn(results, alerts, lit_filtered, mri_results)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            matched = False

        if not matched:
            continue

        # 从 5 维评分计算置信度调整
        # 炎症权重最大，文献和影像次之
        dim_avg = (
            dim_scores.get("inflammation", 50) * 0.35
            + dim_scores.get("lab_abnormality", 50) * 0.20
            + dim_scores.get("literature_support", 50) * 0.20
            + dim_scores.get("imaging_consistency", 50) * 0.15
            + dim_scores.get("variability_stability", 50) * 0.10
        ) / 100.0

        confidence = min(0.95, max(0.10, dim_avg + base_confidence))

        # 来自 feedback.py 的置信度调整
        fb_adj = adjustments.get(rule_name, 0.0)
        if fb_adj:
            confidence = min(0.95, max(0.05, confidence + fb_adj))

        # 支持/矛盾信号
        supporting = _collect_supporting_signals(results, alerts, rule_name)
        contradicting = _collect_contradicting_signals(results, rule_name)

        hypotheses.append(
            {
                "hypothesis": hypothesis_text,
                "confidence": round(confidence, 3),
                "supporting_signals": supporting,
                "contradicting_signals": contradicting,
                "suggested_actions": actions,
            }
        )

    hypotheses.sort(key=lambda h: h["confidence"], reverse=True)
    return hypotheses[:3]


def generate_overall_assessment(
    dim_scores: DimensionScores,
    hypotheses: list[Hypothesis],
) -> str:
    """生成一段综合评估文本。"""
    parts: list[str] = []
    avg = sum(dim_scores.values()) / len(dim_scores) if dim_scores else 0

    if avg >= 70:
        parts.append("综合多源数据，各项评分较高，整体情况可控。")
    elif avg >= 40:
        parts.append("综合多源数据，存在部分异常信号，需要关注。")
    else:
        parts.append("综合多源数据，多项指标异常，建议尽快临床干预。")

    if hypotheses:
        top = hypotheses[0]
        parts.append(f"主要诊断假设：{top['hypothesis']}（置信度 {top['confidence']:.0%}）。")

    inflam = dim_scores.get("inflammation", 0)
    if inflam >= 70:
        parts.append("炎症活动度较高，建议优先控制炎症。")
    elif inflam <= 30:
        parts.append("炎症处于缓解期，维持当前方案。")

    return " ".join(parts)
