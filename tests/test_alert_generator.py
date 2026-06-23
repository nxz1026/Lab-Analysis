"""tests.test_alert_generator — 结构化异常告警摘要测试"""

import json

import pytest

from lab_analysis.alert_generator import (
    _alert_inflammation,
    _alert_reference_range,
    _alert_trend,
    _alert_variability,
    _alert_zscore,
    generate_alerts,
    print_alerts,
)

# ═════════════════════════════════════════════════════════════════════
# Fixtures: 模拟 _compute_stats() 产出的 results dict
# ═════════════════════════════════════════════════════════════════════


@pytest.fixture
def acute_results():
    """急性期 + 多异常值 + 高变异模拟数据"""
    return {
        "inflammation_classification": {
            "labels": ["缓解期", "过渡期", "急性期"],
            "report_dates": ["2026-03-01", "2026-03-15", "2026-04-01"],
        },
        "abnormal_summary": {
            "hs-CRP": {
                "ref_range": "0-1.0",
                "abnormal_dates": ["2026-04-01"],
                "n_abnormal": 1,
            },
            "RDW-SD": {
                "ref_range": "37-50",
                "abnormal_dates": ["2026-03-15", "2026-04-01"],
                "n_abnormal": 2,
            },
        },
        "zscore_outliers": {
            "WBC": {
                "z_scores": [1.0, 2.1, 3.5],
                "outliers_mild": {"count": 1, "dates": ["2026-03-15"], "values": [12.5]},
                "outliers_severe": {"count": 1, "dates": ["2026-04-01"], "values": [15.0]},
                "max_deviation": {"date": "2026-04-01", "value": 15.0, "z_score": 3.5},
                "threshold": 2.0,
            },
        },
        "cv_stability": {
            "PLT": {
                "cv": 0.31,
                "mean": 200,
                "std": 62,
                "stability": "高变异",
                "risk_level": "高",
                "n_points": 4,
            },
            "WBC": {
                "cv": 0.08,
                "mean": 6.5,
                "std": 0.52,
                "stability": "稳定",
                "risk_level": "低",
                "n_points": 4,
            },
        },
        "linear_regression": {
            "hs-CRP": {
                "slope": 2.5,
                "intercept": 0.5,
                "r2": 0.89,
                "trend": "上升",
                "slope_per_day": 2.5,
                "n_points": 3,
            },
            "CRP": {
                "slope": -0.3,
                "intercept": 15,
                "r2": 0.92,
                "trend": "下降",
                "slope_per_day": -0.3,
                "n_points": 3,
            },
        },
    }


@pytest.fixture
def clean_results():
    """无任何异常的基线数据"""
    return {
        "inflammation_classification": {
            "labels": ["缓解期", "缓解期"],
            "report_dates": ["2026-03-01", "2026-03-15"],
        },
        "abnormal_summary": {},
        "zscore_outliers": {},
        "cv_stability": {
            "WBC": {
                "cv": 0.05,
                "mean": 6.0,
                "std": 0.3,
                "stability": "稳定",
                "risk_level": "低",
                "n_points": 2,
            },
        },
        "linear_regression": {
            "WBC": {
                "slope": 0.01,
                "intercept": 6.0,
                "r2": 0.2,
                "trend": "平稳",
                "slope_per_day": 0.01,
                "n_points": 2,
            },
        },
    }


# ═════════════════════════════════════════════════════════════════════
# 1. 炎症告警
# ═════════════════════════════════════════════════════════════════════


class TestAlertInflammation:
    def test_acute_returns_critical(self, acute_results):
        alerts = _alert_inflammation(acute_results)
        assert len(alerts) == 1
        assert alerts[0]["level"] == "CRITICAL"
        assert "急性期" in alerts[0]["message"]

    def test_remission_no_alerts(self, clean_results):
        alerts = _alert_inflammation(clean_results)
        assert len(alerts) == 0

    def test_missing_inflam_no_crash(self):
        alerts = _alert_inflammation({})
        assert alerts == []


# ═════════════════════════════════════════════════════════════════════
# 2. 参考范围告警
# ═════════════════════════════════════════════════════════════════════


