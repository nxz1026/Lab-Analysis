"""tests.test_dspy_modules — DSPy 模块基本验证测试

覆盖：
- 各模块 Signature 字段完整性
- forward() 不抛异常（mock LM 模式下）
- prompt_inspector 工具函数功能
"""

import pytest

# ── 跳过：DSPy 未安装时跳过所有测试 ──────────────────────────────────
try:
    import dspy  # noqa: F401

    HAS_DSPY = True
except ImportError:
    HAS_DSPY = False

pytestmark = pytest.mark.skipif(not HAS_DSPY, reason="dspy-ai not installed")


# ═════════════════════════════════════════════════════════════════════
# 1. Signature 字段完整性
# ═════════════════════════════════════════════════════════════════════
class TestFinalReportSignature:
    def test_signature_has_required_fields(self):
        from lab_analysis.dspy_modules.final_report_generator import FinalReportSignature

        sig = FinalReportSignature
        in_fields = set(sig.input_fields.keys())
        out_fields = set(sig.output_fields.keys())
        # 输入字段
        for f in [
            "patient_info",
            "lab_summary",
            "analysis_results",
            "literature_interpretation",
            "mri_analysis",
            "quality_control",
        ]:
            assert f in in_fields, f"缺少输入字段 {f}"
        # 输出字段
        for f in [
            "report_title",
            "section_1_basic_info",
            "section_2_lab_analysis",
            "section_3_mri_analysis",
            "section_4_multidisciplinary",
            "section_5_diagnosis",
            "section_6_consistency",
            "section_7_action_plan",
            "section_8_followup",
            "section_9_prognosis",
            "confidence",
        ]:
            assert f in out_fields, f"缺少输出字段 {f}"

    def test_signature_input_output_field_counts(self):
        from lab_analysis.dspy_modules.final_report_generator import FinalReportSignature

        sig = FinalReportSignature
        assert len(sig.input_fields) >= 6
        assert len(sig.output_fields) >= 11

    def test_signature_can_instantiate(self):
        from lab_analysis.dspy_modules.final_report_generator import FinalReportGenerator

        module = FinalReportGenerator()
        assert hasattr(module, "generate")
        assert module.generate is not None


class TestLiteratureInterpreterSignature:
    def test_signature_has_required_fields(self):
        from lab_analysis.dspy_modules.literature_interpreter import (
            LiteratureInterpretationSignature,
        )

        sig = LiteratureInterpretationSignature
        in_fields = set(sig.input_fields.keys())
        out_fields = set(sig.output_fields.keys())
        assert "patient_id" in in_fields
        assert "analysis_results" in in_fields
        assert "literature_results" in in_fields
        assert "interpretation" in out_fields
        assert "confidence" in out_fields

    def test_module_can_instantiate(self):
        from lab_analysis.dspy_modules.literature_interpreter import LiteratureInterpreterModule

        module = LiteratureInterpreterModule()
        assert hasattr(module, "interpret")


class TestMRIAnalyzerSignature:
    def test_signature_has_required_fields(self):
        from lab_analysis.dspy_modules.mri_analyzer import MRIAnalysisSignature

        sig = MRIAnalysisSignature
        in_fields = set(sig.input_fields.keys())
        out_fields = set(sig.output_fields.keys())
        assert "image_description" in in_fields
        assert "report_findings" in in_fields
        assert "clinical_context" in in_fields
        assert "consistency_evaluation" in out_fields
        assert "confidence_score" in out_fields

    def test_module_can_instantiate(self):
        from lab_analysis.dspy_modules.mri_analyzer import MRIAnalysisModule

        module = MRIAnalysisModule()
        assert hasattr(module, "forward")
        assert hasattr(module, "predictor")


class TestLabDataExtractorSignature:
    def test_signature_has_required_fields(self):
        from lab_analysis.dspy_modules.lab_data_extractor import LabDataExtractionSignature

        sig = LabDataExtractionSignature
        in_fields = set(sig.input_fields.keys())
        out_fields = set(sig.output_fields.keys())
        assert "image_description" in in_fields
        assert "patient_id" in out_fields
        assert "report_date" in out_fields

    def test_module_can_instantiate(self):
        from lab_analysis.dspy_modules.lab_data_extractor import LabDataExtractor

        module = LabDataExtractor()
        assert hasattr(module, "extract")


