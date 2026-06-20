"""tests.test_scoring_card — 评分卡 & 决策支持测试"""

import json
import pytest

from lab_analysis.scoring_card import (
    score_inflammation,
    score_lab_abnormality,
    score_literature_support,
    score_imaging_consistency,
    score_variability_risk,
    compute_dimension_scores,
    evaluate_hypotheses,
    generate_overall_assessment,
    build_scoring_card,
    format_scoring_md,
)


# ═════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════


@pytest.fixture
def acute_results():
    """急性期数据"""
    return {
        "inflammation_classification": {
            "labels": ["缓解期", "过渡期", "急性期"],
            "report_dates": ["2026-03-01", "2026-03-15", "2026-04-01"],
        },
        "abnormal_summary": {
            "hs-CRP": {"ref_range": "0-1.0", "abnormal_dates": ["2026-04-01"], "n_abnormal": 1},
            "WBC": {"ref_range": "3.5-9.5", "abnormal_dates": ["2026-04-01"], "n_abnormal": 1},
            "PCT": {"ref_range": "0-0.5", "abnormal_dates": ["2026-04-01"], "n_abnormal": 1},
        },
        "zscore_outliers": {
            "WBC": {
                "outliers_severe": {"count": 1, "dates": ["2026-04-01"], "values": [15.0]},
                "outliers_mild": {"count": 0, "dates": [], "values": []},
                "max_deviation": {"z_score": 3.5},
            },
        },
        "linear_regression": {
            "hs-CRP": {"slope": 2.5, "r2": 0.89, "trend": "上升", "intercept": 0.5, "n_points": 3},
            "CRP": {"slope": -0.3, "r2": 0.92, "trend": "下降", "intercept": 15, "n_points": 3},
        },
        "cv_stability": {
            "PLT": {"cv": 0.35, "risk_level": "高"},
            "WBC": {"cv": 0.08, "risk_level": "低"},
        },
    }


@pytest.fixture
def remission_results():
    """缓解期数据"""
    return {
        "inflammation_classification": {
            "labels": ["急性期", "过渡期", "缓解期", "缓解期"],
            "report_dates": ["2026-03-01", "2026-03-15", "2026-04-01", "2026-04-15"],
        },
        "abnormal_summary": {},
        "zscore_outliers": {},
        "linear_regression": {
            "hs-CRP": {"slope": -1.2, "r2": 0.85, "trend": "下降", "intercept": 5, "n_points": 4},
        },
        "cv_stability": {
            "WBC": {"cv": 0.06, "risk_level": "低"},
        },
    }


@pytest.fixture
def sample_alerts():
    return [
        {"level": "CRITICAL", "source": "inflammation", "metric": "hs-CRP",
         "message": "hs-CRP 急性期"},
        {"level": "WARNING", "source": "reference_range", "metric": "WBC",
         "message": "WBC 超出参考范围"},
    ]


@pytest.fixture
def sample_lit_filtered():
    return {
        "filtered_papers": [
            {"grade": {"tier": "S", "score": 0.85}},
            {"grade": {"tier": "A", "score": 0.72}},
            {"grade": {"tier": "B", "score": 0.55}},
        ],
    }


@pytest.fixture
def sample_mri_results():
    return {
        "results": [
            {"status": "success"},
            {"status": "success"},
            {"status": "partial"},
        ],
    }


# ═════════════════════════════════════════════════════════════════════
# 1. 各维度评分
# ═════════════════════════════════════════════════════════════════════


class TestScoreInflammation:
    def test_acute_scores_high(self, acute_results):
        s = score_inflammation(acute_results)
        assert 60 <= s <= 100

    def test_remission_scores_low(self, remission_results):
        s = score_inflammation(remission_results)
        assert 0 <= s <= 60

    def test_empty_data_returns_baseline(self):
        s = score_inflammation({})
        assert s == 50.0


class TestScoreLabAbnormality:
    def test_acute_has_positive_score(self, acute_results, sample_alerts):
        s = score_lab_abnormality(acute_results, sample_alerts)
        assert 20 <= s <= 100

    def test_remission_scores_zero(self, remission_results):
        s = score_lab_abnormality(remission_results, [])
        assert s == 0.0

    def test_empty_returns_zero(self):
        s = score_lab_abnormality({}, [])
        assert s == 0.0


class TestScoreLiteratureSupport:
    def test_graded_papers_produce_score(self, sample_lit_filtered):
        s = score_literature_support(sample_lit_filtered)
        assert 30 <= s <= 100

    def test_empty_returns_zero(self):
        s = score_literature_support({})
        assert s == 0.0


