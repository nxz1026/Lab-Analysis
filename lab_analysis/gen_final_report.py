"""生成最终综合临床报告 - 调用 DeepSeek API"""

import argparse
import json
import os
from pathlib import Path

from lab_analysis.llm_client import call_chat, load_api_key
from lab_analysis.report_schema import PROMPT_SECTION_TEMPLATES

from . import _log
from .utils import WORK_ROOT

logger = _log.get_logger(__name__)
_FINAL_REPORT_SYSTEM_PROMPT = (
    "你是一个无害的医学资料分析助手，基于提供的患者数据生成结构化临床报告。"
)


def _load_patient_info(lab_path: Path) -> dict:
    """从 lab_metrics.json 的第一份报告里读取患者信息。"""
    if lab_path.exists():
        try:
            d = json.loads(lab_path.read_text())
            reports = d.get("reports", [])
            if reports:
                report = reports[0]
                return {
                    "name": report.get("patient_name", "患者"),
                    "age_sex": report.get("age_sex", "未知"),
                    "exam_id": report.get("exam_id", "未知"),
                }
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            pass
    return {"name": "患者", "age_sex": "未知", "exam_id": "未知"}


def parse_args():
    parser = argparse.ArgumentParser(description="生成最终综合临床报告")
    parser.add_argument("--id-card", required=True, help="脱敏ID(由 pipeline 传入)")
    parser.add_argument(
        "--compare-mode", action="store_true", help="同时运行 Standard + DSPy 双模式并输出对比报告"
    )
    return parser.parse_args()


def assess_three_source_consistency(data_dir: Path) -> str:
    """评估三源一致性，生成质控段落。

    三源：
    1. 检验数据（lab_metrics.json）
    2. 影像印证（mri_report_check_results.json）
    3. 文献证据（literature_results.json + literature_interpretation.json）

    Returns:
        Markdown 格式质控段落
    """
    signals = []
    lab_path = data_dir / "02_analyzed" / "lab_metrics.json"
    lab_summary = "数据暂缺"
    if lab_path.exists():
        try:
            d = json.loads(lab_path.read_text(encoding="utf-8"))
            reports = d.get("reports", [])
            if reports:
                latest = reports[-1]
                hs_crp = latest.get("hs-CRP") or latest.get("hsCRP")
                if hs_crp is not None and isinstance(hs_crp, (int, float)):
                    flag = "↑" if hs_crp > 3 else ""
                    lab_summary = f"hs-CRP={hs_crp}{flag}"
                    if hs_crp > 10:
                        signals.append(
                            ("检验-hsCRP", "ACUTE", f"hs-CRP={hs_crp}↑↑，提示急性炎症/感染")
                        )
                    elif hs_crp > 3:
                        signals.append(
                            ("检验-hsCRP", "ELEVATED", f"hs-CRP={hs_crp}↑，提示炎症活跃")
                        )
                    else:
                        signals.append(("检验-hsCRP", "NORMAL", f"hs-CRP={hs_crp}，炎症处于缓解期"))
                else:
                    lab_summary = "hs-CRP数据异常"
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            lab_summary = "数据解析失败"
    mri_path = data_dir / "03_literature" / "mri_report_check_results.json"
    mri_summary = "影像印证暂缺"
    if mri_path.exists():
        try:
            mri = json.loads(mri_path.read_text(encoding="utf-8"))
            checks = mri.get("results", []) if isinstance(mri, dict) else []
            if checks:
                confirmed = sum((1 for c in checks if c.get("status") == "success"))
                suspicious = sum((1 for c in checks if c.get("status") == "partial"))
                mri_summary = f"共{len(checks)}项，成功{confirmed}项，存疑{suspicious}项"
                if confirmed > suspicious:
                    signals.append(
                        ("影像印证", "SUPPORT", f"{confirmed}项影像发现与报告一致，支持检验结论")
                    )
                elif suspicious > 0:
                    signals.append(("影像印证", "CONFLICT", f"{suspicious}项影像发现与报告存疑"))
                else:
                    signals.append(("影像印证", "NEUTRAL", "影像印证无显著异常"))
            else:
                mri_summary = "影像印证结果为空"
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            mri_summary = "影像数据解析失败"
    lit_results_path = data_dir / "03_literature" / "literature_results.json"
    lit_interp_path = data_dir / "03_literature" / "literature_interpretation.json"
    lit_summary = "文献证据暂缺"
    if lit_results_path.exists():
        try:
            lit = json.loads(lit_results_path.read_text(encoding="utf-8"))
            count = lit.get("total_unique_papers", 0)
            papers = lit.get("all_papers", [])
            year_range = ""
            if papers:
                years = [int(p["year"]) for p in papers if p.get("year", "").isdigit()]
                if years:
                    year_range = f"（{min(years)}-{max(years)}）"
            lit_summary = f"检索到{count}篇文献{year_range}"
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            lit_summary = "文献数据解析失败"
    if lit_interp_path.exists():
        try:
            interp = json.loads(lit_interp_path.read_text(encoding="utf-8"))
            resp_text = interp.get("response", "") or interp.get("text", "")
            if resp_text and len(resp_text) > 50:
                signals.append(("文献-循证解读", "SUPPORT", "文献检索+循证解读已完成，证据链完整"))
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            pass
    acute_count = sum((1 for _, s, _ in signals if s == "ACUTE"))
    conflict_count = sum((1 for _, s, _ in signals if s == "CONFLICT"))
    support_count = sum((1 for _, s, _ in signals if s in ("SUPPORT", "NORMAL")))
    if acute_count > 0:
        overall = "[URGENT] **结论一致性：检验/影像/文献三者指向急性炎症状态，建议尽快处理。**"
        detail = "患者处于急性炎症/感染状态，三源证据一致。"
    elif conflict_count > 0 and support_count > conflict_count:
        overall = "[WARN]  **结论一致性：检验/影像/文献存在部分矛盾，需结合临床综合判断。**"
        detail = "三源证据中部分矛盾，建议进一步检查或短期复查后再评估。"
    elif conflict_count > 0:
        overall = "[URGENT] **结论一致性：检验/影像/文献存在明显矛盾，报告可信度存疑。**"
        detail = "三源证据矛盾较多，建议复核原始数据后再发正式报告。"
    elif support_count >= 2:
        overall = "[OK]  **结论一致性：检验/影像/文献三者支持，无显著矛盾。**"
        detail = "三源证据相互印证，报告可信度高。"
    else:
        overall = "[WARN]  **结论一致性：证据不充分，无法完整评估一致性。**"
        detail = "部分源数据缺失，建议补充检查后再出报告。"
    status_icon = {
        "ACUTE": "[URGENT]",
        "ELEVATED": "[WARN]",
        "NORMAL": "[OK]",
        "SUPPORT": "[OK]",
        "CONFLICT": "[FAIL]",
        "NEUTRAL": "[WARN]",
        "UNKNOWN": "[WARN]",
    }.get
    lines = [
        "## 附：三源质控段落\n",
        "| 证据来源 | 内容摘要 |",
        "|---------|---------|",
        f"| 检验数据 | {lab_summary} |",
        f"| 影像印证 | {mri_summary} |",
        f"| 文献证据 | {lit_summary} |",
        "",
        overall,
        detail,
        "",
        "**信号详情**：",
    ]
    for label, status, desc in signals:
        lines.append(f"- {status_icon(status)} [{label}][{status}] {desc}")
    return "\n".join(lines)


