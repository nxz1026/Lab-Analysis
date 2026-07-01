"""tests.test_gen_final_report_pdf — PDF 生成模块单测 (smoke)。"""

from __future__ import annotations

from pathlib import Path

from lab_analysis.gen_final_report_pdf import md_to_pdf


class TestMdToPdf:
    def test_missing_md_returns_false(self, tmp_path):
        result = md_to_pdf(Path("/nonexistent/test.md"), tmp_path / "out.md")
        assert result is False
