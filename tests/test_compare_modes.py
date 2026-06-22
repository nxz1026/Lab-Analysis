"""tests.test_compare_modes — 双模式报告对比测试"""

import json

import pytest

from lab_analysis.compare_report_modes import (
    _KEY_ENTITIES,
    _calc_overlap_rate,
    _count_entities,
    _parse_std_sections,
    compare_reports,
    format_comparison_md,
    render_comparison_chart,
)

# ═════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_std_md():
    return """# 最终综合临床诊断报告
**患者**: 张三 | 男 38岁 | 检查编号: 001
**报告日期**: 2026年06月20日

---

## 一、患者基本信息与就诊背景

患者张三，男，38岁，因反复上腹痛就诊。

## 二、检验数据与炎症状态综合分析

hs-CRP 呈上升趋势，提示炎症活跃。

## 三、MRI影像学综合分析

MRI 显示胰腺形态正常。

## 四、多学科联合诊断意见

建议结合临床。

## 五、核心诊断结论与鉴别诊断

慢性胰腺炎可能性大。

## 六、结论一致性评估

检验与影像结论一致。

## 七、行动计划

[URGENT] 建议进一步检查。

## 八、随访与监测计划

每月复查 hs-CRP。

## 九、预后评估

预后良好。
"""


@pytest.fixture
def sample_dspy_sections():
    return {
        "title": "最终综合临床诊断报告",
        "basic_info": "患者张三，男，38岁。",
        "lab_analysis": "hs-CRP 上升，CRP 正常，提示炎症。",
        "mri_analysis": "MRI 正常。",
        "multidisciplinary": "综合意见。",
        "diagnosis": "慢性胰腺炎。",
        "consistency": "一致。",
        "action_plan": "进一步检查。",
        "followup": "每月复查。",
        "prognosis": "良好。",
    }


# ═════════════════════════════════════════════════════════════════════
# 1. 章节解析
# ═════════════════════════════════════════════════════════════════════


class TestParseStdSections:
    def test_parses_all_9_sections(self, sample_std_md):
        sections = dict(_parse_std_sections(sample_std_md))
        assert len(sections) == 9
        assert "section_1_basic_info" in sections
        assert "section_9_prognosis" in sections

    def test_content_matches(self, sample_std_md):
        sections = dict(_parse_std_sections(sample_std_md))
        info = sections["section_1_basic_info"]
        assert "张三" in info
        assert "38岁" in info

    def test_empty_md_returns_empty_strings(self):
        sections = dict(_parse_std_sections(""))
        assert len(sections) == 9
        assert all(v == "" for v in sections.values())


# ═════════════════════════════════════════════════════════════════════
# 2. 重叠率计算
# ═════════════════════════════════════════════════════════════════════


class TestCalcOverlapRate:
    def test_identical_texts(self):
        assert _calc_overlap_rate("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert _calc_overlap_rate("abc", "xyz") == 0.0

    def test_partial_overlap(self):
        r = _calc_overlap_rate("hello world", "hello there")
        assert 0.0 < r < 1.0

    def test_both_empty(self):
        assert _calc_overlap_rate("", "") == 1.0

    def test_one_empty(self):
        assert _calc_overlap_rate("hello", "") == 0.0


# ═════════════════════════════════════════════════════════════════════
# 3. 实体计数
# ═════════════════════════════════════════════════════════════════════


class TestCountEntities:
    def test_counts_matching_entities(self):
        counts = _count_entities("hs-CRP is elevated, CRP also high", _KEY_ENTITIES)
        assert counts.get("hs-CRP", 0) >= 1
        assert counts.get("CRP", 0) >= 1

    def test_no_match_returns_empty(self):
        counts = _count_entities("nothing relevant here", _KEY_ENTITIES)
        # "inflammation" won't match Chinese, but "CRP" won't match either
        assert all(v == 0 for v in counts.values()) or not counts


# ═════════════════════════════════════════════════════════════════════
# 4. 完整对比流程
# ═════════════════════════════════════════════════════════════════════


class TestCompareReports:
    def test_returns_expected_keys(self, sample_std_md, sample_dspy_sections):
        result = compare_reports(sample_std_md, sample_dspy_sections, dspy_confidence=0.85)
        assert "std_total_length" in result
        assert "dspy_total_length" in result
        assert "avg_overlap_rate" in result
        assert "dspy_confidence" in result
        assert result["dspy_confidence"] == 0.85
        assert len(result["section_diffs"]) == 9

    def test_serializable(self, sample_std_md, sample_dspy_sections):
        result = compare_reports(sample_std_md, sample_dspy_sections)
        dumped = json.dumps(result, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert loaded["n_sections"] == 9


class TestFormatComparisonMd:
    def test_generates_md(self, sample_std_md, sample_dspy_sections):
        result = compare_reports(sample_std_md, sample_dspy_sections)
        md = format_comparison_md(result)
        assert "Standard" in md
        assert "DSPy" in md
        assert len(md) > 100

# ═════════════════════════════════════════════════════════════════════
# render_comparison_chart (PNG) tests
# ═════════════════════════════════════════════════════════════════════

def test_render_comparison_chart_basic_produces_png():
    """render_comparison_chart 应输出合法 PNG bytes (>1KB)."""
    std_md = (
        "# 报告\n"
        "## 一、基本信息\n"
        "患者张三，男 60 岁。\n\n"
        "## 二、检验分析\n"
        "hs-CRP 偏高。\n"
    )
    dspy_sections = {
        "basic_info": "Patient: Zhang San, 60yo male.",
        "lab_analysis": "hs-CRP elevated.",
    }
    result = compare_reports(std_md, dspy_sections, dspy_confidence=0.85)
    png = render_comparison_chart(result)
    assert isinstance(png, bytes)
    assert len(png) > 1024, f"PNG too small: {len(png)}B"
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "Not a valid PNG"


def test_render_comparison_chart_empty_raises():
    """section_diffs 为空应抛 ValueError."""
    import pytest
    with pytest.raises(ValueError, match="section_diffs is empty"):
        render_comparison_chart({"section_diffs": []})


def test_render_comparison_chart_custom_title_and_figsize():
    """支持自定义标题 + figsize."""
    std_md = "## 一、基本信息\n张三"
    dspy_sections = {"basic_info": "Zhang San"}
    result = compare_reports(std_md, dspy_sections)
    png = render_comparison_chart(result, title="My Custom Title", figsize=(8, 4))
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 500
