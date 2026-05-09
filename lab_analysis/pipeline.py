#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline 统一入口：串联各步骤子模块。

用法：
  仓库根目录：python -m lab_analysis --patient-id <诊疗卡号>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .error_reporting import report_error

from .config import WORK_ROOT
from .patient_id import encode


def parse_args():
    parser = argparse.ArgumentParser(description="医学分析 Pipeline 统一入口")
    parser.add_argument("--patient-id", type=str, default=None, help="病人诊疗卡号（可选，如果不提供则从数据中自动识别或提示输入）")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 循证解读步骤")
    parser.add_argument("--skip-imaging", action="store_true", help="跳过影像分析步骤")
    parser.add_argument("--skip-ingest", action="store_true", help="跳过数据摄入步骤（使用已有数据）")
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
    mapping_file = WORK_ROOT / ".hermes" / "patient_mapping.json"
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
    raw_dir = WORK_ROOT / "raw"
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
                        # 注意：此处 patient_id 来自 metadata.md（可能是 raw ID），
                        # 仅用于内部 deid 查找，不对外输出
                        return patient_id
    
    return None


def check_patient_data(deid: str) -> bool:
    """检查病人原始数据目录是否存在且有内容（de-id 目录名）。"""
    raw_dir = WORK_ROOT / "raw" / f"patient_{deid}"
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
        print(f"\n当前 {WORK_ROOT / 'raw'} 下的病人目录：")
        raw_parent = WORK_ROOT / "raw"
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


