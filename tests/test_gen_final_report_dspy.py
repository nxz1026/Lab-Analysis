"""tests.test_gen_final_report_dspy — DSPy 报告模块单测 (smoke)。"""

from __future__ import annotations

from lab_analysis.gen_final_report_dspy import load_api_key


def test_load_api_key_missing():
    key = load_api_key("NONEXISTENT_VAR_FOR_TEST", required=False)
    assert key is None
