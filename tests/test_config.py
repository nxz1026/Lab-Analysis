"""tests.test_config — 集中配置管理单测。"""

from __future__ import annotations

from pathlib import Path

from lab_analysis.config import WORK_ROOT, get


class TestWorkRoot:
    def test_is_path(self):
        assert isinstance(WORK_ROOT, Path)

    def test_is_absolute(self):
        assert WORK_ROOT.is_absolute()

    def test_resolved(self):
        assert WORK_ROOT == WORK_ROOT.resolve()


class TestGet:
    def test_returns_env_value(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "hello")
        assert get("MY_VAR") == "hello"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "  hello  ")
        assert get("MY_VAR") == "hello"

    def test_default_when_missing(self):
        assert get("NONEXISTENT_VAR_XYZ", "default_val") == "default_val"

    def test_empty_default_when_missing(self):
        assert get("NONEXISTENT_VAR_XYZ") == ""
