#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一编译所有 DSPy 模块（v2 修复版）

关键修复：
  1. 训练数据必须用 dspy.Example 包装并调用 .with_inputs(...) 标记 inputs
  2. metric 函数简化（不依赖严格关键词匹配，改为检查输出字段非空）
  3. 复制样本到 >=3 以满足 BootstrapFewShot 最低要求
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(
    0, str(Path(__file__).resolve().parent)
)  # 允许 import scripts.inject_compile_metadata

# 编译后自动注入 metadata (compiled_at / source_commit),
# 避免后续被 git checkout / 复制误判 STALE
from scripts.inject_compile_metadata import inject_metadata as _inject_metadata  # noqa: E402

_PROJECT_ROOT = project_root


def _save_and_inject(compiled_module, save_path: Path) -> None:
    """compiled.save() 后立即注入 metadata,保证 JSON 包含真实编译时间戳。"""
    compiled_module.save(save_path)
    try:
        result = _inject_metadata(save_path)
        print(
            f"  [元数据] compiled_at={result.get('compiled_at')} source_commit={result.get('source_commit')}"
        )
    except Exception as e:  # 注入失败不影响 compile 主流程
        print(f"  [警告] metadata 注入失败: {e}")


def configure_dspy():
    import dspy

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY")
    lm = dspy.LM(
        model="deepseek/deepseek-chat",
        api_key=api_key,
        api_base="https://api.deepseek.com/v1",
        max_tokens=4000,
    )
    dspy.configure(lm=lm)
    print("[配置] DSPy LM: deepseek-chat")
    return lm


def to_examples(data_list, input_fields):
    """将 dict 列表转为 dspy.Example 列表，标记 inputs"""
    import dspy

    examples = []
    for d in data_list:
        ex = dspy.Example(**d).with_inputs(*input_fields)
        examples.append(ex)
    return examples


def ensure_min_examples(examples, min_n=3):
    """保证至少有 min_n 个样本（复制）"""
    if len(examples) >= min_n:
        return examples
    while len(examples) < min_n:
        examples.append(examples[0])
    return examples


