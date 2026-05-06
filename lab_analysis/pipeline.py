#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline 统一入口：串联各步骤子模块。

用法：
  仓库根目录：python run_analysis.py --patient-id <诊疗卡号>
  或：python -m lab_analysis --patient-id <诊疗卡号>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from lab_analysis.patient_id import encode

WIKI_ROOT = Path.home() / "wiki"


def parse_args():
    parser = argparse.ArgumentParser(description="医学分析 Pipeline 统一入口")
    parser.add_argument("--patient-id", type=str, default=None, help="病人诊疗卡号（可选，如果不提供则从数据中自动识别或提示输入）")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 循证解读步骤")
    parser.add_argument("--skip-imaging", action="store_true", help="跳过影像分析步骤")
    parser.add_argument("--ingest-lab", type=str, nargs="*", help="检验报告图片路径列表")
    parser.add_argument("--ingest-dicom-zip", type=str, help="DICOM ZIP文件路径")
    parser.add_argument("--ingest-dicom-dir", type=str, help="DICOM已解压目录路径")
    parser.add_argument("--ingest-mri-report", type=str, help="MRI文字报告路径")
    parser.add_argument("--report-date", type=str, help="报告日期 YYYY-MM-DD（用于摄入）")
    parser.add_argument("--report-type", type=str, choices=["outpatient", "inpatient"], 
                       help="报告类型 outpatient/inpatient（仅检验报告需要）")
    return parser.parse_args()


def repo_root() -> Path:
    """本仓库根目录（含 pyproject.toml / lab_analysis 包）。"""
    return Path(__file__).resolve().parent.parent


def get_deid(original_id: str) -> str:
    """从映射文件查 de-identified ID；若无映射则用 encode()。"""
    mapping_file = Path.home() / ".hermes" / "patient_mapping.json"
    if mapping_file.exists():
        with open(mapping_file, encoding="utf-8") as f:
            mapping = json.load(f)
        for deid, orig in mapping.items():
            if orig == original_id or deid == original_id:
                return deid
    return encode(original_id)


def extract_patient_id_from_reports() -> str:
    """
    从已摄入的检验报告中提取患者ID
    
    Returns:
        患者ID，如果无法提取则返回 None
    """
    raw_dir = WIKI_ROOT / "raw"
    if not raw_dir.exists():
        return None
    
    # 查找所有 patient_* 目录
    patient_dirs = [d for d in raw_dir.iterdir() if d.is_dir() and d.name.startswith("patient_")]
    if not patient_dirs:
        return None
    
    # 尝试从第一个有papers目录的患者中提取ID
    for patient_dir in patient_dirs:
        papers_dir = patient_dir / "papers"
        if not papers_dir.exists():
            continue
        
        # 查找所有 lab_report_* 目录
        report_dirs = [d for d in papers_dir.iterdir() if d.is_dir() and d.name.startswith("lab_report_")]
        if not report_dirs:
            continue
        
        # 读取第一个报告的 metadata.md
        first_report = report_dirs[0]
        metadata_path = first_report / "metadata.md"
        if not metadata_path.exists():
            continue
        
        metadata_text = metadata_path.read_text(encoding="utf-8")
        # 解析表格格式的 metadata
        for line in metadata_text.splitlines():
            line = line.strip()
            if line.startswith("|") and "患者ID" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    patient_id = parts[2].strip()
                    if patient_id:
                        print(f"[INFO] 从检验报告中提取到患者ID: {patient_id}")
                        return patient_id
    
    return None


def check_patient_data(deid: str) -> bool:
    """检查病人原始数据目录是否存在且有内容（de-id 目录名）。"""
    raw_dir = WIKI_ROOT / "raw" / f"patient_{deid}"
    lab_dir = raw_dir / "lab"
    imaging_dir = raw_dir / "imaging"
    papers_dir = raw_dir / "papers"

    errors = []
    warnings = []
    if not raw_dir.exists():
        errors.append(f"  [ERROR] 病人目录不存在: {raw_dir}")
    else:
        has_lab = lab_dir.exists() and any(lab_dir.iterdir())
        has_papers = papers_dir.exists() and any(papers_dir.iterdir())
        has_imaging = imaging_dir.exists() and any(imaging_dir.iterdir())

        if not has_lab and not has_papers:
            errors.append(f"  [ERROR] 未找到检验报告: {lab_dir} 或 {papers_dir}")
        if not has_imaging:
            warnings.append(f"  [WARNING] 未找到影像数据: {imaging_dir}（将跳过影像分析）")

    if errors:
        print("\n".join(errors))
        if warnings:
            print("\n".join(warnings))
        print(f"\n当前 {WIKI_ROOT / 'raw'} 下的病人目录：")
        raw_parent = WIKI_ROOT / "raw"
        if raw_parent.exists():
            for d in sorted(raw_parent.iterdir()):
                if d.is_dir():
                    print(f"  - {d.name}")
        else:
            print("  （raw 目录为空或不存在）")
        return False
    
    if warnings:
        print("\n".join(warnings))
    
    return True


