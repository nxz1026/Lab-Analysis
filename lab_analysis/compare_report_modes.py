"""compare_report_modes.py — 标准模式 vs DSPy 模式报告对比

将同一份数据的 standard API 报告和 DSPy 优化报告按 9 章节对齐，
逐段对比字数、内容重叠率、关键实体提及差异，输出对比报告。

用法:
    from lab_analysis.compare_report_modes import compare_reports

    result = compare_reports(std_md, dspy_result_dict)
    # result 可保存为 JSON / MD
"""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path
from typing import Any

from lab_analysis.report_schema import REPORT_SECTIONS

# 关键医疗实体列表（用于实体级对比）
_KEY_ENTITIES = [
    "hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV",
    "PCT", "PLT", "急性期", "缓解期", "过渡期", "炎症",
    "慢性胰腺炎", "胰腺", "感染",
]


def _parse_std_sections(std_md: str) -> list[tuple[str, str]]:
    """将标准模式的 Markdown 报告按 `## ` 标题拆分为 9 章节。

    Returns:
        ``[(section_name, content), ...]``
        section_name 如 ``section_2_lab_analysis``。
        未找到匹配的章节返回空内容。
    """
    sections: list[tuple[str, str]] = []
    # 找所有 `## ` 标题
    heading_pattern = re.compile(r'^##\s+(.+)$', re.MULTILINE)
    matches = list(heading_pattern.finditer(std_md))

    for idx, (_, header_cn, _) in enumerate(REPORT_SECTIONS):
        field_name = f"section_{idx + 1}_{_REPORT_SECTIONS_SUFFIXES[idx]}"
        # 找到匹配的标题
        content = ""
        for mi, m in enumerate(matches):
            title_text = m.group(1).strip()
            # 匹配中文标题（部分匹配即可）
            if header_cn[:4] in title_text or title_text[:4] in header_cn:
                # 内容从本标题后到下一个标题前
                start = m.end()
                end = matches[mi + 1].start() if mi + 1 < len(matches) else len(std_md)
                content = std_md[start:end].strip()
                break
        sections.append((field_name, content))
    return sections


# 章节后缀（对应 REPORT_SECTIONS 索引位）
_REPORT_SECTIONS_SUFFIXES = [
    "basic_info", "lab_analysis", "mri_analysis", "multidisciplinary",
    "diagnosis", "consistency", "action_plan", "followup", "prognosis",
]


def _calc_overlap_rate(a: str, b: str) -> float:
    """用 difflib SequenceMatcher 计算两段文本的内容重叠比例。"""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _count_entities(text: str, entities: list[str]) -> dict[str, int]:
    """统计文本中提到的关键实体频次。"""
    text_lower = text.lower()
    counts: dict[str, int] = {}
    for e in entities:
        count = text_lower.count(e.lower())
        if count > 0:
            counts[e] = count
    return counts


def compare_reports(
    std_md: str,
    dspy_sections: dict[str, str],
    dspy_confidence: float | None = None,
    std_mode_name: str = "Standard",
    dspy_mode_name: str = "DSPy",
) -> dict[str, Any]:
    """对比标准模式与 DSPy 模式的报告输出。

    Args:
        std_md: 标准模式生成的完整 Markdown 报告文本。
        dspy_sections: DSPy 模块返回的 ``result.sections`` 字典，
            键为 ``{title, basic_info, lab_analysis, ...}``。
        dspy_confidence: DSPy 报告的置信度（无则 None）。
        std_mode_name: 标准模式显示名称。
        dspy_mode_name: DSPy 模式显示名称。

    Returns:
        对比结果 dict，可序列化为 JSON 或渲染为 MD。
    """
    # 解析标准模式的 9 章节
    std_sections = dict(_parse_std_sections(std_md))

    # 对齐 DSPy sections（DSPy 的 key 是 short name，如 "basic_info"）
    dspy_sections_aligned: dict[str, str] = {}
    for idx, suffix in enumerate(_REPORT_SECTIONS_SUFFIXES):
        field = f"section_{idx + 1}_{suffix}"
        dspy_value = dspy_sections.get(suffix, "") or dspy_sections.get(field, "")
        dspy_sections_aligned[field] = dspy_value

    # 逐段对比
    section_diffs = []
    for idx, (_, header_cn, _) in enumerate(REPORT_SECTIONS):
        field = f"section_{idx + 1}_{_REPORT_SECTIONS_SUFFIXES[idx]}"
        std_content = std_sections.get(field, "")
        dspy_content = dspy_sections_aligned.get(field, "")
        std_len = len(std_content)
        dspy_len = len(dspy_content)
        overlap = _calc_overlap_rate(std_content, dspy_content)
        std_entities = _count_entities(std_content, _KEY_ENTITIES)
        dspy_entities = _count_entities(dspy_content, _KEY_ENTITIES)
        # 谁更长
        longer = std_mode_name if std_len > dspy_len else dspy_mode_name if dspy_len > std_len else "持平"
        section_diffs.append({
            "section": field,
            "header": header_cn,
            f"{std_mode_name}_length": std_len,
            f"{dspy_mode_name}_length": dspy_len,
            "overlap_rate": round(overlap, 4),
            "longer": longer,
            f"{std_mode_name}_entities": std_entities,
            f"{dspy_mode_name}_entities": dspy_entities,
        })

    # 总体统计
    std_total_len = sum(s["Standard_length"] for s in section_diffs) if std_mode_name == "Standard" else 0
    dspy_total_len = sum(s[std_mode_name == "DSPy" or "DSPy_length"] for s in section_diffs)
    std_total_len = sum(s.get("Standard_length", 0) for s in section_diffs)
    dspy_total_len = sum(s.get("DSPy_length", 0) for s in section_diffs)
    avg_overlap = sum(s["overlap_rate"] for s in section_diffs) / len(section_diffs) if section_diffs else 0

    result: dict[str, Any] = {
        "std_mode": std_mode_name,
        "dspy_mode": dspy_mode_name,
        "std_total_length": std_total_len,
        "dspy_total_length": dspy_total_len,
        "avg_overlap_rate": round(avg_overlap, 4),
        "dspy_confidence": dspy_confidence,
        "n_sections": len(section_diffs),
        "section_diffs": section_diffs,
    }
    return result


