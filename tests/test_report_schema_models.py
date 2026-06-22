"""report_schema_models Pydantic 强校验单元测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lab_analysis.report_schema_models import (
    MIN_SECTION_LENGTH,
    SectionBlock,
    build_sections_from_dict,
    try_validate_sections,
    validate_final_report_dict,
)


# -------------------- helper --------------------


def _make_sections(**overrides) -> dict[str, str]:
    """生成 9 章节 + title 的 raw dict, 每节默认填 30 字符。"""
    base = {k: f"{k}_content_" + "x" * 20 for k in [
        "basic_info", "lab_analysis", "mri_analysis", "multidisciplinary",
        "diagnosis", "consistency", "action_plan", "followup", "prognosis",
    ]}
    base["title"] = "测试报告"
    base.update(overrides)
    return base


# -------------------- SectionBlock --------------------


def test_section_block_valid():
    block = SectionBlock(name="basic_info", content="x" * 20)
    assert block.name == "basic_info"
    assert len(block.content) == 20


def test_section_block_unknown_name():
    with pytest.raises(ValidationError) as exc_info:
        SectionBlock(name="unknown_section", content="x" * 20)
    assert "未知 section" in str(exc_info.value)


def test_section_block_too_short():
    with pytest.raises(ValidationError) as exc_info:
        SectionBlock(name="basic_info", content="x" * 5)
    assert "过短" in str(exc_info.value)


def test_section_block_whitespace_only_too_short():
    with pytest.raises(ValidationError):
        SectionBlock(name="basic_info", content="   \n\t  ")  # strip 后 0 字符


# -------------------- build_sections_from_dict --------------------


def test_build_sections_all_valid():
    raw = _make_sections()
    sections = build_sections_from_dict(raw)
    assert sections.title == "测试报告"
    assert len(sections.basic_info.content) >= MIN_SECTION_LENGTH


def test_build_sections_missing_key_filled_empty():
    raw = _make_sections()
    raw.pop("lab_analysis")
    with pytest.raises(ValidationError):
        build_sections_from_dict(raw)


def test_build_sections_empty_content_fail():
    raw = _make_sections(diagnosis="")
    with pytest.raises(ValidationError):
        build_sections_from_dict(raw)


def test_build_sections_title_filled_when_missing():
    raw = _make_sections()
    raw.pop("title")
    sections = build_sections_from_dict(raw)
    assert sections.title == "(无标题)"


# -------------------- try_validate_sections (soft) --------------------


def test_try_validate_sections_ok():
    ok, errs = try_validate_sections(_make_sections())
    assert ok is True
    assert errs == []


def test_try_validate_sections_returns_errors():
    ok, errs = try_validate_sections(_make_sections(diagnosis=""))
    assert ok is False
    assert len(errs) > 0
    assert any("diagnosis" in e for e in errs)


def test_try_validate_sections_multiple_errors():
    ok, errs = try_validate_sections(
        _make_sections(diagnosis="", action_plan="x")
    )
    assert ok is False
    assert len(errs) >= 2  # diagnosis + action_plan


# -------------------- validate_final_report_dict --------------------


def _make_full_doc(**overrides) -> dict:
    """生成完整 final_report JSON dict (含 sections)。"""
    raw = _make_sections()
    md = "# 测试报告\n\n**患者**: x | y | z\n\n" + "内容\n" * 30
    doc = {
        "generated": "2026-06-22 11:00:00",
        "model": "deepseek-chat",
        "mode": "dspy",
        "patient_id": "123",
        "confidence": 0.85,
        "report_markdown": md,
        "sections": raw,
        "prompts_dir": "/tmp",
    }
    doc.update(overrides)
    return doc


def test_validate_full_doc_ok():
    parsed = validate_final_report_dict(_make_full_doc())
    assert parsed.mode == "dspy"
    assert parsed.confidence == 0.85
    assert len(parsed.sections.basic_info.content) > 10


def test_validate_full_doc_invalid_mode():
    with pytest.raises(ValidationError) as exc_info:
        validate_final_report_dict(_make_full_doc(mode="invalid"))
    assert "mode" in str(exc_info.value)


def test_validate_full_doc_confidence_out_of_range():
    with pytest.raises(ValidationError):
        validate_final_report_dict(_make_full_doc(confidence=1.5))
    with pytest.raises(ValidationError):
        validate_final_report_dict(_make_full_doc(confidence=-0.1))


def test_validate_full_doc_md_too_short():
    with pytest.raises(ValidationError):
        validate_final_report_dict(_make_full_doc(report_markdown="x"))


def test_validate_full_doc_missing_sections():
    doc = _make_full_doc()
    doc["sections"].pop("diagnosis")
    with pytest.raises(ValidationError):
        validate_final_report_dict(doc)


def test_validate_full_doc_optional_patient_id_none():
    doc = _make_full_doc(patient_id=None)
    parsed = validate_final_report_dict(doc)
    assert parsed.patient_id is None


def test_validate_full_doc_optional_prompts_dir_none():
    doc = _make_full_doc(prompts_dir=None)
    parsed = validate_final_report_dict(doc)
    assert parsed.prompts_dir is None


def test_validate_full_doc_standard_mode():
    parsed = validate_final_report_dict(_make_full_doc(mode="standard"))
    assert parsed.mode == "standard"