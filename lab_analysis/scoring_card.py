"""scoring_card.py — 评分卡 & 临床决策支持

综合检验数据、文献证据、影像印证、变异风险等多源信息，
输出 5 维评分 + 加权诊断假设列表（top-3），辅助临床决策。

纯规则引擎，不调 LLM，可重复可测试。

用法:
    python -m lab_analysis.scoring_card --id-card <deid>
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lab_analysis.utils import WORK_ROOT

# ═════════════════════════════════════════════════════════════════════════
# 类型定义
# ═════════════════════════════════════════════════════════════════════════

Hypothesis = dict[str, Any]
"""诊断假设结构:
- hypothesis: str
- confidence: float (0-1)
- supporting_signals: list[str]
- contradicting_signals: list[str]
- suggested_actions: list[str]
"""

DimensionScores = dict[str, float]
"""评分字典: {维度名: 0-100}"""

ScoringResult = dict[str, Any]
"""完整评分卡结果，包含:
- generated, patient_id
- dimension_scores: DimensionScores
- top_hypotheses: list[Hypothesis]
- overall_assessment: str
- data_quality: dict
"""


# ═════════════════════════════════════════════════════════════════════════
# 5 维评分函数
# ═════════════════════════════════════════════════════════════════════════


def score_inflammation(results: dict) -> float:
    """炎症活动度评分 (0-100)。

    基于 hs-CRP 分期、趋势、急性期占比。
    """
    inflam = results.get("inflammation_classification", {})
    labels = inflam.get("labels", [])
    reg = results.get("linear_regression", {})

    score = 50.0  # 基线

    # 最近一次炎症分期
    if labels:
        latest = labels[-1]
        if latest == "急性期":
            score += 30
        elif latest == "过渡期":
            score += 10
        elif latest == "缓解期":
            score -= 10

    # hs-CRP 趋势
    hs_crp = reg.get("hs-CRP", {})
    if hs_crp.get("trend") == "上升" and hs_crp.get("r2", 0) >= 0.7:
        score += 15
    elif hs_crp.get("trend") == "下降" and hs_crp.get("r2", 0) >= 0.7:
        score -= 10

    # 急性期占比
    if labels:
        acute_ratio = labels.count("急性期") / len(labels)
        score += acute_ratio * 20

    return max(0.0, min(100.0, score))


def score_lab_abnormality(results: dict, alerts: list[dict]) -> float:
    """实验室异常度评分 (0-100)。

    基于异常指标数量、Z-score 严重异常、告警级别。
    """
    abnormal = results.get("abnormal_summary", {})
    zscores = results.get("zscore_outliers", {})

    score = 0.0

    # 异常指标数量（最多 40 分）
    n_abnormal = len(abnormal)
    score += min(40, n_abnormal * 8)

    # 严重 Z-score 异常（最多 30 分）
    for _metric, info in zscores.items():
        severe = info.get("outliers_severe", {})
        score += min(30, severe.get("count", 0) * 15)

    # CRITICAL 告警（最多 30 分）
    n_critical = sum(1 for a in alerts if a.get("level") == "CRITICAL")
    score += min(30, n_critical * 10)

    return max(0.0, min(100.0, score))


def score_literature_support(lit_filtered: dict) -> float:
    """文献证据支持度评分 (0-100)。

    基于 top 论文的 tier 加权平均。
    """
    papers = lit_filtered.get("filtered_papers", [])
    if not papers:
        return 0.0

    tier_weights = {"S": 1.0, "A": 0.8, "B": 0.5, "C": 0.2}
    scores = []
    for p in papers:
        grade = p.get("grade", {})
        tier = grade.get("tier", "C")
        paper_score = grade.get("score", 0)
        scaled = paper_score * 100 * tier_weights.get(tier, 0.3)
        scores.append(scaled)

    if not scores:
        return 0.0
    return max(0.0, min(100.0, sum(scores) / len(scores)))


def score_imaging_consistency(mri_results: dict) -> float:
    """影像一致性评分 (0-100)。

    基于 MRI 检查结果中成功/存疑/失败的比例。
    """
    checks = []
    if isinstance(mri_results, dict):
        checks = mri_results.get("results", []) or mri_results.get("checks", [])

    if not checks:
        return 50.0  # 无影像数据时给中值

    total = len(checks)
    if total == 0:
        return 50.0

    confirmed = sum(1 for c in checks if c.get("status") in ("success", "consistent"))
    conflicted = sum(1 for c in checks if c.get("status") in ("fail", "conflict"))

    return max(0.0, min(100.0, (confirmed / total) * 80 - (conflicted / total) * 30 + 50))


def score_variability_risk(results: dict) -> float:
    """变异风险评分 (0-100)。越高表示风险越低（越稳定）。"""
    cv_data = results.get("cv_stability", {})
    if not cv_data:
        return 50.0

    high = sum(1 for v in cv_data.values() if v.get("risk_level") == "高")
    total = len(cv_data)
    if total == 0:
        return 50.0

    risk_ratio = high / total
    # 转换: 高变异比例越高 → 分数越低
    return max(0.0, min(100.0, 100 - risk_ratio * 100))


def compute_dimension_scores(
    results: dict,
    alerts: list[dict],
    lit_filtered: dict,
    mri_results: dict,
) -> DimensionScores:
    """计算全部 5 维评分。"""
    return {
        "inflammation": round(score_inflammation(results), 1),
        "lab_abnormality": round(score_lab_abnormality(results, alerts), 1),
        "literature_support": round(score_literature_support(lit_filtered), 1),
        "imaging_consistency": round(score_imaging_consistency(mri_results), 1),
        "variability_stability": round(score_variability_risk(results), 1),
    }


# ═════════════════════════════════════════════════════════════════════════
# 诊断规则引擎
# ═════════════════════════════════════════════════════════════════════════


def _is_acute(labels: list[str]) -> bool:
    return "急性期" in labels[-3:] if labels else False


def _has_trend(results: dict, metric: str, direction: str = "上升") -> bool:
    reg = results.get("linear_regression", {})
    m = reg.get(metric, {})
    return m.get("trend") == direction and m.get("r2", 0) >= 0.6


# 诊断规则： (名称, 条件函数, 假设文本, 建议动作, 置信度增量)
DIAGNOSTIC_RULES: list[tuple[str, callable, str, list[str], float]] = [
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
        except Exception:
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


# ═════════════════════════════════════════════════════════════════════════
# 数据加载
# ═════════════════════════════════════════════════════════════════════════


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _load_alerts(path: Path) -> list[dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def build_scoring_card(
    patient_id: str,
    data_dir: Path,
) -> ScoringResult:
    """从数据目录加载所有输入，计算评分卡。

    Args:
        patient_id: 脱敏患者 ID。
        data_dir: 该患者的运行批次目录（``data/<deid>/<ts>/``）。

    Returns:
        评分卡结果 dict。
    """
    analyzed_dir = data_dir / "02_analyzed"
    lit_dir = data_dir / "03_literature"
    imaging_dir = data_dir / "05_imaging"

    results = _load_json(analyzed_dir / "analysis_results.json")
    alerts = _load_alerts(analyzed_dir / "alerts.json")
    lit_filtered = _load_json(lit_dir / "literature_results.filtered.json")
    mri_results = _load_json(imaging_dir / "mri_report_check_results.json")

    if not results:
        print("  [WARNING] analysis_results.json 为空，评分可能不完整")

    # 加载 feedback 置信度调整
    fb_adjustments = {}
    try:
        from lab_analysis.feedback import get_confidence_adjustments

        fb_adjustments = get_confidence_adjustments(patient_id)
        if fb_adjustments:
            print(f"  [FEEDBACK] 已加载 {len(fb_adjustments)} 条置信度调整")
    except Exception:
        pass

    dim_scores = compute_dimension_scores(results, alerts, lit_filtered, mri_results)
    hypotheses = evaluate_hypotheses(
        results,
        alerts,
        lit_filtered,
        mri_results,
        dim_scores,
        confidence_adjustments=fb_adjustments,
    )
    assessment = generate_overall_assessment(dim_scores, hypotheses)

    data_quality = {
        "has_analysis_results": bool(results),
        "has_alerts": bool(alerts),
        "has_literature": bool(lit_filtered),
        "has_mri": bool(mri_results),
        "n_alerts": len(alerts),
        "n_hypotheses": len(hypotheses),
    }

    return {
        "generated": datetime.now().isoformat(),
        "patient_id": patient_id,
        "dimension_scores": dim_scores,
        "top_hypotheses": hypotheses,
        "overall_assessment": assessment,
        "data_quality": data_quality,
    }


def format_scoring_md(card: ScoringResult) -> str:
    """将评分卡格式化为可读 Markdown。"""
    lines: list[str] = [
        "# 评分卡 & 临床决策支持\n",
        f"**患者ID**: {card['patient_id']}",
        f"**生成时间**: {card['generated']}",
        "",
        "---\n",
        "## 五维评分\n",
        "| 维度 | 评分 | 状态 |",
        "|------|------|------|",
    ]

    def _status(s: float) -> str:
        if s >= 70:
            return "✅ 良好"
        if s >= 40:
            return "⚠️ 关注"
        return "🔴 异常"

    for dim, score in card.get("dimension_scores", {}).items():
        label = {
            "inflammation": "炎症活动度",
            "lab_abnormality": "实验室异常度",
            "literature_support": "文献证据支持",
            "imaging_consistency": "影像一致性",
            "variability_stability": "指标稳定性",
        }.get(dim, dim)
        lines.append(f"| {label} | {score}/100 | {_status(score)} |")

    lines.extend(
        [
            "",
            "---\n",
            "## 诊断假设（按置信度排序）\n",
        ]
    )

    for h in card.get("top_hypotheses", []):
        lines.extend(
            [
                f"### {h['hypothesis']}",
                f"- **置信度**: {h['confidence']:.1%}",
                "",
                "**支持信号**:",
            ]
        )
        for s in h.get("supporting_signals", []):
            lines.append(f"  - {s}")
        lines.append("")
        if h.get("contradicting_signals"):
            lines.append("**矛盾信号**:")
            for s in h["contradicting_signals"]:
                lines.append(f"  - {s}")
            lines.append("")
        lines.append("**建议动作**:")
        for a in h.get("suggested_actions", []):
            lines.append(f"  - [ ] {a}")
        lines.append("")

    lines.extend(
        [
            "---\n",
            "## 综合评估\n",
            card.get("overall_assessment", ""),
            "\n",
            "---\n",
            "## 数据质量\n",
            f"- 分析结果: {'✅' if card.get('data_quality', {}).get('has_analysis_results') else '❌'}",
            f"- 异常告警: {'✅' if card.get('data_quality', {}).get('has_alerts') else '❌'}",
            f"- 文献证据: {'✅' if card.get('data_quality', {}).get('has_literature') else '❌'}",
            f"- 影像数据: {'✅' if card.get('data_quality', {}).get('has_mri') else '❌'}",
            f"- 告警数量: {card.get('data_quality', {}).get('n_alerts', 0)}",
            f"- 诊断假设: {card.get('data_quality', {}).get('n_hypotheses', 0)} 条",
        ]
    )

    return "\n".join(lines)


def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="评分卡 & 临床决策支持")
    parser.add_argument("--id-card", required=True, help="脱敏ID")
    args = parser.parse_args()

    raw_ts = __import__("os").environ.get("ANALYSIS_TS", "")
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or args.id_card)
    data_dir = WORK_ROOT / "data" / args.id_card / ts

    print("\n=== 评分卡 & 决策支持 ===")
    print(f"  患者: {args.id_card}")
    print(f"  目录: {data_dir}\n")

    card = build_scoring_card(args.id_card, data_dir)

    reports_dir = data_dir / "04_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "scoring_card.json"
    json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] JSON 已保存: {json_path}")

    md = format_scoring_md(card)
    md_path = reports_dir / "scoring_card.md"
    md_path.write_text(md, encoding="utf-8")
    print(f"  [OK] MD 已保存: {md_path}")

    print("\n" + md)


if __name__ == "__main__":
    _cli()
