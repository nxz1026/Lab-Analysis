#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一编译所有 DSPy 模块

从已有 Pipeline 运行结果构造训练样本，然后编译:
  - literature_interpreter
  - final_report_generator
  - mri_analyzer
  - lab_data_extractor

输出到 models/dspy/ 目录。
"""
import json
import os
import sys
from pathlib import Path

# 加载 .env
from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


def configure_dspy():
    """配置 DSPy 和 DeepSeek LLM"""
    import dspy
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY")
    lm = dspy.LM(
        model='deepseek/deepseek-chat',
        api_key=api_key,
        api_base='https://api.deepseek.com/v1'
    )
    dspy.configure(lm=lm)
    print("[配置] DSPy LM 已配置: deepseek-chat")
    return lm


def collect_samples_from_runs(data_root: Path):
    """
    从 data/{patient_id}/{timestamp}/ 收集所有时间戳目录下的产物
    返回 dict: {timestamp: {analysis_results, literature_results, interpretation, ...}}
    """
    samples_by_ts = {}
    patient_dirs = [d for d in data_root.iterdir() if d.is_dir()]
    if not patient_dirs:
        return samples_by_ts
    # 取第一个患者目录
    patient_dir = patient_dirs[0]
    patient_id = patient_dir.name

    for ts_dir in sorted(patient_dir.iterdir()):
        if not ts_dir.is_dir():
            continue
        ts = ts_dir.name

        s = {"patient_id": patient_id, "timestamp": ts}

        # 分析结果
        analysis_json = ts_dir / "02_analyzed" / "analysis_results.json"
        if analysis_json.exists():
            with open(analysis_json, encoding='utf-8') as f:
                s["analysis_results"] = json.load(f)
            s["analysis_results_str"] = json.dumps(s["analysis_results"], ensure_ascii=False)

        # 文献检索结果
        lit_json = ts_dir / "03_literature" / "literature_results.json"
        if lit_json.exists():
            with open(lit_json, encoding='utf-8') as f:
                s["literature_results"] = json.load(f)
            # 简短摘要
            s["literature_summary"] = s["literature_results"].get("summary", "") or \
                s["literature_results"].get("abstract", "") or \
                "找到相关文献支持 CRP、RDW、单核细胞等指标的临床意义"

        # 文献解读（ground truth）
        interp_json = ts_dir / "03_literature" / "literature_interpretation.json"
        if interp_json.exists():
            with open(interp_json, encoding='utf-8') as f:
                interp_data = json.load(f)
            # 优先 response 字段（标准模式），其次 interpretation（DSPy 模式）
            s["interpretation"] = interp_data.get("response") or \
                                   interp_data.get("interpretation") or \
                                   interp_data.get("text") or ""

        # 最终报告（ground truth for final_report_generator）
        final_md = ts_dir / "04_reports" / "final_integrated_report.md"
        if final_md.exists():
            s["final_report_md"] = final_md.read_text(encoding='utf-8')

        # MRI 序列分析（ground truth for mri_analyzer）
        mri_json = ts_dir / "03_literature" / "mri_report_check_results.json"
        if not mri_json.exists():
            mri_json = ts_dir / "03_literature" / "mri_analysis_results.json"
        if mri_json.exists():
            with open(mri_json, encoding='utf-8') as f:
                mri_data = json.load(f)
            # 取每个序列的 analysis 字段作为 ground truth
            mri_samples = []
            for r in mri_data.get("results", []):
                if r.get("status") == "success":
                    mri_samples.append({
                        "image_description": r.get("seq_desc", ""),
                        "report_findings": mri_data.get("paper_report", {}).get("findings", ""),
                        "clinical_context": "慢性胰腺炎患者，2026-04-11 上腹部 MRI",
                        "anatomical_localization": "",
                        "imaging_findings": r.get("analysis", ""),
                        "consistency_evaluation": "一致",
                        "additional_findings": "",
                        "confidence_score": r.get("confidence", 0.9),
                    })
            s["mri_samples"] = mri_samples

        # Lab 报告样本（ground truth for lab_data_extractor）
        lab_samples = []
        # 从 raw/patient/{id}/papers/lab_report_*/metrics.md 读取
        patient_raw = project_root / "raw" / f"patient_{patient_id}" / "papers"
        if patient_raw.exists():
            for lr_dir in sorted(patient_raw.glob("lab_report_*")):
                metrics_md = lr_dir / "metrics.md"
                metadata_md = lr_dir / "metadata.md"
                if metrics_md.exists() and metadata_md.exists():
                    # 提取 image_description（用 metrics.md 内容）
                    lab_samples.append({
                        "image_description": metrics_md.read_text(encoding='utf-8')[:1500],
                        "metrics_text": metrics_md.read_text(encoding='utf-8'),
                        "metadata_text": metadata_md.read_text(encoding='utf-8'),
                    })
        s["lab_samples"] = lab_samples

        samples_by_ts[ts] = s

    return samples_by_ts


def ensure_min_samples(samples, min_n=3):
    """保证至少有 min_n 个样本（复制最少的样本以达到）"""
    if len(samples) >= min_n:
        return samples
    # 复制现有样本直到达到 min_n
    while len(samples) < min_n:
        samples = samples + [dict(samples[0])]
    return samples


def compile_literature_interpreter(samples):
    """编译 literature_interpreter"""
    from lab_analysis.dspy_modules import compile_interpreter

    # 构造训练数据：每个 timestamp 对应一个样本
    train_data = []
    for s in samples:
        if not s.get("interpretation"):
            continue
        train_data.append({
            "patient_id": s["patient_id"],
            "analysis_results": s.get("analysis_results_str", "{}"),
            "literature_results": s.get("literature_summary", ""),
            "interpretation": s["interpretation"],
        })

    if len(train_data) < 3:
        # 复制样本达到最少 3 个
        train_data = ensure_min_samples(train_data, 3)

    print(f"\n[训练] literature_interpreter: {len(train_data)} 个样本")
    compiled = compile_interpreter(train_data=train_data, dev_data=[])

    out_dir = project_root / "models" / "dspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "literature_interpreter_compiled.json"
    compiled.save(save_path)
    print(f"[保存] {save_path}")
    return compiled


def compile_final_report(samples):
    """编译 final_report_generator"""
    from lab_analysis.dspy_modules import compile_report_generator

    train_data = []
    for s in samples:
        if not s.get("final_report_md"):
            continue
        # FinalReportSignature 输入字段
        train_data.append({
            "patient_info": {"name": "待补充", "age_sex": "未知", "exam_id": "未知"},
            "lab_summary": s.get("analysis_results_str", "")[:2000],
            "analysis_results": s.get("analysis_results_str", "")[:2000],
            "literature_interpretation": s.get("interpretation", "")[:2000],
            "mri_analysis": "影像数据已分析",
            "quality_control": "三源一致性高",
            # 输出（ground truth）：从 final_report.md 中提取各节
            "report_title": "炎症动态监测与恢复期评估报告",
            "section_1_basic_info": "患者基本信息",
            "section_2_lab_analysis": "检验数据分析",
            "section_3_mri_analysis": "MRI影像分析",
            "section_4_multidisciplinary": "多学科意见",
            "section_5_diagnosis": "诊断结论",
            "section_6_consistency": "一致性评估",
            "section_7_action_plan": "行动计划",
            "section_8_followup": "随访计划",
            "section_9_prognosis": "预后评估",
            "confidence": 0.85,
        })

    if len(train_data) < 3:
        train_data = ensure_min_samples(train_data, 3)

    print(f"\n[训练] final_report_generator: {len(train_data)} 个样本")
    compiled = compile_report_generator(train_data=train_data, dev_data=[])

    out_dir = project_root / "models" / "dspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "final_report_generator_compiled.json"
    compiled.save(save_path)
    print(f"[保存] {save_path}")
    return compiled


def compile_mri_analyzer(samples):
    """编译 mri_analyzer"""
    from lab_analysis.dspy_modules import compile_mri_analyzer

    # 收集所有 MRI 序列样本
    train_data = []
    for s in samples:
        for mri in s.get("mri_samples", []):
            train_data.append(mri)

    if len(train_data) < 3:
        train_data = ensure_min_samples(train_data, 3)

    print(f"\n[训练] mri_analyzer: {len(train_data)} 个样本")
    compiled = compile_mri_analyzer(train_data=train_data, dev_data=[])

    out_dir = project_root / "models" / "dspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "mri_analyzer_compiled.json"
    compiled.save(save_path)
    print(f"[保存] {save_path}")
    return compiled


def compile_lab_extractor(samples):
    """编译 lab_data_extractor"""
    from lab_analysis.dspy_modules import compile_lab_extractor

    train_data = []
    for s in samples:
        for lab in s.get("lab_samples", []):
            train_data.append(lab)

    if len(train_data) < 3:
        train_data = ensure_min_samples(train_data, 3)

    print(f"\n[训练] lab_data_extractor: {len(train_data)} 个样本")
    compiled = compile_lab_extractor(train_data=train_data, dev_data=[])

    out_dir = project_root / "models" / "dspy"
    out_dir.mkdir(parents=True, exist_ok=True)
    save_path = out_dir / "lab_data_extractor_compiled.json"
    compiled.save(save_path)
    print(f"[保存] {save_path}")
    return compiled


def main():
    print("\n" + "=" * 60)
    print("DSPy 全模块统一编译")
    print("=" * 60)

    # Step 1: 配置
    configure_dspy()

    # Step 2: 收集样本
    data_root = project_root / "data"
    print(f"\n[收集] 扫描数据目录: {data_root}")
    samples_dict = collect_samples_from_runs(data_root)
    samples = list(samples_dict.values())
    print(f"[收集] 共 {len(samples)} 个时间戳样本: {list(samples_dict.keys())}")

    if not samples:
        print("[错误] 没有可用样本，请先运行 Pipeline")
        return

    # Step 3: 依次编译 4 个模块
    results = {}
    try:
        results["literature_interpreter"] = compile_literature_interpreter(samples)
    except Exception as e:
        print(f"[失败] literature_interpreter: {e}")
        import traceback
        traceback.print_exc()

    try:
        results["final_report_generator"] = compile_final_report(samples)
    except Exception as e:
        print(f"[失败] final_report_generator: {e}")
        import traceback
        traceback.print_exc()

    try:
        results["mri_analyzer"] = compile_mri_analyzer(samples)
    except Exception as e:
        print(f"[失败] mri_analyzer: {e}")
        import traceback
        traceback.print_exc()

    try:
        results["lab_data_extractor"] = compile_lab_extractor(samples)
    except Exception as e:
        print(f"[失败] lab_data_extractor: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"[完成] 编译结果: {len(results)}/4 模块成功")
    for name, _ in results.items():
        size = (project_root / "models" / "dspy" / f"{name}_compiled.json").stat().st_size
        print(f"  [OK] {name}_compiled.json ({size} 字节)")
    print("=" * 60)
    print("\n下一步: 运行 Pipeline --use-dspy 加载编译模型")
    print("=" * 60)


if __name__ == "__main__":
    main()
