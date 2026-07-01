"""tests.test_data_analyzer — 数据分析模块单测 (smoke)。"""

from __future__ import annotations

from lab_analysis.data_analyzer import run


def test_run_is_callable():
    assert callable(run)