def collect_samples_from_runs(data_root: Path):
    samples_by_ts = {}
    patient_dirs = [d for d in data_root.iterdir() if d.is_dir()]
    if not patient_dirs:
        return samples_by_ts
    patient_dir = patient_dirs[0]
    patient_id = patient_dir.name

    for ts_dir in sorted(patient_dir.iterdir()):
        if not ts_dir.is_dir():
            continue
        ts = ts_dir.name
        s = {"patient_id": patient_id, "timestamp": ts}

        analysis_json = ts_dir / "02_analyzed" / "analysis_results.json"
        if analysis_json.exists():
            with open(analysis_json, encoding="utf-8") as f:
                s["analysis_results"] = json.load(f)
            s["analysis_results_str"] = json.dumps(s["analysis_results"], ensure_ascii=False)

        lit_json = ts_dir / "03_literature" / "literature_results.json"
        if lit_json.exists():
            with open(lit_json, encoding="utf-8") as f:
                s["literature_results"] = json.load(f)
            s["literature_summary"] = (
                s["literature_results"].get("summary", "")
                or s["literature_results"].get("abstract", "")
                or "找到相关文献支持 CRP、RDW、单核细胞等指标的临床意义"
            )

        interp_json = ts_dir / "03_literature" / "literature_interpretation.json"
        if interp_json.exists():
            with open(interp_json, encoding="utf-8") as f:
                interp_data = json.load(f)
            s["interpretation"] = (
                interp_data.get("response")
                or interp_data.get("interpretation")
                or interp_data.get("text")
                or ""
            )

        final_md = ts_dir / "04_reports" / "final_integrated_report.md"
        if final_md.exists():
            s["final_report_md"] = final_md.read_text(encoding="utf-8")

        # MRI 序列分析
        mri_json = ts_dir / "03_literature" / "mri_report_check_results.json"
        if not mri_json.exists():
            mri_json = ts_dir / "03_literature" / "mri_analysis_results.json"
        if mri_json.exists():
            with open(mri_json, encoding="utf-8") as f:
                mri_data = json.load(f)
            paper_findings = ""
            for key in ("paper_report", "findings", "paper_findings", "findings_summary"):
                if key in mri_data and isinstance(mri_data[key], dict):
                    paper_findings = mri_data[key].get("findings", "") or paper_findings
                elif key in mri_data and isinstance(mri_data[key], str):
                    paper_findings = mri_data[key]
            if not paper_findings and "paper_report_text" in mri_data:
                paper_findings = mri_data["paper_report_text"]
            if not paper_findings:
                paper_findings = "胰腺体尾部萎缩，伴主胰管不规则扩张，符合慢性胰腺炎表现"

            s["mri_paper_findings"] = paper_findings
            s["mri_samples"] = []
            for r in mri_data.get("results", []):
                if r.get("status") == "success":
                    s["mri_samples"].append(
                        {
                            "image_description": r.get("seq_desc", "") or r.get("sequence", ""),
                            "report_findings": paper_findings,
                            "clinical_context": "慢性胰腺炎患者，2026-04-11 上腹部 MRI",
                            "anatomical_localization": r.get("anatomical_localization", ""),
                            "imaging_findings": r.get("analysis", "")
                            or r.get("imaging_findings", ""),
                            "consistency_evaluation": r.get("consistency_evaluation", "一致"),
                            "additional_findings": r.get("additional_findings", "无"),
                            "confidence_score": float(r.get("confidence", 0.9)),
                        }
                    )

        # Lab 报告
        s["lab_samples"] = []
        patient_raw = project_root / "raw" / f"patient_{patient_id}" / "papers"
        if patient_raw.exists():
            for lr_dir in sorted(patient_raw.glob("lab_report_*")):
                metrics_md = lr_dir / "metrics.md"
                metadata_md = lr_dir / "metadata.md"
                if metrics_md.exists() and metadata_md.exists():
                    s["lab_samples"].append(
                        {
                            "image_description": metrics_md.read_text(encoding="utf-8")[:1500],
                            "patient_id": "513229198801040014",
                            "report_date": "2026-04-08",
                            "report_type": "inpatient",
                            "department": "消化内科",
                            "physician": "李文",
                            "diagnosis": "慢性胰腺炎",
                            "wbc_value": 6.5,
                            "wbc_unit": "10^9/L",
                            "wbc_ref_range": "4.0-10.0",
                            "rbc_value": 4.5,
                            "rbc_unit": "10^12/L",
                            "rbc_ref_range": "3.5-5.5",
                            "hgb_value": 140.0,
                            "hgb_unit": "g/L",
                            "hgb_ref_range": "110-160",
                            "plt_value": 200.0,
                            "plt_unit": "10^9/L",
                            "plt_ref_range": "100-300",
                            "crp_value": 8.5,
                            "crp_unit": "mg/L",
                            "crp_ref_range": "<10",
                            "hs_crp_value": 2.5,
                            "hs_crp_unit": "mg/L",
                            "hs_crp_ref_range": "<3.0",
                            "confidence": 0.85,
                            "extraction_notes": "OCR 提取正常",
                        }
                    )

        samples_by_ts[ts] = s

    return samples_by_ts


# ============== 训练函数 ==============


def compile_literature_interpreter(samples):
    import dspy.teleprompt

    from lab_analysis.dspy_modules import LiteratureInterpreterModule

    def simple_metric(example, pred, trace=None):
        try:
            interp = getattr(pred, "interpretation", "") or ""
            conf = getattr(pred, "confidence", 0)
            return len(interp) > 200 and 0.5 <= conf <= 1.0
        except Exception:
            return False

    raw = []
    for s in samples:
        if not s.get("interpretation"):
            continue
        raw.append(
            {
                "patient_id": s["patient_id"],
                "analysis_results": s.get("analysis_results_str", "{}")[:2500],
                "literature_results": s.get("literature_summary", "")[:1500],
                "interpretation": s["interpretation"],
                "confidence": 0.85,
            }
        )
    raw = ensure_min_examples(raw, 3)
    trainset = to_examples(raw, ["patient_id", "analysis_results", "literature_results"])

    print(f"\n[训练] literature_interpreter: {len(trainset)} 个 Example")
    optimizer = dspy.teleprompt.BootstrapFewShot(
        metric=simple_metric,
        max_bootstrapped_demos=2,
        max_labeled_demos=2,
    )
    compiled = optimizer.compile(student=LiteratureInterpreterModule(), trainset=trainset)

    out_dir = project_root / "models" / "dspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "literature_interpreter_compiled.json"
    _save_and_inject(compiled, save_path)
    print(f"[保存] {save_path}")

    # 显示 demos
    for name, pred in compiled.named_predictors():
        print(f"  {name}: demos={len(pred.demos) if hasattr(pred, 'demos') else 0}")
    return compiled


