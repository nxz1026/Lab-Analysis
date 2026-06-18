"""tests.test_extract_lab_data — 检验数据结构化提取测试"""

from lab_analysis.extract_lab_data import generate_metadata_md


class TestGenerateMetadataMd:
    """metadata.md 生成（核心字段：身份证号）"""

    def test_field_label(self):
        data = {
            "patient_id": "110101199003078888",
            "report_date": "2026-03-24",
            "report_type": "outpatient",
        }
        md = generate_metadata_md(data, "110101199003078888")
        # 必须是「身份证号」而非旧的「患者ID」
        assert "| 身份证号 |" in md
        assert "患者ID" not in md

    def test_uses_validated_id_first(self):
        md = generate_metadata_md({"patient_id": "old_id"}, "real_id")
        assert "real_id" in md

    def test_falls_back_to_data(self):
        md = generate_metadata_md({"patient_id": "extracted_id"}, "")
        assert "extracted_id" in md
