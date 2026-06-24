"""scoring_card — 评分卡 & 临床决策支持。

综合检验数据、文献证据、影像印证、变异风险等多源信息，
输出 5 维评分 + 加权诊断假设列表（top-3），辅助临床决策。

纯规则引擎，不调 LLM，可重复可测试。

注意：暂无单元测试。本模块为纯规则引擎，逻辑简单，易于补充测试。

用法:
    python -m lab_analysis.scoring_card --id-card <deid>
"""

from __future__ import annotations

from .dimensions import (
    compute_dimension_scores,
    score_imaging_consistency,
    score_inflammation,
    score_lab_abnormality,
    score_literature_support,
    score_variability_risk,
)
from .hypotheses import (
    DIAGNOSTIC_RULES,
    evaluate_hypotheses,
    generate_overall_assessment,
)
from .io import build_scoring_card, format_scoring_md
from .types import DimensionScores, Hypothesis, ScoringResult

__all__ = [
    # types
    "Hypothesis",
    "DimensionScores",
    "ScoringResult",
    # dimensions
    "score_inflammation",
    "score_lab_abnormality",
    "score_literature_support",
    "score_imaging_consistency",
    "score_variability_risk",
    "compute_dimension_scores",
    # hypotheses
    "DIAGNOSTIC_RULES",
    "evaluate_hypotheses",
    "generate_overall_assessment",
    # io
    "build_scoring_card",
    "format_scoring_md",
]


def _cli():
    import argparse
    import json
    import os

    from lab_analysis.utils import WORK_ROOT

    from .. import _log

    logger = _log.get_logger(__name__)
    parser = argparse.ArgumentParser(description="评分卡 & 临床决策支持")
    parser.add_argument("--id-card", required=True, help="脱敏ID")
    args = parser.parse_args()

    raw_ts = os.environ.get("ANALYSIS_TS", "")
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts or args.id_card
    data_dir = WORK_ROOT / "data" / args.id_card / ts

    logger.info("\n=== 评分卡 & 决策支持 ===")
    logger.info(f"  患者: {args.id_card}")
    logger.info(f"  目录: {data_dir}\n")

    card = build_scoring_card(args.id_card, data_dir)
    reports_dir = data_dir / "04_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    json_path = reports_dir / "scoring_card.json"
    json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"  [OK] JSON 已保存: {json_path}")

    md = format_scoring_md(card)
    md_path = reports_dir / "scoring_card.md"
    md_path.write_text(md, encoding="utf-8")
    logger.info(f"  [OK] MD 已保存: {md_path}")
    logger.info("\n" + md)


if __name__ == "__main__":
    _cli()
