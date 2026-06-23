"""quant_visualizer.py 单元测试.

覆盖:
- render_metrics_chart: 5 metric 输入 → 合法 PNG bytes
- render_metrics_html: 含 base64 data URI 的 HTML
- _extract_metric_value: 各种 metric 类型 + available=False
- render_trend_chart: 多 report 输入 → PNG bytes
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lab_analysis.quant_visualizer import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    _extract_metric_value,
    render_metrics_chart,
    render_metrics_html,
    render_trend_chart,
)

# ---- _extract_metric_value ----


def test_extract_entity_f1():
    v, ok = _extract_metric_value({"available": True, "f1": 0.88}, "entity_f1")
    assert v == 0.88
    assert ok is True


def test_extract_section_coverage():
    v, ok = _extract_metric_value({"available": True, "coverage_rate": 0.95}, "section_coverage")
    assert v == 0.95
    assert ok is True


def test_extract_confidence():
    v, ok = _extract_metric_value({"available": True, "dspy_confidence": 0.8}, "confidence")
    assert v == 0.8
    assert ok is True


def test_extract_failure_rate_ok():
    v, ok = _extract_metric_value({"available": True, "is_failure": False}, "failure_rate")
    assert v == 0.0
    assert ok is True


def test_extract_failure_rate_failed():
    v, ok = _extract_metric_value({"available": True, "is_failure": True}, "failure_rate")
    assert v == 1.0
    assert ok is True


def test_extract_unavailable():
    v, ok = _extract_metric_value({"available": False, "reason": "x"}, "entity_f1")
    assert v is None
    assert ok is False


def test_extract_empty_metric():
    v, ok = _extract_metric_value({}, "entity_f1")
    assert v is None
    assert ok is False


# ---- render_metrics_chart ----


@pytest.fixture
def sample_metrics() -> dict:
    return {
        "entity_f1": {"available": True, "f1": 0.88},
        "section_coverage": {"available": True, "coverage_rate": 1.0},
        "entity_recall": {"available": True, "recall_rate": 0.92},
        "confidence": {"available": True, "dspy_confidence": 0.88},
        "failure_rate": {"available": True, "is_failure": False, "confidence": 0.88},
        "feedback_delta": {"available": False, "reason": "无 corrections"},
        "cross_modality_consistency": {"available": False, "reason": "no dspy data"},
    }


def test_render_metrics_chart_returns_png(sample_metrics):
    png = render_metrics_chart(sample_metrics)
    # PNG magic number: 89 50 4E 47 0D 0A 1A 0A
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000  # 不是空图


def test_render_metrics_chart_unavailable_metrics():
    """全部 metric 不可用, 应仍能生成 PNG (灰色条)."""
    metrics = {
        "entity_f1": {"available": False},
        "section_coverage": {"available": False},
        "entity_recall": {"available": False},
        "confidence": {"available": False},
        "failure_rate": {"available": False},
    }
    png = render_metrics_chart(metrics)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_metrics_chart_with_thresholds(sample_metrics):
    """自定义阈值能正常生成."""
    thresholds = {
        "entity_f1": (0.95, "f1 ≥ 0.95"),  # 0.88 < 0.95 → 红色条
    }
    png = render_metrics_chart(sample_metrics, thresholds=thresholds)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_metrics_chart_with_failure(sample_metrics):
    """failure_rate 显示 FAIL 时图仍能画."""
    sample_metrics["failure_rate"]["is_failure"] = True
    png = render_metrics_chart(sample_metrics)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


# ---- render_metrics_html ----


def test_render_metrics_html_basic(sample_metrics):
    report = {
        "deid": "TEST",
        "std_ts": "20260101_100000",
        "dspy_ts": "20260101_110000",
        "generated_at": "2026-06-22T12:00:00",
        "metrics": sample_metrics,
    }
    html = render_metrics_html(report)
    assert "data:image/png;base64," in html
    assert "TEST" in html
    assert "<h1>" in html
    assert "<details>" in html
    assert "passed-ok" in html


def test_render_metrics_html_with_chart_bytes(sample_metrics):
    """传 chart_bytes 时不再调 render_metrics_chart."""
    report = {"deid": "X", "metrics": sample_metrics}
    pre_bytes = render_metrics_chart(sample_metrics)
    html = render_metrics_html(report, chart_bytes=pre_bytes)
    # base64 应是 pre_bytes 的 base64
    import base64

    expected_b64 = base64.b64encode(pre_bytes).decode("ascii")
    assert expected_b64 in html


def test_render_metrics_html_unavailable_table_row(sample_metrics):
    """available=False metric 在 HTML table 里以 N/A 展示."""
    sample_metrics["entity_f1"]["available"] = False
    sample_metrics["entity_f1"]["reason"] = "std_md 缺失"
    report = {"deid": "X", "metrics": sample_metrics}
    html = render_metrics_html(report)
    assert "N/A" in html
    assert "std_md 缺失" in html
    # T17: N/A 用 details 折叠块 (passed-skip 样式)
    assert "<details>" in html
    assert "passed-skip" in html


def test_render_metrics_html_feedback_delta_with_corrections(sample_metrics):
    """feedback_delta available=True 时 HTML 含 n_corrections 详情."""
    sample_metrics["feedback_delta"] = {
        "available": True,
        "n_corrections": 3,
        "avg_delta_confidence": 0.1,
        "max_delta": 0.2,
        "min_delta": -0.05,
    }
    report = {"deid": "X", "metrics": sample_metrics}
    html = render_metrics_html(report)
    assert "n_corrections=3" in html
    assert "avg_Δ=+0.1000" in html


def test_render_metrics_html_feedback_delta_n_zero(sample_metrics):
    """U4: feedback_delta n_corrections=0 也算 available=True, 作为 OK 折叠块."""
    sample_metrics["feedback_delta"] = {
        "available": True,
        "n_corrections": 0,
        "avg_delta_confidence": 0.0,
        "max_delta": 0.0,
        "min_delta": 0.0,
    }
    report = {"deid": "X", "metrics": sample_metrics}
    html = render_metrics_html(report)
    assert "n_corrections=0" in html
    assert "passed-ok" in html
    assert "<details>" in html


# ---- render_trend_chart ----


def test_render_trend_chart_basic():
    reports = [
        {
            "std_ts": "20260101_100000",
            "metrics": {
                "entity_f1": {"f1": 0.7},
                "section_coverage": {"coverage_rate": 0.8},
                "entity_recall": {"recall_rate": 0.75},
                "confidence": {"dspy_confidence": 0.8},
            },
        },
        {
            "std_ts": "20260201_100000",
            "metrics": {
                "entity_f1": {"f1": 0.85},
                "section_coverage": {"coverage_rate": 0.95},
                "entity_recall": {"recall_rate": 0.88},
                "confidence": {"dspy_confidence": 0.85},
            },
        },
    ]
    png = render_trend_chart(reports)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000


def test_render_trend_chart_empty_reports_raises():
    """T18: 空 reports 应抛 ValueError 而不是画空白图."""
    with pytest.raises(ValueError, match="不能为空"):
        render_trend_chart([])


def test_render_trend_chart_x_key():
    """T18: x_key 参数控制 X 轴 label 来源."""
    reports = [
        {
            "std_ts": "20260101_100000",
            "deid": "P1",
            "metrics": {
                "entity_f1": {"f1": 0.7},
                "section_coverage": {"coverage_rate": 0.8},
                "entity_recall": {"recall_rate": 0.75},
                "confidence": {"dspy_confidence": 0.8},
            },
        },
        {
            "std_ts": "20260201_100000",
            "deid": "P2",
            "metrics": {
                "entity_f1": {"f1": 0.85},
                "section_coverage": {"coverage_rate": 0.95},
                "entity_recall": {"recall_rate": 0.88},
                "confidence": {"dspy_confidence": 0.85},
            },
        },
    ]
    # 默认 x_key='std_ts' 也能成功画
    png1 = render_trend_chart(reports, x_key="std_ts")
    assert png1[:8] == b"\x89PNG\r\n\x1a\n"
    # x_key='deid' 也能成功画
    png2 = render_trend_chart(reports, x_key="deid")
    assert png2[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_trend_chart_annotations():
    """T18: 阈值参考线 + 数值标签."""
    reports = [
        {
            "std_ts": "run1",
            "metrics": {
                "entity_f1": {"f1": 0.75},
                "section_coverage": {"coverage_rate": 0.85},
                "entity_recall": {"recall_rate": 0.80},
                "confidence": {"dspy_confidence": 0.82},
            },
        },
    ]
    png = render_trend_chart(reports, figsize=(10, 5))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1500  # 有标签的图应大一些


# ---- render_metrics_html 响应式 + 折叠 (T17) ----


def test_render_metrics_html_responsive_css(sample_metrics):
    """T17: HTML 含 @media 响应式 CSS."""
    report = {"deid": "RESP", "metrics": sample_metrics}
    html = render_metrics_html(report)
    assert "@media (max-width: 720px)" in html
    assert "font-size" in html.lower()


def test_render_metrics_html_dark_mode_css(sample_metrics):
    """T17: HTML 含 @media (prefers-color-scheme: dark) CSS."""
    report = {"deid": "DARK", "metrics": sample_metrics}
    html = render_metrics_html(report)
    assert "prefers-color-scheme: dark" in html


def test_render_metrics_html_details_collapsible(sample_metrics):
    """T17: 每个 metric 都包在 <details> 里, 可折叠."""
    report = {"deid": "COL", "metrics": sample_metrics}
    html = render_metrics_html(report)
    # 6 metric 全部为 details
    assert html.count("<details>") == len(sample_metrics)
    assert html.count("<summary>") == len(sample_metrics)
    assert html.count("</details>") == len(sample_metrics)
    # 包含 OK/FAIL/SKIP 状态色类
    assert "passed-ok" in html
    # entity_f1 详情应包含 f1 值
    assert "f1=" in html


def test_render_metrics_html_pass_fail_styles(sample_metrics):
    """T17: 各 metric 根据阈值显示 OK/FAIL 状态色."""
    # 把 entity_f1 设为低于阈值 → 应 FAIL
    sample_metrics["entity_f1"]["f1"] = 0.5
    report = {"deid": "FAIL", "metrics": sample_metrics}
    html = render_metrics_html(report)
    assert "passed-fail" in html
    assert "FAIL" in html


# ---- DEFAULT_THRESHOLDS ----


def test_default_thresholds_have_four_metrics():
    assert "entity_f1" in DEFAULT_THRESHOLDS
    assert "section_coverage" in DEFAULT_THRESHOLDS
    assert "entity_recall" in DEFAULT_THRESHOLDS
    assert "confidence" in DEFAULT_THRESHOLDS


def test_render_metrics_chart_with_real_fixture():
    """用 committed PASS fixture 跑一遍真实路径."""
    fix = PROJECT_ROOT / "tests" / "fixtures" / "quant_eval_sample_pass.json"
    if not fix.exists():
        pytest.skip("fixture 缺失")
    report = json.loads(fix.read_text(encoding="utf-8"))
    png = render_metrics_chart(report["metrics"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    html = render_metrics_html(report, chart_bytes=png)
    assert "CI_FIXTURE_PASS" in html


def test_render_metrics_chart_with_cross_modality(sample_metrics):
    """#7 cross_modality_consistency 可被画进 PNG."""
    sample_metrics["cross_modality_consistency"] = {
        "available": True,
        "accuracy": 0.85,
    }
    png = render_metrics_chart(sample_metrics)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_metrics_html_with_cross_modality(sample_metrics):
    """#7 cross_modality_consistency 出现在 HTML details 中."""
    sample_metrics["cross_modality_consistency"] = {
        "available": True,
        "accuracy": 0.85,
    }
    report = {"deid": "X", "metrics": sample_metrics}
    html = render_metrics_html(report)
    assert "cross_modality_consistency" in html
    assert "accuracy=0.8500" in html


def test_render_metrics_html_print_button(sample_metrics):
    """U7: HTML 含 Print/PDF 按钮 + @media print 隐藏."""
    report = {"deid": "PRINT", "metrics": sample_metrics}
    html = render_metrics_html(report)
    assert "print-btn" in html
    assert "window.print()" in html
    assert "@media print" in html
