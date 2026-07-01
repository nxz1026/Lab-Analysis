"""tests.test_analysis_run — 分析编排器单测。"""

from __future__ import annotations

import pandas as pd

from lab_analysis.analysis.run import _compute_stats, _compute_trends


class TestComputeTrends:
    def test_returns_dict(self):
        df = pd.DataFrame({"hs-CRP": [1.0, 2.0, 3.0]})
        result = _compute_trends(df)
        assert isinstance(result, dict)

    def test_contains_metric_key(self):
        df = pd.DataFrame({"WBC": [5.0, 6.0, 7.0]})
        result = _compute_trends(df)
        assert "WBC" in result

    def test_skips_missing_metric(self):
        df = pd.DataFrame({"OTHER": [1.0, 2.0]})
        result = _compute_trends(df)
        assert result == {}


class TestComputeStats:
    def test_returns_dict(self):
        df = pd.DataFrame({"hs-CRP": [1.0, 2.0], "report_date": pd.to_datetime(["2026-01-01", "2026-01-15"])})
        result = _compute_stats(df)
        assert isinstance(result, dict)

    def test_contains_n_reports(self):
        df = pd.DataFrame({"hs-CRP": [1.0], "report_date": pd.to_datetime(["2026-01-01"])})
        result = _compute_stats(df)
        assert result["n_reports"] == 1

    def test_contains_inflammation(self):
        df = pd.DataFrame({"hs-CRP": [0.5, 5.0], "report_date": pd.to_datetime(["2026-01-01", "2026-01-15"])})
        result = _compute_stats(df)
        assert "inflammation_classification" in result
