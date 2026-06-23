"""final_report JSON schema 的 Pydantic 强校验模型。

在 gen_final_report_dspy.py / dspy_modules/final_report_generator.py
写盘前对 sections 字段做完整校验, 把幻觉/空字段问题暴露在落地之前。

校验规则:
    - 9 个 section 全部存在
    - 每个 section 内容长度 >= 10 (避免 LLM 幻觉输出空 / 截断)
    - confidence 0.0 ~ 1.0
    - mode ∈ {"standard", "dspy"}
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

_SECTION_SUFFIXES: list[str] = [
    "basic_info",
    "lab_analysis",
    "mri_analysis",
    "multidisciplinary",
    "diagnosis",
    "consistency",
    "action_plan",
    "followup",
    "prognosis",
]
MIN_SECTION_LENGTH = 10


class SectionBlock(BaseModel):
    """单个 section 的强校验。"""

    name: str
    content: str

    @field_validator("name")
    @classmethod
    def _name_must_be_known(cls, v: str) -> str:
        if v not in _SECTION_SUFFIXES:
            raise ValueError(f"未知 section name={v!r}, 必须是 {_SECTION_SUFFIXES} 之一")
        return v

    @field_validator("content")
    @classmethod
    def _content_min_length(cls, v: str) -> str:
        if v is None:
            raise ValueError("section content 不能为 None")
        if len(v.strip()) < MIN_SECTION_LENGTH:
            raise ValueError(
                f"section content 过短 ({len(v.strip())} 字符), 最少 {MIN_SECTION_LENGTH} 字符 (防止 LLM 幻觉 / 截断)"
            )
        return v


class FinalReportSections(BaseModel):
    """9 章节 + title 强校验。"""

    title: str = Field(..., min_length=1)
    basic_info: SectionBlock
    lab_analysis: SectionBlock
    mri_analysis: SectionBlock
    multidisciplinary: SectionBlock
    diagnosis: SectionBlock
    consistency: SectionBlock
    action_plan: SectionBlock
    followup: SectionBlock
    prognosis: SectionBlock

    @model_validator(mode="before")
    @classmethod
    def _coerce_str_sections(cls, data: Any) -> Any:
        """允许 sections 字段是 str (自动包装为 SectionBlock dict)。

        gen_final_report_dspy.py 写出的 sections 是 { key: str_content },
        这个 validator 在 Pydantic 严格校验前先转成嵌套 dict。
        """
        if not isinstance(data, dict):
            return data
        out: dict[str, Any] = dict(data)
        for k in _SECTION_SUFFIXES:
            v = out.get(k)
            if isinstance(v, str):
                out[k] = {"name": k, "content": v}
        return out


class FinalReportDocument(BaseModel):
    """最终报告 JSON 完整 schema。"""

    generated: str
    model: str
    mode: Literal["standard", "dspy"]
    patient_id: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    report_markdown: str = Field(..., min_length=100)
    sections: FinalReportSections
    prompts_dir: str | None = None

    @field_validator("report_markdown")
    @classmethod
    def _md_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("report_markdown 不能为空")
        return v

    @model_validator(mode="after")
    def _check_section_count(self) -> "FinalReportDocument":
        """确保 sections 包含全部 9 章节, 名称唯一。"""
        seen: set[str] = set()
        for f in self.sections.__dict__.values():
            if isinstance(f, SectionBlock):
                if f.name in seen:
                    raise ValueError(f"section name 重复: {f.name}")
                seen.add(f.name)
        missing = set(_SECTION_SUFFIXES) - seen
        if missing:
            raise ValueError(f"缺少 section: {sorted(missing)}")
        return self


def build_sections_from_dict(raw_sections: dict[str, str]) -> FinalReportSections:
    """从 gen_final_report_dspy 的 sections dict 构造并验证。

    Args:
        raw_sections: { "title": ..., "basic_info": ..., ... }
                       其中 section 值可以是 str (自动包装为 SectionBlock)。

    Raises:
        pydantic.ValidationError: 校验失败
    """
    data: dict[str, Any] = {}
    for k in _SECTION_SUFFIXES:
        v = raw_sections.get(k)
        if v is None:
            v = ""
        data[k] = {"name": k, "content": str(v)}
    data["title"] = raw_sections.get("title", "") or "(无标题)"
    return FinalReportSections(**data)


def validate_final_report_dict(doc: dict[str, Any]) -> FinalReportDocument:
    """对完整 final_report JSON 字典做强校验。

    Args:
        doc: 写盘前的完整 report dict。

    Returns:
        校验通过后的 Pydantic 模型实例 (含规范化数据)。

    Raises:
        pydantic.ValidationError: 校验失败。
    """
    return FinalReportDocument(**doc)


def try_validate_sections(sections: dict[str, str]) -> tuple[bool, list[str]]:
    """soft-validate: 返回 (ok, errors)。

    用于不希望 raise 阻塞流程的场景, 把错误收集到 warnings 列表。

    Args:
        sections: 同 build_sections_from_dict 的 raw_sections。

    Returns:
        (ok, errors) — ok=True 表示全部通过, errors 是错误列表。
    """
    try:
        build_sections_from_dict(sections)
        return (True, [])
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        errs: list[str] = []
        if hasattr(e, "errors"):
            for err in e.errors():
                loc = ".".join((str(x) for x in err.get("loc", ())))
                msg = err.get("msg", "")
                errs.append(f"{loc}: {msg}")
        else:
            errs.append(str(e))
        return (False, errs)
