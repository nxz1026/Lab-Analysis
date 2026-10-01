"""scoring_card.io — 数据加载 + 评分卡组装 + Markdown 渲染。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .. import _log
from .dimensions import compute_dimension_scores
from .hypotheses import evaluate_hypotheses, generate_overall_assessment
from .types import ScoringResult

logger = _log.get_logger(__name__)


def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _load_alerts(path: Path) -> list[dict]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def build_scoring_card(patient_id: str, data_dir: Path) -> ScoringResult:
    """从数据目录加载所有输入，计算评分卡。

    Args:
        patient_id: 脱敏患者 ID。
        data_dir: 该患者的运行批次目录（``data/<deid>/<ts>/``）。

    Returns:
        评分卡结果 dict。
    """
    analyzed_dir = data_dir / "02_analyzed"
    lit_dir = data_dir / "03_literature"
    results = _load_json(analyzed_dir / "analysis_results.json")
    alerts = _load_alerts(analyzed_dir / "alerts.json")
    lit_filtered_path = lit_dir / "literature_results.filtered.json"
    lit_filtered = _load_json(lit_filtered_path)
    if not lit_filtered:
        logger.warning("  [WARNING] %s 不存在或为空，请先运行文献筛选", lit_filtered_path.name)
    # 影像印证结果由 qwen_vl_report_check*.py 写入 03_literature/ (不是 05_imaging/)。
    # 原先读 05_imaging/ 恒为空 → 影像一致性维度永远是中性 50.0,
    # imaging_lab_conflict 规则永远无法触发。
    mri_results = _load_json(lit_dir / "mri_report_check_results.json")

    if not results:
        logger.warning("  [WARNING] analysis_results.json 为空，评分可能不完整")

    fb_adjustments = {}
    try:
        from lab_analysis.feedback import get_confidence_adjustments

        fb_adjustments = get_confidence_adjustments(patient_id)
        if fb_adjustments:
            logger.info(f"  [FEEDBACK] 已加载 {len(fb_adjustments)} 条置信度调整")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
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
    has_any_data = bool(results or alerts or lit_filtered or mri_results)
    assessment = generate_overall_assessment(dim_scores, hypotheses, has_data=has_any_data)
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


_DIM_LABELS = {
    "inflammation": "炎症活动度",
    "lab_abnormality": "实验室异常度",
    "literature_support": "文献证据支持",
    "imaging_consistency": "影像一致性",
    "variability_stability": "指标稳定性",
}


# 维度极性: True = 分值越高越好, False = 分值越高越差
# 与 dimensions.py 模块 docstring 保持一致, 两处必须同步更新。
# 历史上这里只有一个全局阈值映射, 导致「炎症活动度 100/100 ✅良好」。
_DIM_HIGHER_IS_BETTER = {
    "inflammation": False,
    "lab_abnormality": False,
    "literature_support": True,
    "imaging_consistency": True,
    "variability_stability": True,
}


def _status_emoji(score: float, dim: str = "") -> str:
    """按维度极性返回状态标签。

    Args:
        score: 0-100 分值。
        dim:  维度键; 未知维度按「越高越好」处理(保守默认, 与历史行为一致)。
    """
    if _DIM_HIGHER_IS_BETTER.get(dim, True):
        if score >= 70:
            return "✅ 良好"
        if score >= 40:
            return "⚠️ 关注"
        return "🔴 异常"
    # 越高越差的维度: 低分才是好
    if score <= 30:
        return "✅ 良好"
    if score <= 60:
        return "⚠️ 关注"
    return "🔴 异常"


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

    for dim, score in card.get("dimension_scores", {}).items():
        label = _DIM_LABELS.get(dim, dim)
        lines.append(f"| {label} | {score}/100 | {_status_emoji(score, dim)} |")

    lines.extend(["", "---\n", "## 诊断假设（按置信度排序）\n"])
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

    dq = card.get("data_quality", {})
    lines.extend(
        [
            "---\n",
            "## 综合评估\n",
            card.get("overall_assessment", ""),
            "\n",
            "---\n",
            "## 数据质量\n",
            f"- 分析结果: {'✅' if dq.get('has_analysis_results') else '❌'}",
            f"- 异常告警: {'✅' if dq.get('has_alerts') else '❌'}",
            f"- 文献证据: {'✅' if dq.get('has_literature') else '❌'}",
            f"- 影像数据: {'✅' if dq.get('has_mri') else '❌'}",
            f"- 告警数量: {dq.get('n_alerts', 0)}",
            f"- 诊断假设: {dq.get('n_hypotheses', 0)} 条",
        ]
    )
    return "\n".join(lines)
