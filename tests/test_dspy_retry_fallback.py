"""_retry.py + 4 个 module forward 的 retry/fallback 测试。

不调真实 LLM, 用 stub predictor 模拟成功 / 失败 / 重试成功 / 永久失败。
"""

from __future__ import annotations

import pytest

from lab_analysis.dspy_modules._retry import (
    SafeCallError,
    make_empty_prediction,
    safe_predict,
)
from lab_analysis.dspy_modules.final_report_generator import (
    FinalReportGenerator,
    FinalReportSignature,
)
from lab_analysis.dspy_modules.lab_data_extractor import (
    LabDataExtractionSignature,
    LabDataExtractor,
)
from lab_analysis.dspy_modules.literature_interpreter import (
    LiteratureInterpretationSignature,
    LiteratureInterpreterModule,
)
from lab_analysis.dspy_modules.mri_analyzer import MRIAnalysisModule, MRIAnalysisSignature

# -------------------- helpers --------------------


class _FakePrediction:
    """Mock dspy.Prediction for stub."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _stub_predictor(behaviour: list):
    """behaviour: list of either Exception instance or dict (return value).
    Each call pops one element. After list exhausted, raises RuntimeError.
    """
    queue = list(behaviour)

    def _call(**kwargs):
        if not queue:
            raise RuntimeError("stub exhausted")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return _FakePrediction(**item)

    return _call


# -------------------- safe_predict --------------------


def test_safe_predict_success_first_try():
    pred = safe_predict(_stub_predictor([{"x": 1}]), module_name="t", x=1)
    assert pred.x == 1


def test_safe_predict_retry_then_success(monkeypatch):
    # monkeypatch time.sleep to avoid actual sleep
    monkeypatch.setattr("lab_analysis.dspy_modules._retry.time.sleep", lambda s: None)
    pred = safe_predict(
        _stub_predictor([RuntimeError("net1"), RuntimeError("net2"), {"y": "ok"}]),
        module_name="t",
        backoff_base=0.1,
    )
    assert pred.y == "ok"


def test_safe_predict_raises_safe_call_error_after_exhausting(monkeypatch):
    monkeypatch.setattr("lab_analysis.dspy_modules._retry.time.sleep", lambda s: None)
    with pytest.raises(SafeCallError) as exc_info:
        safe_predict(
            _stub_predictor([RuntimeError("a"), RuntimeError("b"), RuntimeError("c")]),
            module_name="t",
            max_retries=3,
            backoff_base=0.1,
        )
    assert "after 3 attempts" in str(exc_info.value)


def test_safe_predict_backoff_grows(monkeypatch):
    sleeps = []
    monkeypatch.setattr("lab_analysis.dspy_modules._retry.time.sleep", lambda s: sleeps.append(s))
    with pytest.raises(SafeCallError):
        safe_predict(
            _stub_predictor([RuntimeError("x")] * 3),
            module_name="t",
            max_retries=3,
            backoff_base=2.0,
        )
    # 2 retries (after attempt 1 fail, after attempt 2 fail)
    # base^1 = 2.0, base^2 = 4.0
    assert sleeps == [2.0, 4.0]


# -------------------- make_empty_prediction --------------------


def test_make_empty_prediction_only_outputs():
    pred = make_empty_prediction(LiteratureInterpretationSignature)
    # interpretation (str) → ""
    assert pred.interpretation == ""
    assert pred.confidence == 0.0


def test_make_empty_prediction_lab_data():
    pred = make_empty_prediction(LabDataExtractionSignature)
    # str defaults to ""
    assert pred.patient_id == ""
    assert pred.report_date == ""
    # optional[float] defaults to None (Optional handling)
    assert pred.wbc_value is None
    assert pred.confidence == 0.0


def test_make_empty_prediction_mri():
    pred = make_empty_prediction(MRIAnalysisSignature)
    assert pred.anatomical_localization == ""
    assert pred.imaging_findings == ""
    assert pred.consistency_evaluation == ""
    assert pred.additional_findings == ""
    assert pred.confidence_score == 0.0


def test_make_empty_prediction_final_report():
    pred = make_empty_prediction(FinalReportSignature)
    assert pred.report_title == ""
    assert pred.section_1_basic_info == ""
    assert pred.section_9_prognosis == ""
    assert pred.confidence == 0.0


# -------------------- module forward fallback --------------------


def test_lab_extractor_forward_fallback(monkeypatch):
    """LabDataExtractor.forward: predictor always fails → fallback empty Prediction."""
    monkeypatch.setattr(
        "lab_analysis.dspy_modules.lab_data_extractor.safe_predict",
        lambda *a, **kw: (_ for _ in ()).throw(SafeCallError("simulated")),
    )
    mod = LabDataExtractor()
    result = mod.forward(image_description="dummy")
    assert result.patient_id == ""
    assert result.confidence == 0.0


def test_literature_interpreter_forward_fallback(monkeypatch):
    monkeypatch.setattr(
        "lab_analysis.dspy_modules.literature_interpreter.safe_predict",
        lambda *a, **kw: (_ for _ in ()).throw(SafeCallError("simulated")),
    )
    mod = LiteratureInterpreterModule()
    result = mod.forward(patient_id="x", analysis_results={}, literature_results={})
    assert result.interpretation == ""
    assert result.confidence == 0.0


def test_mri_analyzer_forward_fallback(monkeypatch):
    monkeypatch.setattr(
        "lab_analysis.dspy_modules.mri_analyzer.safe_predict",
        lambda *a, **kw: (_ for _ in ()).throw(SafeCallError("simulated")),
    )
    mod = MRIAnalysisModule()
    result = mod.forward(
        image_description="",
        report_findings="",
        clinical_context="",
    )
    assert result.anatomical_localization == ""
    assert result.confidence_score == 0.0


def test_final_report_forward_fallback(monkeypatch):
    monkeypatch.setattr(
        "lab_analysis.dspy_modules.final_report_generator.safe_predict",
        lambda *a, **kw: (_ for _ in ()).throw(SafeCallError("simulated")),
    )
    mod = FinalReportGenerator()
    result = mod.forward(
        patient_info={},
        lab_summary="",
        analysis_results={},
        literature_interpretation="",
        mri_analysis="",
        quality_control="",
    )
    assert result.report_title == ""
    assert result.section_1_basic_info == ""
    assert result.confidence == 0.0


def test_lab_extractor_forward_success(monkeypatch):
    """LabDataExtractor.forward: predictor 正常返回 → 直接透传。"""
    fake = _FakePrediction(patient_id="12345", confidence=0.9, wbc_value=5.5)
    monkeypatch.setattr(
        "lab_analysis.dspy_modules.lab_data_extractor.safe_predict",
        lambda *a, **kw: fake,
    )
    mod = LabDataExtractor()
    result = mod.forward(image_description="dummy")
    assert result.patient_id == "12345"
    assert result.confidence == 0.9
    assert result.wbc_value == 5.5


def test_safe_predict_passes_kwargs(monkeypatch):
    captured = {}

    def _spy(**kwargs):
        captured.update(kwargs)
        return _FakePrediction(z="ok")

    monkeypatch.setattr("lab_analysis.dspy_modules._retry.time.sleep", lambda s: None)
    safe_predict(
        _stub_predictor([{"z": "ok"}]),
        module_name="t",
        foo="bar",
        n=42,
    )
    # stub_predictor doesn't accept kwargs through our fixture,
    # so we test directly:
    safe_predict(_spy, module_name="t", foo="bar", n=42)
    assert captured == {"foo": "bar", "n": 42}
