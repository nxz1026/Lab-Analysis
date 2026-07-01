"""tests.test_qwen_vl_report_check_dspy — DSPy 视觉质检模块单测 (smoke)。"""

from __future__ import annotations

from lab_analysis.qwen_vl_report_check_dspy import load_api_key, load_dicom_image


def test_load_api_key_missing():
    key = load_api_key("NONEXISTENT_VAR_FOR_TEST", required=False)
    assert key is None


def test_load_dicom_image_missing(tmp_path):
    result = load_dicom_image(tmp_path / "nonexistent.dcm")
    assert result is None
