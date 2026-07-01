"""tests.test_report_schema — 报告 Schema 单测。"""

from __future__ import annotations

import pytest

from lab_analysis.report_schema import REPORT_MD_TEMPLATE, REPORT_SECTIONS, build_section_field_name


class TestReportSections:
    def test_has_nine_sections(self):
        assert len(REPORT_SECTIONS) == 9

    def test_each_section_is_tuple(self):
        for s in REPORT_SECTIONS:
            assert isinstance(s, tuple) and len(s) == 3

    def test_first_section(self):
        assert REPORT_SECTIONS[0][0] == "basic_info"

    def test_last_section(self):
        assert REPORT_SECTIONS[-1][0] == "prognosis"


class TestBuildSectionFieldName:
    def test_basic_info(self):
        assert build_section_field_name("basic_info") == "section_1_basic_info"

    def test_prognosis(self):
        assert build_section_field_name("prognosis") == "section_9_prognosis"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="未知章节"):
            build_section_field_name("nonexistent")


class TestReportMdTemplate:
    def test_is_string(self):
        assert isinstance(REPORT_MD_TEMPLATE, str)

    def test_contains_section_placeholders(self):
        for i in range(1, 10):
            assert f"section_{i}_" in REPORT_MD_TEMPLATE

    def test_has_title(self):
        assert "{report_title}" in REPORT_MD_TEMPLATE
