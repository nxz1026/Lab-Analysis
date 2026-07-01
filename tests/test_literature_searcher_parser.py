"""tests.test_literature_searcher_parser — 文献解析模块单测。"""

from __future__ import annotations

from lab_analysis.literature_searcher.parser import parse_papers


class TestParsePapers:
    def test_empty_text_returns_empty(self):
        result = parse_papers("")
        assert result == []

    def test_returns_list(self):
        result = parse_papers("<root></root>", pmids=["12345"])
        assert isinstance(result, list)