def auto_ingest_from_origin_data(patient_id: str, deid: str, report_date: str = None, report_type: str = None) -> bool:
    """
    从 Origin_data 目录自动摄入数据

    Args:
        patient_id: 患者原始ID（仅用于查找映射）
        deid: 脱敏ID（所有输出/日志使用）
        report_date: 报告日期（可选）
        report_type: 报告类型（可选）
    
    Returns:
        是否成功摄入数据
    """
    origin_data_dir = WORK_ROOT / "raw" / "Origin_data"
    
    if not origin_data_dir.exists():
        print(f"[INFO] Origin_data 目录不存在: {origin_data_dir}")
        return False
    
    # 查找所有检验报告图片
    lab_images = list(origin_data_dir.glob("lab_*.jpg")) + list(origin_data_dir.glob("lab_*.png"))
    
    # 查找所有MRI报告图片
    mri_images = list(origin_data_dir.glob("mri_*.jpg")) + list(origin_data_dir.glob("mri_*.png"))
    
    # 查找所有DICOM压缩包
    dicom_zips = list(origin_data_dir.glob("export_*.zip")) + list(origin_data_dir.glob("dicom_*.zip"))
    
    # 查找所有DICOM文件（如果在根目录下）
    dcm_files = list(origin_data_dir.glob("*.dcm"))
    
    if not any([lab_images, mri_images, dicom_zips, dcm_files]):
        print(f"[INFO] Origin_data 目录中没有找到任何可处理的文件")
        return False
    
    print(f"\n{'='*60}")
    print(f"[STEP ①] 自动数据摄入 - 从 Origin_data 目录")
    print(f"{'='*60}")
    print(f"发现 {len(lab_images)} 张检验报告图片")
    print(f"发现 {len(mri_images)} 张MRI报告图片")
    print(f"发现 {len(dicom_zips)} 个DICOM压缩包")
    print(f"发现 {len(dcm_files)} 个DICOM文件")
    
    total_success = 0
    
    # 处理检验报告图片
    if lab_images:
        print(f"\n{'─'*60}")
        print(f"【检验报告处理】")
        print(f"{'─'*60}")
        
        for idx, img_path in enumerate(lab_images, 1):
            print(f"\n[{idx}/{len(lab_images)}] 处理: {img_path.name}")
            
            try:
                # 解析文件名中的日期和类型
                filename = img_path.stem  # 不带扩展名
                parts = filename.split('_')
                
                # 尝试从文件名提取日期 (lab_YYYY-MM-DD_type)
                extracted_date = None
                extracted_type = None
                
                for part in parts:
                    if '-' in part and len(part) == 10:  # YYYY-MM-DD
                        extracted_date = part
                    elif part in ['outpatient', 'inpatient']:
                        extracted_type = part
                
                # 使用提供的参数或从文件名提取的参数
                final_date = report_date or extracted_date
                final_type = report_type or extracted_type
                
                if not final_type:
                    print(f"  [WARNING] 无法从文件名确定报告类型，默认为 outpatient")
                    final_type = "outpatient"
                
                print(f"  报告日期: {final_date or '未指定'}")
                print(f"  报告类型: {final_type}")
                
                # 调用 extract_lab_data 模块进行处理
                from lab_analysis import extract_lab_data
                
                # 构建参数
                args = argparse.Namespace(
                    image=str(img_path),
                    patient_id=patient_id,
                    deid=deid,
                    no_interactive=False
                )
                
                # 执行提取
                result = extract_lab_data.main_with_args(args)
                
                if result:
                    total_success += 1
                    print(f"  [OK] 摄入成功")
                else:
                    print(f"  [FAIL] 摄入失败")

            except Exception as e:
                report_error("检验报告摄入", e, {"patient_id": deid, "file": str(img_path)})

    # 处理MRI报告图片
    if mri_images:
        print(f"\n{'─'*60}")
        print(f"【MRI报告处理】")
        print(f"{'─'*60}")
        
        for idx, img_path in enumerate(mri_images, 1):
            print(f"\n[{idx}/{len(mri_images)}] 处理: {img_path.name}")
            
            try:
                # 解析文件名中的日期
                filename = img_path.stem  # 不带扩展名
                parts = filename.split('_')
                
                # 尝试从文件名提取日期 (mri_YYYY-MM-DD)
                extracted_date = None
                
                for part in parts:
                    if '-' in part and len(part) == 10:  # YYYY-MM-DD
                        extracted_date = part
                        break
                
                # 使用提供的参数或从文件名提取的参数
                final_date = report_date or extracted_date
                
                print(f"  报告日期: {final_date or '未指定'}")
                print(f"  [INFO] MRI报告将作为文字报告摄入")
                
                # 调用 ingest_data 模块进行摄入
                from lab_analysis import ingest_data
                
                result = ingest_data.ingest_mri_report(
                    report_path=img_path,
                    patient_id=patient_id,
                    report_date=final_date
                )
                
                if result:
                    total_success += 1
                    print(f"  [OK] MRI报告摄入成功")
                else:
                    print(f"  [FAIL] MRI报告摄入失败")

            except Exception as e:
                report_error("MRI报告摄入", e, {"patient_id": deid, "file": str(img_path)})

    # 处理DICOM压缩包
    if dicom_zips:
        print(f"\n{'─'*60}")
        print(f"【DICOM压缩包处理】")
        print(f"{'─'*60}")
        
        for idx, zip_path in enumerate(dicom_zips, 1):
            print(f"\n[{idx}/{len(dicom_zips)}] 处理: {zip_path.name}")
            
            try:
                # 解析文件名中的日期
                filename = zip_path.stem  # 不带扩展名
                parts = filename.split('_')
                
                # 尝试从文件名提取日期
                extracted_date = None
                
                for part in parts:
                    if '-' in part and len(part) == 10:  # YYYY-MM-DD
                        extracted_date = part
                        break
                
                # 使用提供的参数或从文件名提取的参数
                final_date = report_date or extracted_date
                
                print(f"  报告日期: {final_date or '未指定'}")
                print(f"  [INFO] 正在解压并处理DICOM序列...")
                
                # 调用 ingest_data 模块进行摄入
                from lab_analysis import ingest_data
                
                result = ingest_data.ingest_mri_dicom(
                    zip_path=zip_path,
                    patient_id=patient_id,
                    report_date=final_date
                )
                
                if result:
                    total_success += 1
                    print(f"  [OK] DICOM压缩包摄入成功")
                else:
                    print(f"  [FAIL] DICOM压缩包摄入失败")

            except Exception as e:
                report_error("DICOM摄入", e, {"patient_id": deid, "file": str(zip_path)})

    # 处理DICOM文件（如果直接在根目录下）
    if dcm_files:
        print(f"\n{'─'*60}")
        print(f"【DICOM文件处理】")
        print(f"{'─'*60}")
        print(f"  [WARNING] 发现 {len(dcm_files)} 个DICOM文件在根目录")
        print(f"  [INFO] 建议将DICOM文件组织到子目录中，或使用ZIP压缩包")
        print(f"  [INFO] 跳过直接处理，请使用 --ingest-dicom-dir 手动指定")
    
    print(f"\n{'='*60}")
    total_files = len(lab_images) + len(mri_images) + len(dicom_zips)
    print(f"数据摄入完成: 共处理 {total_files} 个文件，成功 {total_success} 个")
    print(f"{'='*60}\n")
    
    return total_success > 0


