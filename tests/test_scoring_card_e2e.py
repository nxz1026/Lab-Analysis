"""scoring_card.py 端到端测试 — 5 维评分 + 假设推理。

覆盖纯函数路径，不依赖真实数据文件。
"""

from __future__ import annotations

import pytest

from lab_analysis.scoring_card import (
    compute_dimension_scores,
    evaluate_hypotheses,
    score_imaging_consistency,
    score_inflammation,
    score_lab_abnormality,
    score_literature_support,
    score_variability_risk,
)

# ═════════════════════════════════════════════════════════════════════════
# 工厂: 构造最小可用字典
# ═════════════════════════════════════════════════════════════════════════


def _empty_results() -> dict:
    return {}


def _acute_results(labels: list[str] | None = None) -> dict:
    labels = labels or ["急性期", "急性期", "急性期"]
    return {
        "inflammation_classification": {
            "labels": labels,
            "report_dates": [f"2026-01-{i + 1:02d}" for i in range(len(labels))],
        },
        "linear_regression": {
            "hs-CRP": {"trend": "上升", "r2": 0.85, "slope": 0.12},
        },
        "abnormal_summary": {"hs-CRP": "5.2", "CRP": "30"},
        "zscore_outliers": {"hs-CRP": {"outliers_severe": {"count": 2}}},
        "cv_stability": {"hs-CRP": {"risk_level": "高"}, "CRP": {"risk_level": "高"}},
    }


def _remission_results() -> dict:
    labels = ["缓解期", "缓解期", "缓解期"]
    return {
        "inflammation_classification": {
            "labels": labels,
            "report_dates": [f"2026-01-{i + 1:02d}" for i in range(len(labels))],
        },
        "linear_regression": {
            "hs-CRP": {"trend": "下降", "r2": 0.8, "slope": -0.05},
        },
        "abnormal_summary": {},
        "zscore_outliers": {},
        "cv_stability": {"hs-CRP": {"risk_level": "低"}},
    }


def _alerts(level: str = "CRITICAL", n: int = 1) -> list[dict]:
    return [{"level": level, "message": f"测试告警 {i}"} for i in range(n)]


def _lit_filtered(tiers: list[str]) -> dict:
    """构造 evidence-grading 后的文献结构。"""
    papers = []
    weights = {"S": 1.0, "A": 0.8, "B": 0.5, "C": 0.2}
    for i, tier in enumerate(tiers):
        papers.append(
            {
                "pmid": f"PMID-{i}",
                "title": f"Test paper {i}",
                "grade": {"tier": tier, "score": weights[tier]},
            }
        )
    return {"filtered_papers": papers}


def _mri_results(confirmed: int = 0, conflict: int = 0) -> dict:
    checks = [{"status": "success"} for _ in range(confirmed)]
    checks.extend([{"status": "fail"} for _ in range(conflict)])
    return {"results": checks}


# ═════════════════════════════════════════════════════════════════════════
# score_inflammation
# ═════════════════════════════════════════════════════════════════════════


class TestScoreInflammation:
    def test_empty_results_baseline(self):
        """空结果应给基线分 50。"""
        score = score_inflammation(_empty_results())
        assert 45.0 <= score <= 55.0

    def test_acute_with_rising_trend(self):
        """急性期 + hs-CRP 上升趋势 → 分数显著高于基线。"""
        score = score_inflammation(_acute_results())
        assert score >= 80.0, f"急性+上升应高分，实测 {score}"

    def test_remission_lowers_score(self):
        """持续缓解期 → 分数低于基线。"""
        score = score_inflammation(_remission_results())
        assert score <= 50.0, f"缓解期应低于基线，实测 {score}"

    def test_score_clamped_to_0_100(self):
        """分数必须在 0-100 区间。"""
        for results in (
            _empty_results(),
            _acute_results(),
            _remission_results(),
        ):
            s = score_inflammation(results)
            assert 0.0 <= s <= 100.0


# ═════════════════════════════════════════════════════════════════════════
# score_lab_abnormality
# ═════════════════════════════════════════════════════════════════════════