def pick_python_exe() -> str:
    """优先使用 ~/wiki/.venv（Hermes 部署）；否则当前解释器。"""
    unix_venv = WIKI_ROOT / ".venv" / "bin" / "python"
    win_venv = WIKI_ROOT / ".venv" / "Scripts" / "python.exe"
    if unix_venv.is_file():
        return str(unix_venv)
    if win_venv.is_file():
        return str(win_venv)
    return sys.executable


def run_step(name: str, module: str, extra_args: list[str] | None = None, env: dict | None = None) -> int:
    """以 python -m lab_analysis.<module> 运行单步。"""
    root = repo_root()
    python = pick_python_exe()
    cmd = [python, "-m", f"lab_analysis.{module}"]
    if extra_args:
        cmd.extend(extra_args)
    print(f"\n{'='*60}")
    print(f"[STEP] {name}")
    print(f"命令: {' '.join(cmd)}")
    print(f"{'='*60}")
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    pp = str(root)
    if full_env.get("PYTHONPATH"):
        full_env["PYTHONPATH"] = pp + os.pathsep + full_env["PYTHONPATH"]
    else:
        full_env["PYTHONPATH"] = pp
    result = subprocess.run(cmd, cwd=str(root), env=full_env)
    return result.returncode


def main():
    args = parse_args()
    original_id = args.patient_id
    
    # 步骤1：获取患者ID（优先级：命令行参数 > 从报告提取 > 用户输入）
    if not original_id:
        print("[INFO] 未提供 --patient-id 参数，尝试从已摄入的检验报告中提取...")
        original_id = extract_patient_id_from_reports()
    
    # 步骤2：如果仍然没有ID，提示用户输入
    if not original_id:
        print("[WARNING] 无法从数据中自动识别患者ID")
        try:
            original_id = input("请输入患者身份证号: ").strip()
            if not original_id:
                print("[ERROR] 未输入患者ID，退出")
                sys.exit(1)
            print(f"[INFO] 使用用户输入的ID: {original_id}")
        except (EOFError, KeyboardInterrupt):
            print("\n[ERROR] 无法读取输入，请使用 --patient-id 参数提供患者ID")
            sys.exit(1)
    
    # 步骤3：生成脱敏ID
    deid = get_deid(original_id)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir = f"{deid}/{ts}"

    print(f"[{datetime.now().isoformat()}] Pipeline 启动")
    print(f"原始病人ID: {original_id}")
    print(f"脱敏病人ID: {deid}")
    print(f"输出目录: data/{ts_dir}/")
    print(f"时间戳: {ts}")

    # ① 数据摄入（如果提供了摄入参数）
    if args.ingest_lab or args.ingest_dicom_zip or args.ingest_dicom_dir or args.ingest_mri_report:
        print("\n① 数据摄入 (ingest_data)")
        python = pick_python_exe()
        root = repo_root()
        full_env = dict(os.environ)
        pp = str(root)
        if full_env.get("PYTHONPATH"):
            full_env["PYTHONPATH"] = pp + os.pathsep + full_env["PYTHONPATH"]
        else:
            full_env["PYTHONPATH"] = pp
        
        # 摄入检验报告图片
        if args.ingest_lab:
            for lab_path in args.ingest_lab:
                cmd = [python, "-m", "lab_analysis.ingest_data",
                      "--type", "lab_image",
                      "--path", lab_path,
                      "--patient-id", original_id]
                if args.report_date:
                    cmd.extend(["--report-date", args.report_date])
                if args.report_type:
                    cmd.extend(["--report-type", args.report_type])
                print(f"  摄入检验报告: {lab_path}")
                result = subprocess.run(cmd, cwd=str(root), env=full_env)
                if result.returncode != 0:
                    print(f"  [!] 摄入失败: {lab_path}")
        
        # 摄入DICOM数据
        if args.ingest_dicom_zip or args.ingest_dicom_dir:
            cmd = [python, "-m", "lab_analysis.ingest_data",
                  "--type", "mri_dicom",
                  "--patient-id", original_id]
            if args.ingest_dicom_zip:
                cmd.extend(["--zip-path", args.ingest_dicom_zip])
            if args.ingest_dicom_dir:
                cmd.extend(["--dicom-dir", args.ingest_dicom_dir])
            if args.report_date:
                cmd.extend(["--report-date", args.report_date])
            print(f"  摄入DICOM数据...")
            result = subprocess.run(cmd, cwd=str(root), env=full_env)
            if result.returncode != 0:
                print(f"  [!] DICOM摄入失败")
        
        # 摄入MRI文字报告
        if args.ingest_mri_report:
            cmd = [python, "-m", "lab_analysis.ingest_data",
                  "--type", "mri_report",
                  "--path", args.ingest_mri_report,
                  "--patient-id", original_id]
            if args.report_date:
                cmd.extend(["--report-date", args.report_date])
            print(f"  摄入MRI报告: {args.ingest_mri_report}")
            result = subprocess.run(cmd, cwd=str(root), env=full_env)
            if result.returncode != 0:
                print(f"  [!] MRI报告摄入失败")
        
        print("\n✅ 数据摄入完成，继续执行Pipeline...\n")

    # ② 前置检查：验证病人数据
    print("② 前置检查：验证病人数据")
    if not check_patient_data(deid):
        wr = WIKI_ROOT
        print(f"\n[ERROR] 病人ID [{deid}] 没有找到对应的原始数据，请确认目录结构：")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'lab'}/        ← 检验报告截图")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'papers'}/    ← 结构化报告（lab_report_*/metrics.md）")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'imaging'}/   ← MRI 影像序列（可选）")
        print("\n请确认病人ID，或将数据放入上述目录后重新执行。")
        sys.exit(1)

    pid_arg = ["--patient-id", deid]
    ts_env = {"ANALYSIS_TS": ts}

    rc = run_step("③ 数据加载 (data_loader)", "data_loader", pid_arg, ts_env)
    if rc != 0:
        print("[!] data_loader 失败，退出")
        sys.exit(1)

    rc = run_step("④ 数据分析 (data_analyzer)", "data_analyzer", pid_arg, ts_env)
    if rc != 0:
        print("[!] data_analyzer 失败，退出")
        sys.exit(1)

    rc = run_step("⑤ 文献检索 (literature_searcher)", "literature_searcher", pid_arg, ts_env)
    if rc != 0:
        print("[!] literature_searcher 失败，退出")
        sys.exit(1)

    if args.skip_llm:
        print("\n[跳过] 循证解读（--skip-llm）")
    else:
        rc = run_step("⑥ 循证解读 (literature_interpreter)", "literature_interpreter", pid_arg, ts_env)
        if rc != 0:
            print("[!] literature_interpreter 失败（非致命，继续）")

    if args.skip_imaging:
        print("\n[跳过] 影像分析（--skip-imaging）")
    else:
        rc = run_step("⑦ 影像分析 (qwen_vl_report_check)", "qwen_vl_report_check", pid_arg, ts_env)
        if rc != 0:
            print("[!] qwen_vl_report_check 失败（非致命，继续）")

    rc = run_step("⑧ 生成最终报告 (gen_final_report)", "gen_final_report", pid_arg, ts_env)
    if rc != 0:
        print("[!] gen_final_report 失败（非致命，继续）")

    rc = run_step("⑨ 飞书上云 (upload_to_feishu)", "upload_to_feishu", pid_arg, ts_env)
    if rc != 0:
        print("[!] upload_to_feishu 失败（非致命，完成）")

    data_dir = WIKI_ROOT / "data" / ts_dir
    print(f"\n[{datetime.now().isoformat()}] Pipeline 完成")
    print(f"\n输出目录：{data_dir}/")
    if data_dir.exists():
        for f in sorted(data_dir.iterdir()):
            print(f"  - {f.name}")


if __name__ == "__main__":
    main()