def pick_python_exe() -> str:
    """优先使用 ~/wiki/.venv（Hermes 部署）；否则当前解释器。"""
    unix_venv = WORK_ROOT / ".venv" / "bin" / "python"
    win_venv = WORK_ROOT / ".venv" / "Scripts" / "python.exe"
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
            print(f"[INFO] 已确认患者身份")
        except (EOFError, KeyboardInterrupt):
            print("\n[ERROR] 无法读取输入，请使用 --patient-id 参数提供患者ID")
            sys.exit(1)
    
    # 步顤3：生成脱敏ID
    deid = get_deid(original_id)
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir = f"{deid}/{ts}"
    
    print(f"[{datetime.now().isoformat()}] Pipeline 启动")
    print(f"患者标识: {deid}")
    print(f"输出目录: data/{ts_dir}/")
    print(f"时间戳: {ts}")
    
    # ① 数据摄入（第一步）
    if not args.skip_ingest:
        # 先尝试从 Origin_data 自动摄入
        has_origin_data = auto_ingest_from_origin_data(
            patient_id=original_id,
            deid=deid,
            report_date=args.report_date,
            report_type=args.report_type
        )
            
        # 如果提供了手动摄入参数，也执行
        if args.ingest_lab or args.ingest_dicom_zip or args.ingest_dicom_dir or args.ingest_mri_report:
            print("\n① 数据摄入 (手动指定)")
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
        wr = WORK_ROOT
        print(f"\n[ERROR] 病人ID [{deid}] 没有找到对应的原始数据，请确认目录结构：")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'lab'}/        ← 检验报告截图")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'papers'}/    ← 结构化报告（lab_report_*/metrics.md）")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'imaging'}/   ← MRI 影像序列（可选）")
        print("\n请确认病人ID，或将数据放入上述目录后重新执行。")
        sys.exit(1)

    pid_arg = ["--patient-id", deid]
    lit_env  = {"ANALYSIS_TS": ts}
    rc = run_step("③ 数据加载 (data_loader)", "data_loader", pid_arg, lit_env)
    if rc != 0:
        print("[!] data_loader 失败，退出")
        sys.exit(1)

    rc = run_step("④ 数据分析 (data_analyzer)", "data_analyzer", pid_arg,    lit_env)
    if rc != 0:
        print("[!] data_analyzer 失败，退出")
        sys.exit(1)

    rc = run_step("⑤ 文献检索 (literature_searcher)", "literature_searcher", pid_arg,    lit_env)
    if rc != 0:
        print("[!] literature_searcher 失败，退出")
        sys.exit(1)

    if args.skip_llm:
        print("\n[跳过] 循证解读（--skip-llm）")
    else:
        rc = run_step("⑥ 循证解读 (literature_interpreter)", "literature_interpreter", pid_arg,    lit_env)
        if rc != 0:
            print("[!] literature_interpreter 失败（非致命，继续）")

    if args.skip_imaging:
        print("\n[跳过] 影像分析（--skip-imaging）")
    else:
        rc = run_step("⑦ 影像分析 (qwen_vl_report_check)", "qwen_vl_report_check", pid_arg,    lit_env)
        if rc != 0:
            print("[!] qwen_vl_report_check 失败（非致命，继续）")

    rc = run_step("⑧ 生成最终报告 (gen_final_report)", "gen_final_report", pid_arg,    lit_env)
    if rc != 0:
        print("[!] gen_final_report 失败（非致命，继续）")

    rc = run_step("⑨ 本地文件组织 (organize_local_files)", "organize_local_files", pid_arg,    lit_env)
    if rc != 0:
        print("[!] organize_local_files 失败（非致命，完成）")

    data_dir = WORK_ROOT / "data" / ts_dir
    print(f"\n[{datetime.now().isoformat()}] Pipeline 完成")
    print(f"\n输出目录：{data_dir}/")
    if data_dir.exists():
        for f in sorted(data_dir.iterdir()):
            print(f"  - {f.name}")


if __name__ == "__main__":
    main()
