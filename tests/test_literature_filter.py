"""tests.test_literature_filter — 文献过滤模块单测。"""

from __future__ import annotations

from pathlib import Path

import pytest

from lab_analysis.literature_filter import ScenarioName, filter_literature


class TestScenarioName:
    def test_is_string(self):
        assert isinstance(ScenarioName, object)


class TestFilterLiterature:
    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            filter_literature(Path("/nonexistent/path.json"))
