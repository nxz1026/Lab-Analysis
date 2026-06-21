"""tests.test_feedback — 交互式反馈回路测试"""

import json

import pytest

from lab_analysis.feedback import (
    clear_feedback,
    get_confidence_adjustments,
    load_feedback,
    record_correction,
)


@pytest.fixture
def mock_feedback_path(tmp_path, monkeypatch):
    """临时改 WORK_ROOT 避免写入真实 data/"""
    import lab_analysis.feedback as fb
    original_root = fb.WORK_ROOT
    fb.WORK_ROOT = tmp_path
    yield tmp_path
    fb.WORK_ROOT = original_root


class TestLoadFeedback:
    def test_no_file_returns_empty_template(self, mock_feedback_path):
        fb = load_feedback("test_deid")
        assert fb["patient_id"] == "test_deid"
        assert fb["corrections"] == []
        assert fb["confidence_adjustments"] == {}

    def test_existing_file_loaded(self, mock_feedback_path):
        path = mock_feedback_path / "data" / "test_deid" / "feedback.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"patient_id": "test_deid", "corrections": [{"test": 1}]}))
        fb = load_feedback("test_deid")
        assert len(fb["corrections"]) == 1


class TestRecordCorrection:
    def test_adds_correction(self, mock_feedback_path):
        fb = record_correction(
            "test_deid",
            original_hypothesis="慢性胰腺炎（活动期）",
            corrected_hypothesis="急性胰腺炎",
            original_confidence=0.82,
            corrected_confidence=0.90,
            user_comment="临床确诊",
        )
        assert len(fb["corrections"]) == 1
        c = fb["corrections"][0]
        assert c["original_hypothesis"] == "慢性胰腺炎（活动期）"
        assert c["corrected_hypothesis"] == "急性胰腺炎"
        assert "corrected_at" in c

    def test_confidence_adjustment_updated(self, mock_feedback_path):
        fb = record_correction(
            "test_deid",
            original_hypothesis="慢性胰腺炎（活动期）",
            corrected_hypothesis="急性胰腺炎",
            original_confidence=0.82,
            corrected_confidence=0.90,
        )
        adj = fb.get("confidence_adjustments", {})
        assert "chronic_pancreatitis_active" in adj
        # confidence diff = 0.08, not > 0.1, but hypothesis changed → -0.10
        assert adj["chronic_pancreatitis_active"] <= 0


class TestGetConfidenceAdjustments:
    def test_returns_adjustments(self, mock_feedback_path):
        # First record something
        record_correction("test_deid", "hyp A", "hyp B", 0.9, 0.5)
        adj = get_confidence_adjustments("test_deid")
        assert isinstance(adj, dict)

    def test_no_feedback_returns_empty(self, mock_feedback_path):
        adj = get_confidence_adjustments("no_data")
        assert adj == {}


class TestClearFeedback:
    def test_clears_existing(self, mock_feedback_path):
        record_correction("test_deid", "a", "b", 0.8, 0.9)
        assert (mock_feedback_path / "data" / "test_deid" / "feedback.json").exists()
        clear_feedback("test_deid")
        assert not (mock_feedback_path / "data" / "test_deid" / "feedback.json").exists()