def build_prompt(data_dir: Path, patient_id: str) -> str:
    """构建完整的 USER_PROMPT，包含三源数据和质控段落。"""
    lab_data = ""
    lab_path = data_dir / "02_analyzed" / "lab_metrics.json"
    if lab_path.exists():
        try:
            d = json.loads(lab_path.read_text(encoding="utf-8"))
            reports = d.get("reports", [])
            if reports:
                cols = [
                    "report_date",
                    "hs-CRP",
                    "CRP",
                    "WBC",
                    "NEUT#",
                    "MONO%",
                    "RDW-SD",
                    "PCT",
                    "PLT",
                ]
                rows = ["日期       hs-CRP  CRP     WBC     NEUT#   MONO%   RDW-SD  PCT     PLT"]
                for r in reports:
                    vals = []
                    for c in cols[1:]:
                        v = r.get(c) or r.get(c.replace("-", "")) or "—"
                        if isinstance(v, float):
                            v = f"{v:.2f}"
                        vals.append(str(v))
                    rows.append(f"{r.get('report_date', '??')}  " + "  ".join(vals))
                lab_data = "\n".join(rows)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            lab_data = "(检验数据解析失败)"
    lit_data = ""
    lit_path = data_dir / "03_literature" / "literature_results.json"
    if lit_path.exists():
        try:
            lit = json.loads(lit_path.read_text(encoding="utf-8"))
            papers = lit.get("all_papers", [])[:6]
            if papers:
                lit_lines = [
                    f"- {p.get('year', '?')} | {p.get('title', '')[:60]}... (PMID:{p.get('pmid')})"
                    for p in papers
                ]
                lit_data = "\n".join(lit_lines)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            lit_data = "(文献数据解析失败)"
    interp_data = ""
    interp_path = data_dir / "03_literature" / "literature_interpretation.json"
    if interp_path.exists():
        try:
            d = json.loads(interp_path.read_text(encoding="utf-8"))
            t = d.get("response", "") or d.get("text", "")
            if t:
                interp_data = t[:800] + "..." if len(t) > 800 else t
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            interp_data = "(循证解读解析失败)"
    mri_data = ""
    mri_path = data_dir / "03_literature" / "mri_report_check_results.json"
    if mri_path.exists():
        try:
            mri = json.loads(mri_path.read_text(encoding="utf-8"))
            checks = mri.get("results", []) if isinstance(mri, dict) else []
            if checks:
                mri_lines = [
                    f"- {c.get('seq_name', '')}: {c.get('analysis', [{}])[0].get('text', '')[:60]}"
                    for c in checks[:5]
                ]
                mri_data = "\n".join(mri_lines)
            else:
                mri_data = "(影像印证结果为空)"
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            mri_data = "(影像数据解析失败)"
    qc = assess_three_source_consistency(data_dir)
    import datetime as dt

    today = dt.date.today().strftime("%Y年%m月%d日")
    patient_info = _load_patient_info(lab_path)
    patient_name = patient_info["name"]
    patient_age_sex = patient_info["age_sex"]
    patient_exam_id = patient_info["exam_id"]
    prompt = f"""你是资深临床医学专家，请为患者{patient_name}（{patient_age_sex}，ID:{patient_exam_id}）生成最终综合临床诊断报告。\n\n【说明】以下数据来自 pipeline 各步骤汇总，请生成结构化报告。\n\n【请依次阅读以下数据文件，未找到的文件请注明"数据暂缺"】：\n1. 检验指标时序数据：{str(lab_path)}\n2. 统计分析结果：{str(data_dir / "02_analyzed" / "analysis_results.json")}\n3. 文献检索结果：{str(lit_path)}\n4. 循证医学解读：{str(interp_path)}\n5. MRI影像AI分析（如有）：{str(mri_path)}\n\n---\n\n### 【检验数据摘要】\n{(lab_data if lab_data else "(数据暂缺)")}\n\n### 【Top 文献列表】\n{(lit_data if lit_data else "(数据暂缺)")}\n\n### 【循证解读摘要】\n{(interp_data if interp_data else "(数据暂缺)")}\n\n### 【MRI影像印证摘要】\n{(mri_data if mri_data else "(影像数据暂缺)")}\n\n---\n\n{qc}\n\n---\n\n请生成【最终综合临床诊断报告】，结构如下：\n\n# 最终综合临床诊断报告\n**患者**：{patient_name} | {patient_age_sex} | 检查编号：{patient_exam_id}\n**报告日期**：{today}\n**数据来源**：MRI影像报告 + 检验数据 + 文献证据\n\n{PROMPT_SECTION_TEMPLATES}\n\n> 对于「六、结论一致性评估」，请将上方「三源质控段落」的核心结论原文引用或摘要写入本节。\n\n要求：专业清晰，中文输出；不生成具体药物处方或手术建议；各部分内容充实"""
    return prompt


