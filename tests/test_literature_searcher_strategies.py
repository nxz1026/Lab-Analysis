"""tests.test_literature_searcher_strategies — 搜索策略模块单测。"""

from __future__ import annotations

from lab_analysis.literature_searcher.strategies import SEARCH_STRATEGIES, auto_generate_queries


class TestSearchStrategies:
    def test_is_dict(self):
        assert isinstance(SEARCH_STRATEGIES, dict)
        assert len(SEARCH_STRATEGIES) > 0

    def test_has_expected_keys(self):
        assert "inflammation" in SEARCH_STRATEGIES
        assert "chronic_pancreatitis" in SEARCH_STRATEGIES


class TestAutoGenerateQueries:
    def test_empty_input_returns_dict(self):
        result = auto_generate_queries({})
        assert isinstance(result, dict)

    def test_with_analysis_results(self):
        result = auto_generate_queries({"hs-CRP": {"mean": 5.0}})
        assert isinstance(result, dict)
