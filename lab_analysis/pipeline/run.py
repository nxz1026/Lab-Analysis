"""lab_analysis.pipeline.run — Pipeline 编排器（main 函数）"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from lab_analysis.patient_id import validate_id_card
from lab_analysis.pipeline.cli import get_deid, parse_args
from lab_analysis.pipeline.ingest import auto_ingest_from_origin_data
from lab_analysis.pipeline.steps import (
    check_patient_data,
    extract_patient_id_from_reports,
    pick_python_exe,
    run_step,
)
from lab_analysis.utils import WORK_ROOT


def main():
    args = parse_args()
    raw_id = None

    # 步骤1：优先从已摄入的检验报告中自动提取身份证号
    print("[INFO] 尝试从已摄入的检验报告中自动提取身份证号...")
    raw_id = extract_patient_id_from_reports()

    # 步骤2：无法自动提取则强制交互输入
    if not raw_id:
        print("[INFO] 未能自动识别身份证号，请手动输入")
        try:
            raw_id = input("请输入患者身份证号: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[ERROR] 无法读取输入，本 Pipeline 要求交互式提供合法身份证号")
            sys.exit(1)

    # 步骤3：强制校验身份证号格式
    raw_id = validate_id_card(raw_id, interactive=True)
    if not raw_id:
        print("[ERROR] 未获得有效的身份证号，退出")
        sys.exit(1)

    deid = get_deid(raw_id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir = f"{deid}/{ts}"

    print(f"[{datetime.now().isoformat()}] Pipeline 启动")
    print(f"脱敏病人ID: {deid}")
    print(f"输出目录: data/{ts_dir}/")
    print(f"时间戳: {ts}")

    # ① 数据摄入
    if not args.skip_ingest:
        auto_ingest_from_origin_data(
            id_card=raw_id,
            report_date=args.report_date,
            report_type=args.report_type,
            no_interactive=args.no_interactive,
        )

        if args.ingest_lab or args.ingest_dicom_zip or args.ingest_dicom_dir or args.ingest_mri_report:
            print("\n① 数据摄入 (手动指定)")
            python = pick_python_exe()
            root = Path(__file__).resolve().parent.parent.parent
            full_env = dict(os.environ)
            pp = str(root)
            full_env["PYTHONPATH"] = pp + os.pathsep + full_env.get("PYTHONPATH", "")

            if args.ingest_lab:
                for lab_path in args.ingest_lab:
                    cmd = [python, "-m", "lab_analysis.ingest_data", "--type", "lab_image",
                           "--path", lab_path, "--id-card", raw_id]
                    if args.report_date:
                        cmd += ["--report-date", args.report_date]
                    if args.report_type:
                        cmd += ["--report-type", args.report_type]
                    print(f"  摄入检验报告: {lab_path}")
                    r = subprocess.run(cmd, cwd=str(root), env=full_env)
                    if r.returncode != 0:
                        print(f"  [!] 摄入失败: {lab_path}")

            if args.ingest_dicom_zip or args.ingest_dicom_dir:
                cmd = [python, "-m", "lab_analysis.ingest_data", "--type", "mri_dicom",
                       "--id-card", raw_id]
                if args.ingest_dicom_zip:
                    cmd += ["--zip-path", args.ingest_dicom_zip]
                if args.ingest_dicom_dir:
                    cmd += ["--dicom-dir", args.ingest_dicom_dir]
                if args.report_date:
                    cmd += ["--report-date", args.report_date]
                r = subprocess.run(cmd, cwd=str(root), env=full_env)
                if r.returncode != 0:
                    print("  [!] DICOM摄入失败")

            if args.ingest_mri_report:
                cmd = [python, "-m", "lab_analysis.ingest_data", "--type", "mri_report",
                       "--path", args.ingest_mri_report, "--id-card", raw_id]
                if args.report_date:
                    cmd += ["--report-date", args.report_date]
                r = subprocess.run(cmd, cwd=str(root), env=full_env)
                if r.returncode != 0:
                    print("  [!] MRI报告摄入失败")

            print("\n[OK] 数据摄入完成，继续执行Pipeline...\n")

    del raw_id  # 不再持有原始身份证号

    # ② 前置检查
    print("② 前置检查：验证病人数据")
    if not check_patient_data(deid):
        wr = WORK_ROOT
        print(f"\n[ERROR] 病人ID [{deid}] 没有找到对应的原始数据，请确认目录结构：")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'lab'}/        ← 检验报告截图")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'papers'}/    ← 结构化报告（lab_report_*/metrics.md）")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'imaging'}/   ← MRI 影像序列（可选）")
        sys.exit(1)

    pid_arg = ["--id-card", deid]
    ts_env = {"ANALYSIS_TS": ts}

    rc = run_step("③ 数据加载", "data_loader", pid_arg, ts_env)
    if rc != 0:
        print("[!] data_loader 失败，退出")
        sys.exit(1)
    rc = run_step("④ 数据分析", "data_analyzer", pid_arg, ts_env)
    if rc != 0:
        print("[!] data_analyzer 失败，退出")
        sys.exit(1)
    rc = run_step("⑤ 文献检索", "literature_searcher", pid_arg, ts_env)
    if rc != 0:
        print("[!] literature_searcher 失败，退出")
        sys.exit(1)

    # ⑤b 文献二次筛选（evidence-grading 可选增强）
    if args.skip_lit_filter:
        print("\n[跳过] 文献二次筛选（--skip-lit-filter）")
    else:
        rc = run_step(
            "⑤b 文献二次筛选", "literature_filter",
            env=ts_env,
            extra_args=pid_arg + [
                "--scenario", args.lit_filter_scenario,
                "--top-k", str(args.lit_filter_top_k),
            ],
        )
        if rc != 0:
            print("[!] literature_filter 失败（非致命，继续）")

    if args.skip_llm:
        print("\n[跳过] 循证解读（--skip-llm）")
    else:
        if args.use_dspy:
            rc = run_step("⑥ 循证解读", "literature_interpreter_dspy",
                          env=ts_env, extra_args=pid_arg + ["--use-dspy"])
        else:
            rc = run_step("⑥ 循证解读", "literature_interpreter", pid_arg, ts_env)
        if rc != 0:
            print("[!] literature_interpreter 失败（非致命，继续）")

    if args.skip_imaging:
        print("\n[跳过] 影像分析（--skip-imaging）")
    else:
        if args.use_dspy:
            rc = run_step("⑦ 影像分析", "qwen_vl_report_check_dspy",
                          env=ts_env, extra_args=pid_arg + ["--use-dspy"])
        else:
            rc = run_step("⑦ 影像分析", "qwen_vl_report_check", pid_arg, ts_env)
        if rc != 0:
            print("[!] qwen_vl_report_check 失败（非致命，继续）")

    if args.use_dspy:
        rc = run_step("⑧ 生成报告", "gen_final_report_dspy",
                      env=ts_env, extra_args=pid_arg + ["--use-dspy"])
    else:
        rc = run_step("⑧ 生成报告", "gen_final_report", pid_arg, ts_env)
    if rc != 0:
        print("[!] gen_final_report 失败（非致命，继续）")

    # ⑧b 评分卡 & 决策支持
    if args.skip_scoring:
        print("\n[跳过] 评分卡 & 决策支持（--skip-scoring）")
    else:
        rc = run_step("⑧b 评分卡", "scoring_card", pid_arg, ts_env)
        if rc != 0:
            print("[!] scoring_card 失败（非致命，继续）")

    rc = run_step("⑨ 文件归档", "organize_local_files", pid_arg, ts_env)
    if rc != 0:
        print("[!] organize_local_files 失败（非致命，完成）")

    # ⑨b FHIR 输出
    if args.skip_fhir:
        print("\n[跳过] FHIR 输出（--skip-fhir）")
    else:
        rc = run_step("⑨b FHIR 输出", "fhir_exporter", pid_arg, ts_env)
        if rc != 0:
            print("[!] fhir_exporter 失败（非致命，继续）")

    # ⑩ 旧产物清理
    if args.skip_cleanup:
        print("\n[跳过] 旧产物清理（--skip-cleanup）")
    else:
        print(f"\n⑩ 旧产物清理（保留最近 {args.keep_last} 次）")
        try:
            from lab_analysis.cleanup_runs import cleanup_all, print_summary
            clean_results = cleanup_all(keep_last=args.keep_last, dry_run=False, id_card=deid)
            print_summary(clean_results)
        except Exception as e:
            print(f"  [!] 产物清理失败（非致命）: {e}")

    data_dir = WORK_ROOT / "data" / ts_dir
    print(f"\n[{datetime.now().isoformat()}] Pipeline 完成")
    print(f"\n输出目录：{data_dir}/")
    if data_dir.exists():
        for f in sorted(data_dir.iterdir()):
            print(f"  - {f.name}")