def main():
    args = parse_args()
    patient_id = args.id_card
    import os

    raw_ts = os.environ.get("ANALYSIS_TS", "")
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts or patient_id
    data_dir = WORK_ROOT / "data" / patient_id / ts
    DEEPSEEK_API_KEY = load_api_key("DEEPSEEK_API_KEY", required=False)
    if not DEEPSEEK_API_KEY:
        logger.error("[FAIL] 未找到 DEEPSEEK_API_KEY")
        return
    reports_dir = data_dir / "04_reports"
    output_path = reports_dir / "final_integrated_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    required = [
        data_dir / "02_analyzed" / "lab_metrics.json",
        data_dir / "02_analyzed" / "analysis_results.json",
        data_dir / "03_literature" / "literature_results.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        logger.warning("[WARN]  以下前置文件不存在，将使用内置默认数据：")
        for p in missing:
            logger.info(f"   - {p}")
    logger.info(f"[{__import__('datetime').datetime.now().isoformat()}] 生成最终报告...")
    logger.info(f"  data_dir: {data_dir}")
    USER_PROMPT = build_prompt(data_dir, patient_id)
    content = call_chat(
        "deepseek",
        user_prompt=USER_PROMPT,
        system_prompt=_FINAL_REPORT_SYSTEM_PROMPT,
        max_tokens=5000,
        temperature=0.3,
        timeout=180,
        api_key=DEEPSEEK_API_KEY,
    )
    logger.info(f"Content length: {len(content)}")
    if content:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"\n报告已保存: {output_path}")
        if args.compare_mode:
            logger.info("\n[COMPARE] 双模式对比模式 — 同时运行 DSPy 版本...")
            try:
                import argparse as _argparse

                from lab_analysis.compare_report_modes import compare_reports, format_comparison_md
                from lab_analysis.gen_final_report_dspy import run_dspy_mode as _dspy_run

                _dspy_args = _argparse.Namespace(id_card=patient_id, use_dspy=True)
                dspy_result = _dspy_run(_dspy_args)
                dspy_sections = dspy_result.get("sections", {})
                dspy_confidence = dspy_result.get("confidence")
                comp = compare_reports(content, dspy_sections, dspy_confidence)
                comp_md = format_comparison_md(comp)
                comp_md_path = reports_dir / "mode_comparison_report.md"
                comp_md_path.write_text(comp_md, encoding="utf-8")
                logger.info(f"[COMPARE] 对比报告已保存: {comp_md_path}")
                comp_json_path = reports_dir / "mode_comparison.json"
                import json as _json

                comp_json_path.write_text(
                    _json.dumps(comp, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                logger.info(f"[COMPARE] 对比数据已保存: {comp_json_path}")
            except ImportError as _e:
                logger.info(f"[COMPARE] 跳过对比（DSPy 模块未就绪: {_e})")
            except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as _e:
                logger.info(f"[COMPARE] 对比出错（非致命）: {_e}")
    else:
        logger.info("[EMPTY CONTENT]")


if __name__ == "__main__":
    main()
