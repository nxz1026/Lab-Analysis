#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终综合临床诊断报告生成 - DSPy 增强版

支持传统 Prompt 工程和 DSPy 优化两种模式
用法: python gen_final_report_dspy.py --patient-id <ID> [--use-dspy]
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))


def load_env_key(key: str) -> str:
    """加载环境变量"""
    val = os.environ.get(key, "")
    if val:
        return val
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""


def assess_three_source_consistency(data_dir: Path) -> str:
    """评估三源一致性（复用原函数）"""
    from lab_analysis.gen_final_report import assess_three_source_consistency as original_func
    return original_func(data_dir)


def run_standard_mode(patient_id: str, data_dir: Path):
    """运行标准 Prompt 工程模式"""
    from lab_analysis.gen_final_report import build_prompt, call_deepseek
    
    print("[标准] 构建 prompt...")
    prompt = build_prompt(patient_id, data_dir)
    
    print("[标准] 调用 DeepSeek...")
    DEEPSEEK_API_KEY = load_env_key("DEEPSEEK_API_KEY")
    if not DEEPSEEK_API_KEY:
        raise ValueError("未找到 DEEPSEEK_API_KEY")
    
    response = call_deepseek(prompt, DEEPSEEK_API_KEY)
    
    output = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "deepseek-chat",
        "mode": "standard",
        "report_markdown": response,
    }
    
    return output


def run_dspy_mode(patient_id: str, data_dir: Path):
    """运行 DSPy 优化模式"""
    try:
        from lab_analysis.dspy_modules import run_dspy_final_report
        
        # 加载患者信息
        lab_path = data_dir / "02_analyzed" / "lab_metrics.json"
        patient_info = {"name": "患者", "age_sex": "未知", "exam_id": "未知"}
        if lab_path.exists():
            try:
                d = json.loads(lab_path.read_text(encoding="utf-8"))
                reports = d.get("reports", [])
                if reports:
                    report = reports[0]
                    patient_info = {
                        "name": report.get("patient_name", "患者"),
                        "age_sex": report.get("age_sex", "未知"),
                        "exam_id": report.get("exam_id", "未知"),
                    }
            except Exception:
                pass
        
        # 加载检验数据摘要
        lab_summary = ""
        if lab_path.exists():
            try:
                d = json.loads(lab_path.read_text(encoding="utf-8"))
                reports = d.get("reports", [])
                if reports:
                    latest = reports[-1]
                    hs_crp = latest.get("hs-CRP") or latest.get("hsCRP")
                    wbc = latest.get("WBC")
                    neut = latest.get("NEUT%")
                    lab_summary = f"最新检验: hs-CRP={hs_crp}, WBC={wbc}, NEUT%={neut}"
            except Exception:
                pass
        
        # 加载分析结果
        analysis_results = {}
        analysis_path = data_dir / "02_analyzed" / "analysis_results.json"
        if analysis_path.exists():
            try:
                with open(analysis_path, 'r', encoding='utf-8') as f:
                    analysis_results = json.load(f)
            except Exception:
                pass
        
        # 加载文献解读
        literature_interpretation = ""
        interp_path = data_dir / "03_literature" / "literature_interpretation.md"
        if interp_path.exists():
            try:
                literature_interpretation = interp_path.read_text(encoding='utf-8')
            except Exception:
                pass
        
        # 加载 MRI 分析
        mri_analysis = ""
        mri_path = data_dir / "05_imaging" / "mri_report_check_results.md"
        if mri_path.exists():
            try:
                mri_analysis = mri_path.read_text(encoding='utf-8')
            except Exception:
                pass
        
        # 生成质控段落
        quality_control = assess_three_source_consistency(data_dir)
        
        print("[DSPy] 开始生成报告...")
        output = run_dspy_final_report(
            patient_id=patient_id,
            data_dir=data_dir,
            patient_info=patient_info,
            lab_summary=lab_summary,
            analysis_results=analysis_results,
            literature_interpretation=literature_interpretation,
            mri_analysis=mri_analysis,
            quality_control=quality_control
        )
        
        return output
        
    except ImportError as e:
        print(f"[错误] DSPy 模块导入失败: {e}")
        print("请安装 DSPy: pip install dspy-ai")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] DSPy 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="最终报告生成 (DSPy 增强版)")
    parser.add_argument("--patient-id", required=True, help="病人诊疗卡号")
    parser.add_argument("--use-dspy", action="store_true", help="使用 DSPy 优化版本")
    args = parser.parse_args()
    
    patient_id = args.patient_id
    raw_ts = os.environ.get("ANALYSIS_TS", "")
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or patient_id)
    data_dir = WORK_ROOT / "data" / patient_id / ts
    
    # 选择执行模式
    mode_name = "DSPy 优化" if args.use_dspy else "标准 Prompt"
    print(f"\n{'='*60}")
    print(f"最终报告生成 - {mode_name} 模式")
    print(f"{'='*60}\n")
    
    if args.use_dspy:
        output = run_dspy_mode(patient_id, data_dir)
    else:
        output = run_standard_mode(patient_id, data_dir)
    
    # 保存结果
    reports_dir = data_dir / "04_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = reports_dir / "final_integrated_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 保存 Markdown 版本
    md_path = reports_dir / "final_integrated_report.md"
    report_md = output.get("report_markdown", "")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    
    print(f"\n[成功] 报告生成完成 → {output_path}")
    print(f"[报告] Markdown 已保存: {md_path}")
    

if __name__ == "__main__":
    main()