def compare_reports_from_files(
    std_md_path: str | Path,
    dspy_json_path: str | Path,
) -> dict[str, Any]:
    """从已保存的文件直接加载数据并对比。

    Args:
        std_md_path: 标准模式报告 Markdown 路径。
        dspy_json_path: DSPy 模式输出的 JSON 路径（含 ``report_markdown`` 和 ``sections``）。

    Returns:
        同 ``compare_reports()``。
    """
    std_md = Path(std_md_path).read_text(encoding="utf-8")
    dspy_data = json.loads(Path(dspy_json_path).read_text(encoding="utf-8"))

    dspy_sections = dspy_data.get("sections", {})
    dspy_confidence = dspy_data.get("confidence")

    return compare_reports(std_md, dspy_sections, dspy_confidence)


def format_comparison_md(result: dict) -> str:
    """将对比结果格式化为可读的 Markdown 报告。"""
    lines = [
        "# 报告模式对比分析\n",
        f"**Standard 模式**: {result['std_mode']}",
        f"**DSPy 模式**: {result['dspy_mode']}",
        f"**DSPy 置信度**: {result['dspy_confidence'] or 'N/A'}",
        "",
        "## 总体统计\n",
        "| 指标 | Standard | DSPy |",
        "|------|----------|------|",
        f"| 总字符数 | {result['std_total_length']} | {result['dspy_total_length']} |",
        f"| 章节数 | {result['n_sections']} | {result['n_sections']} |",
        f"| 平均内容重叠率 | — | {result['avg_overlap_rate']:.2%} |",
        "",
        "## 逐段对比\n",
        "| 章节 | Standard长度 | DSPy长度 | 重叠率 | 较长方 |",
        "|------|------------|---------|-------|-------|",
    ]
    for d in result["section_diffs"]:
        overlap = f"{d['overlap_rate']:.1%}"
        lines.append(
            f"| {d['header'][:20]}... | {d['Standard_length']} | "
            f"{d['DSPy_length']} | {overlap} | {d['longer']} |"
        )

    lines.append("\n## 实体提及对比\n")
    for d in result["section_diffs"]:
        std_ents = d.get("Standard_entities", {})
        dspy_ents = d.get("DSPy_entities", {})
        if std_ents or dspy_ents:
            lines.append(f"### {d['header']}\n")
            all_entities = sorted(set(list(std_ents.keys()) + list(dspy_ents.keys())))
            lines.append("| 实体 | Standard | DSPy |")
            lines.append("|------|----------|------|")
            for ent in all_entities:
                lines.append(f"| {ent} | {std_ents.get(ent, 0)} | {dspy_ents.get(ent, 0)} |")
            lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="对比 Standard / DSPy 报告模式")
    parser.add_argument("--std-md", required=True, help="Standard 模式报告的 .md 路径")
    parser.add_argument("--dspy-json", required=True, help="DSPy 模式报告的 .json 路径")
    parser.add_argument("--out-json", default=None, help="对比结果 JSON 输出路径")
    parser.add_argument("--out-md", default=None, help="对比报告 MD 输出路径")
    args = parser.parse_args()

    result = compare_reports_from_files(args.std_md, args.dspy_json)

    md_report = format_comparison_md(result)
    print(md_report)

    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n[OK] JSON 已保存: {args.out_json}")
    if args.out_md:
        Path(args.out_md).write_text(md_report, encoding="utf-8")
        print(f"[OK] MD 已保存: {args.out_md}")