class TestAlertReferenceRange:
    def test_abnormal_metrics_returned(self, acute_results):
        alerts = _alert_reference_range(acute_results)
        assert len(alerts) == 2
        metrics = {a["metric"] for a in alerts}
        assert "hs-CRP" in metrics
        assert "RDW-SD" in metrics

    def test_three_or_more_abnormal_is_critical(self, acute_results):
        # 模拟 3 次异常 → CRITICAL
        acute_results["abnormal_summary"]["WBC"] = {
            "ref_range": "3.5-9.5",
            "abnormal_dates": ["d1", "d2", "d3"],
            "n_abnormal": 3,
        }
        alerts = _alert_reference_range(acute_results)
        wbc_alert = [a for a in alerts if a["metric"] == "WBC"][0]
        assert wbc_alert["level"] == "CRITICAL"


# ═════════════════════════════════════════════════════════════════════
# 3. Z-score 告警
# ═════════════════════════════════════════════════════════════════════


class TestAlertZscore:
    def test_severe_outlier_critical(self, acute_results):
        alerts = _alert_zscore(acute_results)
        assert any(a["level"] == "CRITICAL" and a["metric"] == "WBC" for a in alerts)

    def test_no_alerts_on_clean(self, clean_results):
        alerts = _alert_zscore(clean_results)
        assert alerts == []


# ═════════════════════════════════════════════════════════════════════
# 4. 变异系数告警
# ═════════════════════════════════════════════════════════════════════


class TestAlertVariability:
    def test_high_variability_warning(self, acute_results):
        alerts = _alert_variability(acute_results)
        assert any(a["level"] == "WARNING" and a["metric"] == "PLT" for a in alerts)

    def test_low_variability_no_alert(self, clean_results):
        alerts = _alert_variability(clean_results)
        assert alerts == []


# ═════════════════════════════════════════════════════════════════════
# 5. 趋势告警
# ═════════════════════════════════════════════════════════════════════


class TestAlertTrend:
    def test_upward_trend_warning(self, acute_results):
        alerts = _alert_trend(acute_results)
        hs_crp = [a for a in alerts if a["metric"] == "hs-CRP"]
        assert len(hs_crp) == 1
        assert hs_crp[0]["level"] == "WARNING"
        assert "上升" in hs_crp[0]["message"]

    def test_downward_trend_info(self, acute_results):
        alerts = _alert_trend(acute_results)
        crp = [a for a in alerts if a["metric"] == "CRP"]
        assert len(crp) == 1
        assert crp[0]["level"] == "INFO"
        assert "下降" in crp[0]["message"]

    def test_no_trend_alert_low_r2(self, acute_results):
        # R² < 0.7 时不触发
        acute_results["linear_regression"]["hs-CRP"]["r2"] = 0.3
        alerts = _alert_trend(acute_results)
        hs_crp = [a for a in alerts if a["metric"] == "hs-CRP"]
        assert len(hs_crp) == 0


# ═════════════════════════════════════════════════════════════════════
# 6. 聚合测试
# ═════════════════════════════════════════════════════════════════════


class TestGenerateAlerts:
    def test_aggregation_order(self, acute_results):
        """CRITICAL 排在 WARNING 之前。"""
        alerts = generate_alerts(acute_results)
        levels = [a["level"] for a in alerts]
        assert levels == sorted(levels, key=lambda x: {"CRITICAL": 0, "WARNING": 1, "INFO": 2}[x])

    def test_clean_returns_empty(self, clean_results):
        alerts = generate_alerts(clean_results)
        assert alerts == []

    def test_acute_has_item(self, acute_results):
        alerts = generate_alerts(acute_results)
        assert len(alerts) >= 5  # 1 inflam + 2 ref + 1 zscore + 1 var + 2 trend

    def test_alerts_are_serializable(self, acute_results):
        alerts = generate_alerts(acute_results)
        dumped = json.dumps(alerts, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert len(loaded) == len(alerts)


class TestPrintAlerts:
    def test_print_alerts_no_crash(self, acute_results, caplog):
        import logging

        caplog.set_level(logging.INFO)
        alerts = generate_alerts(acute_results)
        print_alerts(alerts)
        text = " ".join(rec.getMessage() for rec in caplog.records)
        assert len(text) > 0
        assert "CRITICAL" in text or "WARNING" in text

    def test_print_alerts_empty(self, clean_results, caplog):
        import logging

        caplog.set_level(logging.INFO)
        alerts = generate_alerts(clean_results)
        print_alerts(alerts)
        text = " ".join(rec.getMessage() for rec in caplog.records)
        assert "无异常告警" in text
