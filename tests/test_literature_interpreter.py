"""tests.test_literature_interpreter — 文献解读模块单测 (smoke)。"""

from __future__ import annotations

from pathlib import Path

from lab_analysis.literature_interpreter import load_json


class TestLoadJson:
    def test_missing_file(self, tmp_path):
        result = load_json(str(tmp_path / "nonexistent.json"))
        assert result == {}

    def test_default_value(self, tmp_path):
        result = load_json(str(tmp_path / "nonexistent.json"), default={})
        assert result in ({}, None)
