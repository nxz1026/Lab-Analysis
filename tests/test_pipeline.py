"""tests.test_pipeline — 管线入口模块单测 (smoke)。"""

from __future__ import annotations

from lab_analysis.pipeline import main


def test_main_func_exists():
    assert callable(main)
