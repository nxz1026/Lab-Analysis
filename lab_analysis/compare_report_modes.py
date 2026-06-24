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
import io
import json
import re
from pathlib import Path
from typing import Any

from lab_analysis.report_schema import REPORT_SECTIONS

from . import _log

logger = _log.get_logger(__name__)

# 章节后缀（对应 REPORT_SECTIONS 索引位）
_REPORT_SECTIONS_SUFFIXES = [
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

# 关键医疗实体列表（用于实体级对比）
_KEY_ENTITIES = [
    "hs-CRP",
    "CRP",
    "WBC",
    "NEUT#",
    "MONO%",
    "RDW-SD",
    "RDW-CV",
    "PCT",
    "PLT",
    "急性期",
    "缓解期",
    "过渡期",
    "炎症",
    "慢性胰腺炎",
    "胰腺",
    "感染",
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
    heading_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
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
    section_diffs: list[dict[str, Any]] = []
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
        longer = (
            std_mode_name
            if std_len > dspy_len
            else dspy_mode_name
            if dspy_len > std_len
            else "持平"
        )
        section_diffs.append(
            {
                "section": field,
                "header": header_cn,
                f"{std_mode_name}_length": std_len,
                f"{dspy_mode_name}_length": dspy_len,
                "overlap_rate": round(overlap, 4),
                "longer": longer,
                f"{std_mode_name}_entities": std_entities,
                f"{dspy_mode_name}_entities": dspy_entities,
            }
        )

    # 总体统计 (key 是动态 {std_mode_name}_length / {dspy_mode_name}_length)
    std_len_key = f"{std_mode_name}_length"
    dspy_len_key = f"{dspy_mode_name}_length"
    std_total_len = sum(int(s.get(std_len_key, 0)) for s in section_diffs)
    dspy_total_len = sum(int(s.get(dspy_len_key, 0)) for s in section_diffs)
    avg_overlap = (
        sum(float(s["overlap_rate"]) for s in section_diffs) / len(section_diffs)
        if section_diffs
        else 0
    )

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


def render_comparison_chart(
    result: dict,
    *,
    title: str = "Standard vs DSPy Report Comparison",
    figsize: tuple[float, float] = (11, 6),
) -> bytes:
    """生成双模式拼接对比图 (2 子图): 上=长度对比, 下=overlap rate."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import warnings

        warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
        warnings.filterwarnings("ignore", message=".*missing from font.*")
        from matplotlib.figure import Figure
    except ImportError:
        logger.warning("matplotlib not available, skipping chart rendering")
        return b""

    diffs = result.get("section_diffs", [])
    if not diffs:
        raise ValueError("result.section_diffs is empty")

    std_mode = result.get("std_mode", "Standard")
    dspy_mode = result.get("dspy_mode", "DSPy")

    headers = [d["header"][:10] for d in diffs]
    std_lens = [int(d.get(f"{std_mode}_length", 0)) for d in diffs]
    dspy_lens = [int(d.get(f"{dspy_mode}_length", 0)) for d in diffs]
    overlaps = [float(d.get("overlap_rate", 0.0)) for d in diffs]

    fig = Figure(figsize=figsize, dpi=100)

    # 上: Std vs DSPy 长度对比 (grouped horizontal bar)
    ax1 = fig.add_subplot(211)
    y_pos = list(range(len(headers)))
    ax1.barh(
        [y - 0.2 for y in y_pos], std_lens, height=0.4, label=std_mode, color="#1f77b4", alpha=0.85
    )
    ax1.barh(
        [y + 0.2 for y in y_pos],
        dspy_lens,
        height=0.4,
        label=dspy_mode,
        color="#ff7f0e",
        alpha=0.85,
    )
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(headers, fontsize=8)
    ax1.invert_yaxis()
    ax1.set_xlabel("Section Length (chars)")
    ax1.set_title("Length per Section", fontsize=10, pad=6)
    ax1.legend(loc="lower right", fontsize=8)
    ax1.grid(axis="x", alpha=0.3)

    max_len = max(std_lens + dspy_lens) if (std_lens or dspy_lens) else 1
    for i, (s, d) in enumerate(zip(std_lens, dspy_lens, strict=False)):
        ax1.text(s + max_len * 0.01, i - 0.2, str(s), va="center", fontsize=7, color="#1f77b4")
        ax1.text(d + max_len * 0.01, i + 0.2, str(d), va="center", fontsize=7, color="#ff7f0e")

    # 下: Overlap rate
    ax2 = fig.add_subplot(212)
    colors = ["#2ca02c" if o >= 0.7 else "#ff7f0e" if o >= 0.4 else "#d62728" for o in overlaps]
    bars = ax2.bar(headers, overlaps, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    ax2.axhline(
        0.7, color="green", linestyle="--", linewidth=1, alpha=0.6, label="overlap >= 0.7 (good)"
    )
    ax2.axhline(
        0.4, color="orange", linestyle="--", linewidth=1, alpha=0.6, label="overlap >= 0.4 (warn)"
    )
    ax2.set_ylim(0, 1.05)
    ax2.set_ylabel("Content Overlap Rate")
    ax2.set_title(
        f"Overlap Rate per Section (avg={result.get('avg_overlap_rate', 0):.1%})",
        fontsize=10,
        pad=6,
    )
    ax2.tick_params(axis="x", labelsize=7, rotation=30)
    ax2.legend(loc="upper right", fontsize=8)
    ax2.grid(axis="y", alpha=0.3)
    for bar, o in zip(bars, overlaps, strict=False):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{o:.1%}",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.suptitle(title, fontsize=12, fontweight="bold", y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
    return buf.getvalue()


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
            f"| {d['header'][:20]}... | {d[f"{result['std_mode']}_length"]} | "
            f"{d[f"{result['dspy_mode']}_length"]} | {overlap} | {d['longer']} |"
        )

    lines.append("\n## 实体提及对比\n")
    std_mode = result.get("std_mode", "Standard")
    dspy_mode = result.get("dspy_mode", "DSPy")
    for d in result["section_diffs"]:
        std_ents = d.get(f"{std_mode}_entities", {})
        dspy_ents = d.get(f"{dspy_mode}_entities", {})
        if std_ents or dspy_ents:
            lines.append(f"### {d['header']}\n")
            all_entities = sorted(set(list(std_ents.keys()) + list(dspy_ents.keys())))
            lines.append(f"| 实体 | {std_mode} | {dspy_mode} |")
            lines.append(f"|------|{'-' * len(std_mode)}|{'-' * len(dspy_mode)}|")
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
    parser.add_argument("--out-png", default=None, help="双模式拼接对比图 PNG 输出路径")
    args = parser.parse_args()

    result = compare_reports_from_files(args.std_md, args.dspy_json)

    md_report = format_comparison_md(result)
    logger.info(md_report)

    if args.out_json:
        Path(args.out_json).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"\n[OK] JSON 已保存: {args.out_json}")
    if args.out_md:
        Path(args.out_md).write_text(md_report, encoding="utf-8")
        logger.info(f"[OK] MD 已保存: {args.out_md}")
    if args.out_png:
        png_bytes = render_comparison_chart(result)
        Path(args.out_png).write_bytes(png_bytes)
        logger.info(f"[OK] PNG 已保存: {args.out_png} ({len(png_bytes)}B)")
