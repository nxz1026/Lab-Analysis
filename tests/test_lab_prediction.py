"""tests.test_lab_prediction — 检验指标预测测试"""

import pandas as pd

from lab_analysis.lab_prediction import predict_metric, predict_metrics, print_predictions


class TestPredictMetric:
    def test_enough_data_returns_prediction(self):
        series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        pred = predict_metric(series, "hs-CRP")
        assert "next_value" in pred
        assert pred["n_used"] == 5
        assert pred["trend"] == "上升"

    def test_downward_trend(self):
        series = pd.Series([10.0, 8.0, 6.0, 4.0])
        pred = predict_metric(series, "CRP")
        assert pred["trend"] == "下降"
        assert pred["next_value"] < 4.0

    def test_flat_trend(self):
        series = pd.Series([5.0, 5.1, 4.9, 5.0])
        pred = predict_metric(series, "WBC")
        assert pred["trend"] == "平稳"

    def test_insufficient_data_returns_empty(self):
        series = pd.Series([1.0])
        pred = predict_metric(series, "hs-CRP")
        assert pred == {}

    def test_ci_lower_less_than_upper(self):
        series = pd.Series([2.0, 3.0, 4.0, 5.0, 6.0])
        pred = predict_metric(series, "hs-CRP")
        assert pred["ci_95_lower"] <= pred["ci_95_upper"]

    def test_alert_above_threshold(self):
        series = pd.Series([4.0, 5.0, 6.0, 7.0])
        pred = predict_metric(series, "hs-CRP")
        assert pred["alert"] is not None
        assert "阈值" in pred["alert"]

    def test_no_alert_below_threshold(self):
        series = pd.Series([0.5, 0.6, 0.4, 0.7])
        pred = predict_metric(series, "hs-CRP")
        assert pred.get("alert") is None


class TestPredictMetrics:
    def test_predicts_key_metrics(self):
        df = pd.DataFrame(
            {
                "hs-CRP": [1.0, 2.0, 3.0, 4.0],
                "CRP": [5.0, 6.0, 7.0, 8.0],
                "WBC": [6.0, 6.5, 7.0, 7.5],
            }
        )
        results = {}
        preds = predict_metrics(results, df)
        assert "hs-CRP" in preds
        assert "CRP" in preds
        assert "WBC" in preds

    def test_missing_column_skipped(self):
        df = pd.DataFrame({"hs-CRP": [1.0, 2.0]})
        preds = predict_metrics({}, df)
        assert list(preds.keys()) == ["hs-CRP"]


class TestPrintPredictions:
    def test_prints_without_error(self, capsys):
        preds = {
            "hs-CRP": {
                "next_value": 5.0,
                "ci_95_lower": 3.0,
                "ci_95_upper": 7.0,
                "n_used": 4,
                "method": "linear",
                "trend": "上升",
                "alert": None,
            }
        }
        print_predictions(preds)
        captured = capsys.readouterr()
        assert "hs-CRP" in captured.out
        assert "上升" in captured.out

    def test_empty_prints_info(self, capsys):
        print_predictions({})
        captured = capsys.readouterr()
        assert "无有效预测数据" in captured.out