# ═════════════════════════════════════════════════════════════════════
# 2. prompt_inspector 工具函数
# ═════════════════════════════════════════════════════════════════════
class TestPromptInspector:
    def test_extract_signature_info_without_dspy_lm(self):
        """无需 LM 配置即可提取 signature 信息"""
        from lab_analysis.dspy_modules.final_report_generator import FinalReportSignature
        from lab_analysis.dspy_modules.prompt_inspector import extract_signature_info

        info = extract_signature_info(FinalReportSignature)
        assert "signature_name" in info
        assert "input_fields" in info
        assert "output_fields" in info
        assert "FinalReportSignature" in info["signature_name"]

    def test_extract_module_prompts_returns_structure(self):
        """extract_module_prompts 返回正确的数据结构"""
        from lab_analysis.dspy_modules.final_report_generator import FinalReportGenerator
        from lab_analysis.dspy_modules.prompt_inspector import extract_module_prompts

        module = FinalReportGenerator()
        result = extract_module_prompts(module, module_name="final_report_generator")
        assert result["module_name"] == "final_report_generator"
        assert "predictors" in result

    def test_safe_str_truncates_long_strings(self):
        from lab_analysis.dspy_modules.prompt_inspector import safe_str

        short = safe_str("hello")
        assert short == "hello"

        long_str = "x" * 2000
        truncated = safe_str(long_str, max_length=100)
        assert len(truncated) < len(long_str)
        assert "截断" in truncated

    def test_extract_field_desc_handles_none(self):
        from lab_analysis.dspy_modules.prompt_inspector import extract_field_desc

        # Should not crash on None or empty input
        result = extract_field_desc(None)
        assert result == ""

    def test_save_prompts_to_json_creates_file(self, tmp_path):
        from lab_analysis.dspy_modules.prompt_inspector import save_prompts_to_json

        data = {"module_name": "test", "predictors": []}
        path = save_prompts_to_json("test_module", data, tmp_path)
        assert path.exists()
        assert path.suffix == ".json"
        import json

        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert loaded["module_name"] == "test"

    def test_save_prompts_to_markdown_creates_file(self, tmp_path):
        from lab_analysis.dspy_modules.prompt_inspector import save_prompts_to_markdown

        data = {
            "module_name": "test",
            "module_type": "TestModule",
            "predictors": [],
            "total_demos": 0,
        }
        path = save_prompts_to_markdown("test_module", data, tmp_path)
        assert path.exists()
        assert path.suffix == ".md"
        content = path.read_text(encoding="utf-8")
        assert "test_module" in content


# ═════════════════════════════════════════════════════════════════════
# 3. 模拟 forward() 不抛异常
# ═════════════════════════════════════════════════════════════════════
class TestForwardWithMockedLM:
    def test_final_report_forward_with_mock(self, monkeypatch):
        """mock DSPy 的 forward 验证不抛异常"""
        from lab_analysis.dspy_modules.final_report_generator import FinalReportGenerator

        module = FinalReportGenerator()

        # monkeypatch forward to return a mock prediction
        class MockPrediction:
            report_title = "Test Title"
            section_1_basic_info = "Basic info"
            section_2_lab_analysis = "Lab analysis"
            section_3_mri_analysis = "MRI"
            section_4_multidisciplinary = "Multi"
            section_5_diagnosis = "Diagnosis"
            section_6_consistency = "Consistency"
            section_7_action_plan = "Action"
            section_8_followup = "Followup"
            section_9_prognosis = "Prognosis"
            confidence = 0.85

        monkeypatch.setattr(module, "forward", lambda *a, **kw: MockPrediction())

        result = module(
            patient_info={},
            lab_summary="test",
            analysis_results={},
            literature_interpretation="test",
            mri_analysis="test",
            quality_control="test",
        )
        assert result.report_title == "Test Title"
        assert result.confidence == 0.85

    def test_mri_forward_with_mock(self, monkeypatch):
        from lab_analysis.dspy_modules.mri_analyzer import MRIAnalysisModule

        module = MRIAnalysisModule()

        class MockResult:
            consistency_analysis = "consistent"
            confidence_score = 0.9

        monkeypatch.setattr(module, "forward", lambda *a, **kw: MockResult())

        result = module(
            image_description="MRI scan", report_findings="normal", clinical_context="adult male"
        )
        assert result.consistency_analysis == "consistent"
        assert result.confidence_score == 0.9