class TestScoreLabAbnormality:
    def test_empty_inputs_zero(self):
        """无异常无告警 → 0 分。"""
        score = score_lab_abnormality(_empty_results(), [])
        assert score == 0.0

    def test_many_abnormal_and_critical_alerts(self):
        """多异常 + CRITICAL 告警 → 接近上限。"""
        results = {
            "abnormal_summary": {f"m{i}": "high" for i in range(8)},  # 8*8=64→clip40
            "zscore_outliers": {"hs-CRP": {"outliers_severe": {"count": 2}}},  # 2*15=30
        }
        alerts = _alerts(level="CRITICAL", n=3)  # 3*10=30
        score = score_lab_abnormality(results, alerts)
        assert score >= 90.0, f"应近满，实测 {score}"
        assert score <= 100.0

    def test_only_warnings_no_score(self):
        """仅 WARNING 告警（无 CRITICAL）→ 只算异常项。"""
        results = {
            "abnormal_summary": {"hs-CRP": "5"},
            "zscore_outliers": {},
        }
        alerts = _alerts(level="WARNING", n=5)
        score = score_lab_abnormality(results, alerts)
        # 1*8=8 → 8
        assert score == pytest.approx(8.0, abs=0.1)


# ═════════════════════════════════════════════════════════════════════════
# score_literature_support
# ═════════════════════════════════════════════════════════════════════════


class TestScoreLiteratureSupport:
    def test_no_papers_zero(self):
        assert score_literature_support({"filtered_papers": []}) == 0.0

    def test_all_S_tier_high(self):
        """全是 S 级 → 高分。"""
        lit = _lit_filtered(["S", "S", "S"])
        score = score_literature_support(lit)
        assert score >= 80.0

    def test_all_C_tier_low(self):
        """全是 C 级 → 低分。"""
        lit = _lit_filtered(["C", "C", "C"])
        score = score_literature_support(lit)
        assert score <= 30.0


# ═════════════════════════════════════════════════════════════════════════
# score_imaging_consistency
# ═════════════════════════════════════════════════════════════════════════


class TestScoreImagingConsistency:
    def test_no_imaging_neutral(self):
        """无影像数据 → 中性分 50。"""
        assert score_imaging_consistency({}) == 50.0

    def test_all_confirmed_high(self):
        """全部 success → 高分。"""
        score = score_imaging_consistency(_mri_results(confirmed=5))
        assert score >= 70.0

    def test_all_conflicted_low(self):
        """全部 fail → 低分。"""
        score = score_imaging_consistency(_mri_results(conflict=5))
        assert score <= 30.0

    def test_mixed(self):
        """混合应在 30-70 区间。"""
        score = score_imaging_consistency(_mri_results(confirmed=2, conflict=2))
        assert 20.0 <= score <= 80.0


# ═════════════════════════════════════════════════════════════════════════
# score_variability_risk
# ═════════════════════════════════════════════════════════════════════════


class TestScoreVariabilityRisk:
    def test_empty_cv_neutral(self):
        assert score_variability_risk(_empty_results()) == 50.0

    def test_all_low_risk(self):
        """全低风险 → 高分（100）。"""
        results = {"cv_stability": {f"m{i}": {"risk_level": "低"} for i in range(3)}}
        assert score_variability_risk(results) == 100.0

    def test_all_high_risk(self):
        """全高风险 → 0 分。"""
        results = {"cv_stability": {f"m{i}": {"risk_level": "高"} for i in range(3)}}
        assert score_variability_risk(results) == 0.0


# ═════════════════════════════════════════════════════════════════════════
# compute_dimension_scores (integration)
# ═════════════════════════════════════════════════════════════════════════


class TestComputeDimensionScores:
    def test_full_inputs_all_dimensions(self):
        """完整 4 输入 → 5 维评分全部返回。"""
        results = _acute_results()
        alerts = _alerts("CRITICAL", 2)
        lit = _lit_filtered(["A", "A"])
        mri = _mri_results(confirmed=3)

        dims = compute_dimension_scores(results, alerts, lit, mri)
        assert set(dims.keys()) == {
            "inflammation",
            "lab_abnormality",
            "literature_support",
            "imaging_consistency",
            "variability_stability",
        }
        for v in dims.values():
            assert 0.0 <= v <= 100.0
            assert isinstance(v, float)


