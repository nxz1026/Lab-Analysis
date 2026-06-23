"""scoring_card.types — 评分卡的类型别名定义。"""

from __future__ import annotations

from typing import Any

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
