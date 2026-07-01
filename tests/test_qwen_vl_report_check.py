"""tests.test_qwen_vl_report_check — 通义千问视觉质检模块单测 (smoke)。"""

from __future__ import annotations

from pathlib import Path

from lab_analysis.qwen_vl_report_check import load_api_key, load_dicom_image


def test_load_api_key_missing():
    key = load_api_key("NONEXISTENT_VAR_FOR_TEST", required=False)
    assert key is None


def test_load_dicom_image_missing(tmp_path):
    import pytest
    with pytest.raises(RuntimeError):
        load_dicom_image(tmp_path / "nonexistent.dcm")