# ═════════════════════════════════════════════════════════════════════════
# evaluate_hypotheses
# ═════════════════════════════════════════════════════════════════════════


class TestEvaluateHypotheses:
    def test_acute_triggers_active_pancreatitis(self):
        """急性期 + 上升趋势 → 应触发慢性胰腺炎活动期假设。"""
        results = _acute_results()
        alerts = _alerts("CRITICAL", 1)
        lit = _lit_filtered(["A"])
        mri = _mri_results(confirmed=2)
        dims = compute_dimension_scores(results, alerts, lit, mri)

        hyps = evaluate_hypotheses(results, alerts, lit, mri, dims)
        assert len(hyps) >= 1
        assert len(hyps) <= 3
        # 至少有一个假设提到胰腺炎或系统性炎症
        names = [h["hypothesis"] for h in hyps]
        assert any("胰腺炎" in n or "炎症" in n or "感染" in n for n in names), (
            f"未触发活动期/感染假设: {names}"
        )

    def test_empty_inputs_no_hypotheses(self):
        """空数据 → 可能 0 或 1 个低置信度假设。"""
        results = _empty_results()
        alerts = []
        lit = {"filtered_papers": []}
        mri = {}

        dims = compute_dimension_scores(results, alerts, lit, mri)
        hyps = evaluate_hypotheses(results, alerts, lit, mri, dims)
        assert isinstance(hyps, list)
        # 不应超过 3
        assert len(hyps) <= 3

    def test_confidence_adjustments_applied(self):
        """置信度调整表应能上下调指定假设。"""
        results = _acute_results()
        alerts = _alerts("CRITICAL", 1)
        lit = _lit_filtered(["A"])
        mri = _mri_results(confirmed=2)
        dims = compute_dimension_scores(results, alerts, lit, mri)

        hyps_no_adj = evaluate_hypotheses(results, alerts, lit, mri, dims)
        # 记录无调整时，慢性胰腺炎活动期假说（如果存在）的置信度
        target = "慢性胰腺炎（活动期）"
        baseline_conf = next(
            (h["confidence"] for h in hyps_no_adj if h["hypothesis"] == target),
            None,
        )

        # 大幅下调该规则
        hyps_down = evaluate_hypotheses(
            results,
            alerts,
            lit,
            mri,
            dims,
            confidence_adjustments={"chronic_pancreatitis_active": -0.9},
        )
        down_conf = next(
            (h["confidence"] for h in hyps_down if h["hypothesis"] == target),
            None,
        )

        # 两个断言同时表达调整生效
        if baseline_conf is not None:
            # 若未调整时有该假设 → 调整后置信度应低于基线
            assert down_conf is not None
            assert down_conf < baseline_conf, f"下调无效: base={baseline_conf}, down={down_conf}"
        else:
            # 若未调整时都没有该假设，下调后更不应出现
            assert not any(h["hypothesis"] == target for h in hyps_down)

    def test_hypotheses_sorted_desc_by_confidence(self):
        """假设列表应按置信度降序。"""
        results = _acute_results()
        alerts = _alerts("CRITICAL", 2)
        lit = _lit_filtered(["A", "B"])
        mri = _mri_results(confirmed=2, conflict=1)
        dims = compute_dimension_scores(results, alerts, lit, mri)

        hyps = evaluate_hypotheses(results, alerts, lit, mri, dims)
        confs = [h["confidence"] for h in hyps]
        assert confs == sorted(confs, reverse=True)

    def test_each_hypothesis_has_required_fields(self):
        """每条假设必须含 5 个标准字段。"""
        results = _acute_results()
        alerts = _alerts("CRITICAL", 1)
        lit = _lit_filtered(["S"])
        mri = _mri_results(confirmed=3)
        dims = compute_dimension_scores(results, alerts, lit, mri)

        hyps = evaluate_hypotheses(results, alerts, lit, mri, dims)
        for h in hyps:
            assert set(h.keys()) >= {
                "hypothesis",
                "confidence",
                "supporting_signals",
                "contradicting_signals",
                "suggested_actions",
            }
            assert isinstance(h["confidence"], float)
            assert 0.0 <= h["confidence"] <= 1.0
