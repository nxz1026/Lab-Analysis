"""report_schema.py — 综合临床报告 9 章节定义与 MD 模板

让 gen_final_report.py（标准版）和 dspy_modules/final_report_generator.py（DSPy 版）
共享同一份章节结构定义，避免 9 章节的 header/description 在两处重复维护。
"""

# 章节定义：(字段名后缀, 章节中文标题, DSPy OutputField 描述)
REPORT_SECTIONS = [
    ("basic_info",          "一、患者基本信息与就诊背景",
     "患者基本信息与就诊背景"),
    ("lab_analysis",        "二、检验数据与炎症状态综合分析",
     "检验数据与炎症状态综合分析"),
    ("mri_analysis",        "三、MRI影像学综合分析",
     "MRI影像学综合分析"),
    ("multidisciplinary",   "四、多学科联合诊断意见",
     "多学科联合诊断意见"),
    ("diagnosis",           "五、核心诊断结论与鉴别诊断",
     "核心诊断结论与鉴别诊断"),
    ("consistency",         "六、结论一致性评估",
     "结论一致性评估"),
    ("action_plan",         "七、行动计划（紧急[URGENT] / 重要[IMPORTANT] / 常规[ROUTINE]）",
     "行动计划（紧急/重要/常规）"),
    ("followup",            "八、随访与监测计划",
     "随访与监测计划"),
    ("prognosis",           "九、预后评估",
     "预后评估"),
]

# 标准版 prompt 中的章节模板（供 gen_final_report.py 拼接 USER_PROMPT 用）
PROMPT_SECTION_TEMPLATES = "\n".join(
    f"## {header}\n" for _, header, _ in REPORT_SECTIONS
)

# Markdown 报告组装模板（供两版本共用，用 str.format 填充）
REPORT_MD_TEMPLATE = """# {report_title}
**患者**：{patient_name} | {patient_age_sex} | 检查编号：{exam_id}
**报告日期**：{report_date}
**数据来源**：{data_sources}
**生成模式**：{mode}
**可信度评分**：{confidence:.2f}

---

## 一、患者基本信息与就诊背景

{section_1_basic_info}

## 二、检验数据与炎症状态综合分析

{section_2_lab_analysis}

## 三、MRI影像学综合分析

{section_3_mri_analysis}

## 四、多学科联合诊断意见

{section_4_multidisciplinary}

## 五、核心诊断结论与鉴别诊断

{section_5_diagnosis}

## 六、结论一致性评估

{section_6_consistency}

## 七、行动计划（紧急[URGENT] / 重要[IMPORTANT] / 常规[ROUTINE]）

{section_7_action_plan}

## 八、随访与监测计划

{section_8_followup}

## 九、预后评估

{section_9_prognosis}
"""


def build_section_field_name(suffix: str) -> str:
    """根据章节后缀生成 DSPy/标准字段名。
    >>> build_section_field_name("basic_info")
    'section_1_basic_info'
    """
    idx = next((i + 1 for i, (s, _, _) in enumerate(REPORT_SECTIONS) if s == suffix), None)
    if idx is None:
        raise ValueError(f"未知章节后缀: {suffix!r}")
    return f"section_{idx}_{suffix}"
