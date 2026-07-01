"""tests.test_literature_searcher_pubmed — PubMed API 模块单测 (smoke)。"""

from __future__ import annotations

from lab_analysis.literature_searcher.pubmed import efetch, esearch


class TestEsearch:
    def test_is_callable(self):
        assert callable(esearch)

    def test_returns_dict(self):
        import json
        result = esearch("test_query", retmax=1)
        assert isinstance(result, dict)
