"""tests.test_literature_interpreter_dspy — DSPy 文献解读模块单测 (smoke)。"""

from __future__ import annotations

from lab_analysis.literature_interpreter_dspy import run_standard_mode


class MockArgs:
    def __init__(self):
        self.analysis = ""
        self.lit = ""
        self.out = "output.json"


def test_run_standard_mode_defaults():
    args = MockArgs()
    result = run_standard_mode(args)
    assert result is None or isinstance(result, dict)