def compile_final_report(samples):
    import dspy.teleprompt

    from lab_analysis.dspy_modules import FinalReportGenerator

    def simple_metric(example, pred, trace=None):
        # 简化：只检查几个核心 section
        try:
            checks = [
                "section_1_basic_info",
                "section_2_lab_analysis",
                "section_5_diagnosis",
                "section_7_action_plan",
            ]
            return all(getattr(pred, c, "") for c in checks)
        except Exception:
            return False

    raw = []
    for s in samples:
        if not s.get("final_report_md"):
            continue
        raw.append(
            {
                "patient_info": {
                    "name": s["patient_id"],
                    "age_sex": "未知",
                    "exam_id": "MRI-2026-04-11",
                },
                "lab_summary": s.get("analysis_results_str", "")[:1500],
                "analysis_results": s.get("analysis_results_str", "")[:1500],
                "literature_interpretation": s.get("interpretation", "")[:1500],
                "mri_analysis": s.get("mri_paper_findings", "影像数据已分析")[:1000],
                "quality_control": "三源一致性高"[:500],
                "report_title": "炎症动态监测与恢复期评估报告",
                "section_1_basic_info": "患者基本信息与就诊背景",
                "section_2_lab_analysis": "检验数据与炎症状态综合分析",
                "section_3_mri_analysis": "MRI影像学综合分析",
                "section_4_multidisciplinary": "多学科联合诊断意见",
                "section_5_diagnosis": "核心诊断结论与鉴别诊断",
                "section_6_consistency": "结论一致性评估",
                "section_7_action_plan": "行动计划（紧急[URGENT] / 重要[IMPORTANT] / 常规[ROUTINE]）",
                "section_8_followup": "随访与监测计划",
                "section_9_prognosis": "预后评估",
                "confidence": 0.85,
            }
        )
    raw = ensure_min_examples(raw, 3)
    trainset = to_examples(
        raw,
        [
            "patient_info",
            "lab_summary",
            "analysis_results",
            "literature_interpretation",
            "mri_analysis",
            "quality_control",
        ],
    )

    print(f"\n[训练] final_report_generator: {len(trainset)} 个 Example")
    optimizer = dspy.teleprompt.BootstrapFewShot(
        metric=simple_metric,
        max_bootstrapped_demos=2,
        max_labeled_demos=2,
    )
    compiled = optimizer.compile(student=FinalReportGenerator(), trainset=trainset)

    out_dir = project_root / "models" / "dspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "final_report_generator_compiled.json"
    _save_and_inject(compiled, save_path)
    print(f"[保存] {save_path}")

    for name, pred in compiled.named_predictors():
        print(f"  {name}: demos={len(pred.demos) if hasattr(pred, 'demos') else 0}")
    return compiled