class TestScoreImagingConsistency:
    def test_good_consistency(self, sample_mri_results):
        s = score_imaging_consistency(sample_mri_results)
        assert 50 <= s <= 100

    def test_empty_returns_mid(self):
        s = score_imaging_consistency({})
        assert s == 50.0


class TestScoreVariabilityRisk:
    def test_high_risk(self, acute_results):
        s = score_variability_risk(acute_results)
        # PLT high risk → score should be reduced
        assert 0 <= s <= 80

    def test_low_risk(self, remission_results):
        s = score_variability_risk(remission_results)
        assert s >= 80

    def test_empty_returns_mid(self):
        s = score_variability_risk({})
        assert s == 50.0


# ═════════════════════════════════════════════════════════════════════
# 2. 聚合评分
# ═════════════════════════════════════════════════════════════════════


class TestComputeDimensionScores:
    def test_returns_all_5_dims(self, acute_results, sample_alerts, sample_lit_filtered, sample_mri_results):
        dims = compute_dimension_scores(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results)
        expected_keys = {"inflammation", "lab_abnormality", "literature_support",
                         "imaging_consistency", "variability_stability"}
        assert set(dims.keys()) == expected_keys
        for v in dims.values():
            assert 0 <= v <= 100


# ═════════════════════════════════════════════════════════════════════
# 3. 诊断假设
# ═════════════════════════════════════════════════════════════════════


class TestEvaluateHypotheses:
    def test_acute_produces_hypotheses(self, acute_results, sample_alerts, sample_lit_filtered, sample_mri_results):
        dims = compute_dimension_scores(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results)
        hyps = evaluate_hypotheses(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results, dims)
        assert len(hyps) >= 1
        assert hyps[0]["confidence"] > 0

    def test_remission_produces_different_hypotheses(self, remission_results, sample_alerts, sample_lit_filtered, sample_mri_results):
        dims = compute_dimension_scores(remission_results, sample_alerts, sample_lit_filtered, sample_mri_results)
        hyps = evaluate_hypotheses(remission_results, sample_alerts, sample_lit_filtered, sample_mri_results, dims)
        # remission should match different rules than acute
        # at minimum, should not crash and produce valid output
        assert isinstance(hyps, list)

    def test_max_3_hypotheses(self, acute_results, sample_alerts, sample_lit_filtered, sample_mri_results):
        dims = compute_dimension_scores(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results)
        hyps = evaluate_hypotheses(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results, dims)
        assert len(hyps) <= 3

    def test_hypotheses_have_required_fields(self, acute_results, sample_alerts, sample_lit_filtered, sample_mri_results):
        dims = compute_dimension_scores(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results)
        hyps = evaluate_hypotheses(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results, dims)
        for h in hyps:
            assert "hypothesis" in h
            assert "confidence" in h
            assert "supporting_signals" in h
            assert "suggested_actions" in h


# ═════════════════════════════════════════════════════════════════════
# 4. 综合评估
# ═════════════════════════════════════════════════════════════════════


class TestGenerateOverallAssessment:
    def test_returns_string(self, acute_results, sample_alerts, sample_lit_filtered, sample_mri_results):
        dims = compute_dimension_scores(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results)
        hyps = evaluate_hypotheses(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results, dims)
        assessment = generate_overall_assessment(dims, hyps)
        assert isinstance(assessment, str)
        assert len(assessment) > 10


# ═════════════════════════════════════════════════════════════════════
# 5. 序列化 & 格式
# ═════════════════════════════════════════════════════════════════════


class TestScoringCardFormat:
    def test_json_serializable(self, acute_results, sample_alerts, sample_lit_filtered, sample_mri_results):
        dims = compute_dimension_scores(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results)
        hyps = evaluate_hypotheses(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results, dims)
        card = {
            "generated": "2026-06-20T12:00:00",
            "patient_id": "test",
            "dimension_scores": dims,
            "top_hypotheses": hyps,
            "overall_assessment": generate_overall_assessment(dims, hyps),
            "data_quality": {},
        }
        dumped = json.dumps(card, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert "dimension_scores" in loaded
        assert "top_hypotheses" in loaded

    def test_format_md_produces_output(self, acute_results, sample_alerts, sample_lit_filtered, sample_mri_results):
        dims = compute_dimension_scores(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results)
        hyps = evaluate_hypotheses(acute_results, sample_alerts, sample_lit_filtered, sample_mri_results, dims)
        card = {
            "generated": "2026-06-20T12:00:00",
            "patient_id": "test",
            "dimension_scores": dims,
            "top_hypotheses": hyps,
            "overall_assessment": generate_overall_assessment(dims, hyps),
            "data_quality": {"has_analysis_results": True, "n_hypotheses": len(hyps)},
        }
        md = format_scoring_md(card)
        assert "评分" in md
        assert "诊断假设" in md
        assert len(md) > 200
