"""tests.test_analysis_compute — 统计分析计算函数单测。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from lab_analysis.analysis._compute import (
    classify_inflammation,
    correlation_matrix_calc,
    cv_stability_analysis,
    descriptive_stats,
    linear_regression_trend,
    moving_average_analysis,
    zscore_outlier_detection,
)


class TestClassifyInflammation:
    def test_none_returns_unknown(self):
        assert classify_inflammation(None) == "未知"

    def test_high_returns_acute(self):
        assert classify_inflammation(5.0) == "急性期"

    def test_low_returns_remission(self):
        assert classify_inflammation(0.5) == "缓解期"

    def test_mid_returns_transition(self):
        assert classify_inflammation(2.0) == "过渡期"

    def test_boundary_acute(self):
        assert classify_inflammation(3.0) == "过渡期"

    def test_boundary_remission(self):
        assert classify_inflammation(1.0) == "过渡期"


class TestLinearRegressionTrend:
    def test_insufficient_data(self):
        result = linear_regression_trend(pd.Series([1.0]))
        assert result["trend"] == "数据不足"

    def test_upward_trend(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = linear_regression_trend(s)
        assert result["trend"] == "上升"
        assert result["slope"] > 0

    def test_downward_trend(self):
        s = pd.Series([5.0, 4.0, 3.0, 2.0, 1.0])
        result = linear_regression_trend(s)
        assert result["trend"] == "下降"

    def test_flat_trend(self):
        s = pd.Series([3.0, 3.0, 3.0, 3.0])
        result = linear_regression_trend(s)
        assert result["trend"] == "平稳"

    def test_has_n_points(self):
        s = pd.Series([1.0, 2.0, 3.0])
        result = linear_regression_trend(s)
        assert result["n_points"] == 3


class TestCorrelationMatrixCalc:
    def test_returns_correlations(self):
        df = pd.DataFrame({"A": [1, 2, 3], "B": [2, 4, 6], "C": [6, 5, 4]})
        result = correlation_matrix_calc(df, ["A", "B", "C"])
        assert "A~B" in result
        assert abs(result["A~B"] - 1.0) < 0.01

    def test_skips_metrics_not_in_df(self):
        df = pd.DataFrame({"A": [1, 2, 3]})
        result = correlation_matrix_calc(df, ["A", "NONEXISTENT"])
        assert result == {}

    def test_returns_empty_for_single_metric(self):
        df = pd.DataFrame({"A": [1, 2, 3]})
        result = correlation_matrix_calc(df, ["A"])
        assert result == {}


class TestDescriptiveStats:
    def test_empty_series(self):
        result = descriptive_stats(pd.Series([], dtype=float))
        assert result["count"] == 0

    def test_basic_stats(self):
        result = descriptive_stats(pd.Series([1.0, 2.0, 3.0]))
        assert result["count"] == 3
        assert result["mean"] == 2.0
        assert result["min"] == 1.0
        assert result["max"] == 3.0

    def test_single_value_std_zero(self):
        result = descriptive_stats(pd.Series([5.0]))
        assert result["std"] == 0

    def test_cv(self):
        result = descriptive_stats(pd.Series([2.0, 4.0, 6.0]))
        assert result["cv"] is not None
        assert result["cv"] > 0


class TestMovingAverageAnalysis:
    def test_empty_for_window_one(self):
        df = pd.DataFrame({"hs-CRP": [1, 2, 3]})
        assert moving_average_analysis(df, window=1) == {}

    def test_insufficient_data_skipped(self):
        df = pd.DataFrame({"hs-CRP": [1]})
        result = moving_average_analysis(df, window=3)
        assert result == {}

    def test_returns_ma_for_key_metrics(self):
        df = pd.DataFrame({"hs-CRP": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = moving_average_analysis(df, window=3)
        assert "hs-CRP" in result
        assert "moving_avg" in result["hs-CRP"]

    def test_skips_missing_metric(self):
        df = pd.DataFrame({"OTHER": [1, 2, 3]})
        result = moving_average_analysis(df)
        assert result == {}


class TestCvStabilityAnalysis:
    def test_insufficient_data_skipped(self):
        df = pd.DataFrame({"WBC": [5.0, 6.0]})
        result = cv_stability_analysis(df)
        assert result == {}

    def test_stable_metric(self):
        df = pd.DataFrame({"WBC": [5.0, 5.1, 5.0, 5.1, 5.0]})
        result = cv_stability_analysis(df)
        assert "WBC" in result
        assert result["WBC"]["risk_level"] == "低"


class TestZscoreOutlierDetection:
    def test_insufficient_data_skipped(self):
        df = pd.DataFrame({"WBC": [5.0, 6.0]})
        result = zscore_outlier_detection(df)
        assert result == {}

    def test_detects_outlier(self):
        values = [5.0] * 20 + [999.0]
        df = pd.DataFrame({"WBC": values, "report_date": pd.date_range("2026-01-01", periods=21)})
        result = zscore_outlier_detection(df)
        assert "WBC" in result
        assert result["WBC"]["outliers_severe"]["count"] >= 1