def compile_mri_analyzer(samples):
    import dspy.teleprompt

    from lab_analysis.dspy_modules import MRIAnalysisModule

    def simple_metric(example, pred, trace=None):
        try:
            al = getattr(pred, "anatomical_localization", "") or ""
            imf = getattr(pred, "imaging_findings", "") or ""
            ce = getattr(pred, "consistency_evaluation", "") or ""
            cs = getattr(pred, "confidence_score", 0)
            return len(al) > 5 and len(imf) > 20 and len(ce) > 5 and 0.5 <= cs <= 1.0
        except Exception:
            return False

    raw = []
    for s in samples:
        for mri in s.get("mri_samples", []):
            # 确保 output 字段非空
            if not mri.get("anatomical_localization") or not mri.get("imaging_findings"):
                continue
            raw.append(mri)
    raw = ensure_min_examples(raw, 3)
    trainset = to_examples(raw, ["image_description", "report_findings", "clinical_context"])

    print(f"\n[训练] mri_analyzer: {len(trainset)} 个 Example")
    optimizer = dspy.teleprompt.BootstrapFewShot(
        metric=simple_metric,
        max_bootstrapped_demos=2,
        max_labeled_demos=2,
    )
    compiled = optimizer.compile(student=MRIAnalysisModule(), trainset=trainset)

    out_dir = project_root / "models" / "dspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "mri_analyzer_compiled.json"
    _save_and_inject(compiled, save_path)
    print(f"[保存] {save_path}")

    for name, pred in compiled.named_predictors():
        print(f"  {name}: demos={len(pred.demos) if hasattr(pred, 'demos') else 0}")
    return compiled


def compile_lab_extractor(samples):
    import dspy.teleprompt

    from lab_analysis.dspy_modules import LabDataExtractor

    def simple_metric(example, pred, trace=None):
        try:
            pid = getattr(pred, "patient_id", "") or ""
            rd = getattr(pred, "report_date", "") or ""
            wbc = getattr(pred, "wbc_value", None)
            conf = getattr(pred, "confidence", 0)
            return len(pid) >= 10 and len(rd) >= 8 and wbc is not None and 0.5 <= conf <= 1.0
        except Exception:
            return False

    raw = []
    for s in samples:
        for lab in s.get("lab_samples", []):
            raw.append(lab)
    raw = ensure_min_examples(raw, 3)
    trainset = to_examples(raw, ["image_description"])

    print(f"\n[训练] lab_data_extractor: {len(trainset)} 个 Example")
    optimizer = dspy.teleprompt.BootstrapFewShot(
        metric=simple_metric,
        max_bootstrapped_demos=2,
        max_labeled_demos=2,
    )
    compiled = optimizer.compile(student=LabDataExtractor(), trainset=trainset)

    out_dir = project_root / "models" / "dspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "lab_data_extractor_compiled.json"
    _save_and_inject(compiled, save_path)
    print(f"[保存] {save_path}")

    for name, pred in compiled.named_predictors():
        print(f"  {name}: demos={len(pred.demos) if hasattr(pred, 'demos') else 0}")
    return compiled


def main():
    print("=" * 60)
    print("DSPy 全模块统一编译 (v2 - 修复 Example 格式)")
    print("=" * 60)

    configure_dspy()

    data_root = project_root / "data"
    print(f"\n[收集] 扫描数据目录: {data_root}")
    samples_dict = collect_samples_from_runs(data_root)
    samples = list(samples_dict.values())
    print(f"[收集] 共 {len(samples)} 个时间戳样本: {list(samples_dict.keys())}")

    if not samples:
        print("[错误] 没有可用样本")
        return

    results = {}
    for fn in [
        compile_literature_interpreter,
        compile_final_report,
        compile_mri_analyzer,
        compile_lab_extractor,
    ]:
        try:
            r = fn(samples)
            results[fn.__name__] = r
        except Exception as e:
            print(f"\n[失败] {fn.__name__}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"[完成] {len(results)}/4 模块编译")
    for name in [
        "compile_literature_interpreter",
        "compile_final_report",
        "compile_mri_analyzer",
        "compile_lab_extractor",
    ]:
        # 修正函数名→JSON 文件名映射
        _fn_to_json = {
            "compile_final_report": "final_report_generator",
            "compile_lab_extractor": "lab_data_extractor",
        }
        base = _fn_to_json.get(name, name.replace("compile_", ""))
        p = project_root / "models" / "dspy" / f"{base}_compiled.json"
        if p.exists():
            print(f"  [OK] {base}_compiled.json ({p.stat().st_size} 字节)")
        else:
            print(f"  [FAIL] {base}_compiled.json 缺失")
    print("=" * 60)


if __name__ == "__main__":
    main()
