"""lab_analysis.pipeline.run — Pipeline 编排器（main 函数）"""

from __future__ import annotations

import atexit
import contextlib
import contextvars
import ctypes
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

from lab_analysis import _log
from lab_analysis.patient_id import validate_id_card
from lab_analysis.pipeline.cli import get_deid, parse_args
from lab_analysis.pipeline.context import PipelineContext
from lab_analysis.pipeline.ingest import auto_ingest_from_origin_data
from lab_analysis.pipeline.step_defs import CORE_STEPS
from lab_analysis.pipeline.steps import (
    check_patient_data,
    extract_patient_id_from_reports,
    pick_python_exe,
    run_step,
)
from lab_analysis.utils import WORK_ROOT

logger = _log.get_logger("pipeline")


# ---------------------------------------------------------------------------
# P1-4: fatal/正常路径统一的 cleanup 钩子
# ---------------------------------------------------------------------------
# 设计: 注册到 atexit, 不论 main() 走正常结束、sys.exit(1)、KeyboardInterrupt、还是
# 未捕获异常, 进程退出前 atexit handler 都会被调用, 保证 logger handler flush。
# 幂等性: 使用模块级 _cleanup_done 标志防止同一进程多次调用 main() 时重复 flush。
_cleanup_done_var: contextvars.ContextVar[bool] = contextvars.ContextVar("cleanup_done", default=False)


def _cleanup_pipeline_state() -> None:
    """统一的 pipeline 退出清理 (flush logger handlers, 幂等)。

    调用场景:
    - main() 入口处 atexit.register, 正常结束触发
    - run_step() fatal=True 失败 → sys.exit(1) → 进程退出前 atexit 触发
    - 未捕获 Exception → 进程退出前 atexit 触发
    - 重复调用 main() (e.g. 测试) → 幂等, 只 flush 一次
    """
    if _cleanup_done_var.get():
        return
    _cleanup_done_var.set(True)
    for h in logger.handlers:
        # best-effort: cleanup 不能二次崩 (SIM105: 用 contextlib.suppress)
        with contextlib.suppress(Exception):
            h.flush()
    logger.info("[CLEANUP] Pipeline 状态清理完成 (logger flushed)")


def _setup_pipeline_logging(ts: str) -> None:
    """配置 pipeline 日志：输出到 logs/pipeline_{ts}.log。"""
    log_dir = WORK_ROOT / "logs"
    log_file = log_dir / f"pipeline_{ts}.log"
    _log.add_file_handler(logger, log_file)
    logger.setLevel(logging.INFO)
    logger.info("Pipeline 日志初始化: %s", log_file)


def _clear_memory(val: str) -> None:
    """尽力清除字符串内存（Python 字符串不可变，此操作仅覆盖引用）。"""
    try:
        buf = ctypes.create_string_buffer(val.encode("utf-8"))
        ctypes.memset(buf, 0, len(buf))
    except Exception:
        pass


def main():
    args = parse_args()
    raw_id = None
    logger.info("[INFO] 尝试从已摄入的检验报告中自动提取身份证号...")
    raw_id = extract_patient_id_from_reports()
    if not raw_id:
        logger.info("[INFO] 未能自动识别身份证号，请手动输入")
        try:
            raw_id = input("请输入患者身份证号: ").strip()
        except (EOFError, KeyboardInterrupt):
            logger.error("\n[ERROR] 无法读取输入，本 Pipeline 要求交互式提供合法身份证号")
            raise SystemExit(1)
    raw_id = validate_id_card(raw_id, interactive=True)
    if not raw_id:
        logger.error("[ERROR] 未获得有效的身份证号，退出")
        raise SystemExit(1)
    deid = get_deid(raw_id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ctx = PipelineContext(deid=deid, timestamp=ts)
    ts_dir = f"{deid}/{ts}"
    _setup_pipeline_logging(ts)
    # P1-4: 注册 cleanup 到 atexit, 不论 fatal sys.exit(1) 还是正常结束都触发
    atexit.register(_cleanup_pipeline_state)
    logger.info(f"[{datetime.now().isoformat()}] Pipeline 启动")
    logger.info(f"脱敏病人ID: {deid}")
    logger.info(f"输出目录: data/{ts_dir}/")
    logger.info(f"时间戳: {ts}")
    if not args.skip_ingest:
        auto_ingest_from_origin_data(
            id_card=raw_id,
            report_date=args.report_date,
            report_type=args.report_type,
            no_interactive=args.no_interactive,
        )
        if (
            args.ingest_lab
            or args.ingest_dicom_zip
            or args.ingest_dicom_dir
            or args.ingest_mri_report
        ):
            logger.info("\n① 数据摄入 (手动指定)")
            python = pick_python_exe()
            root = Path(__file__).resolve().parent.parent.parent
            full_env = dict(os.environ)
            pp = str(root)
            full_env["PYTHONPATH"] = pp + os.pathsep + full_env.get("PYTHONPATH", "")
            full_env["LAB_RAW_ID_CARD"] = raw_id  # P0: 通过环境变量传递明文ID，避免进程列表泄露
            if args.ingest_lab:
                for lab_path in args.ingest_lab:
                    cmd = [
                        python,
                        "-m",
                        "lab_analysis.ingest_data",
                        "--type",
                        "lab_image",
                        "--path",
                        lab_path,
                    ]
                    if args.report_date:
                        cmd += ["--report-date", args.report_date]
                    if args.report_type:
                        cmd += ["--report-type", args.report_type]
                    logger.info(f"  摄入检验报告: {lab_path}")
                    r = subprocess.run(cmd, cwd=str(root), env=full_env)  # noqa: S603
                    if r.returncode != 0:
                        logger.info(f"  [!] 摄入失败: {lab_path}")
            if args.ingest_dicom_zip or args.ingest_dicom_dir:
                cmd = [
                    python,
                    "-m",
                    "lab_analysis.ingest_data",
                    "--type",
                    "mri_dicom",
                ]
                if args.ingest_dicom_zip:
                    cmd += ["--zip-path", args.ingest_dicom_zip]
                if args.ingest_dicom_dir:
                    cmd += ["--dicom-dir", args.ingest_dicom_dir]
                if args.report_date:
                    cmd += ["--report-date", args.report_date]
                r = subprocess.run(cmd, cwd=str(root), env=full_env)  # noqa: S603
                if r.returncode != 0:
                    logger.error("  [!] DICOM摄入失败")
            if args.ingest_mri_report:
                cmd = [
                    python,
                    "-m",
                    "lab_analysis.ingest_data",
                    "--type",
                    "mri_report",
                    "--path",
                    args.ingest_mri_report,
                ]
                if args.report_date:
                    cmd += ["--report-date", args.report_date]
                r = subprocess.run(cmd, cwd=str(root), env=full_env)  # noqa: S603
                if r.returncode != 0:
                    logger.error("  [!] MRI报告摄入失败")
            del full_env["LAB_RAW_ID_CARD"]
            logger.info("\n[OK] 数据摄入完成，继续执行Pipeline...\n")
    _clear_memory(raw_id)
    del raw_id
    logger.info("② 前置检查：验证病人数据")
    if not check_patient_data(deid):
        wr = WORK_ROOT
        logger.info(f"\n[ERROR] 病人ID [{deid}] 没有找到对应的原始数据，请确认目录结构：")
        logger.info(f"   {wr / 'raw' / f'patient_{deid}' / 'lab'}/        ← 检验报告截图")
        logger.info(
            f"   {wr / 'raw' / f'patient_{deid}' / 'papers'}/    ← 结构化报告（lab_report_*/metrics.md）"
        )
        logger.info(f"   {wr / 'raw' / f'patient_{deid}' / 'imaging'}/   ← MRI 影像序列（可选）")
        raise SystemExit(1)
    pid_arg = ["--id-card", deid]
    ts_env = ctx.env_dict()
    for s in CORE_STEPS:
        run_step(s.name, s.module, pid_arg, ts_env, fatal=s.fatal)
    if args.skip_lit_filter:
        logger.warning("\n[跳过] 文献二次筛选（--skip-lit-filter）")
    else:
        run_step(
            "⑤b 文献二次筛选",
            "literature_filter",
            env=ts_env,
            extra_args=pid_arg
            + ["--scenario", args.lit_filter_scenario, "--top-k", str(args.lit_filter_top_k)],
            fatal=False,
        )
    if args.skip_llm:
        logger.warning("\n[跳过] 循证解读（--skip-llm）")
    else:
        if args.use_dspy:
            run_step(
                "⑥ 循证解读",
                "literature_interpreter_dspy",
                env=ts_env,
                extra_args=pid_arg + ["--use-dspy"],
            )
        else:
            run_step("⑥ 循证解读", "literature_interpreter", pid_arg, ts_env)
    if args.skip_imaging:
        logger.warning("\n[跳过] 影像分析（--skip-imaging）")
    else:
        if args.use_dspy:
            run_step(
                "⑦ 影像分析",
                "qwen_vl_report_check_dspy",
                env=ts_env,
                extra_args=pid_arg + ["--use-dspy"],
            )
        else:
            run_step("⑦ 影像分析", "qwen_vl_report_check", pid_arg, ts_env)
    if args.use_dspy:
        run_step(
            "⑧ 生成报告",
            "gen_final_report_dspy",
            env=ts_env,
            extra_args=pid_arg + ["--use-dspy"],
        )
    else:
        run_step("⑧ 生成报告", "gen_final_report", pid_arg, ts_env)
    if args.skip_scoring:
        logger.warning("\n[跳过] 评分卡 & 决策支持（--skip-scoring）")
    else:
        run_step("⑧b 评分卡", "scoring_card", pid_arg, ts_env, fatal=False)
    if args.compare_report_modes and (not args.use_dspy):
        logger.info(f"\n{'=' * 60}\n[COMPARE] 生成 DSPy 对比报告\n{'=' * 60}")
        dspy_ts = ts + "_dspy_compare"
        dspy_ts_env = {"ANALYSIS_TS": dspy_ts}
        dspy_pid = ["--id-card", deid]
        run_step(
            "⑧ DSPy 循证解读",
            "literature_interpreter_dspy",
            env=dspy_ts_env,
            extra_args=dspy_pid + ["--use-dspy"],
        )
        run_step(
            "⑧ DSPy 影像分析",
            "qwen_vl_report_check_dspy",
            env=dspy_ts_env,
            extra_args=dspy_pid + ["--use-dspy"],
        )
        rc = run_step(
            "⑧ DSPy 生成报告",
            "gen_final_report_dspy",
            env=dspy_ts_env,
            extra_args=dspy_pid + ["--use-dspy"],
        )
        if rc != 0:
            logger.error("[!] DSPy gen_final_report 失败（非致命，继续）")
        std_md = ctx.reports_dir / "final_integrated_report.md"
        dspy_ts_ctx = PipelineContext(deid=deid, timestamp=dspy_ts)
        dspy_json = dspy_ts_ctx.reports_dir / "final_integrated_report.json"
        if std_md.exists() and dspy_json.exists():
            try:
                from lab_analysis.compare_report_modes import (
                    compare_reports_from_files,
                    format_comparison_md,
                )

                cmp = compare_reports_from_files(std_md, dspy_json)
                cmp_dir = ctx.reports_dir
                (cmp_dir / "mode_comparison.json").write_text(
                    json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                (cmp_dir / "mode_comparison_report.md").write_text(
                    format_comparison_md(cmp), encoding="utf-8"
                )
                logger.info(f"[COMPARE] 对比报告已保存: {cmp_dir}/mode_comparison_report.md")
            except Exception as e:
                logger.info(f"[!] 对比报告生成失败（非致命）: {e}")
        else:
            logger.warning("[!] 缺少标准或 DSPy 报告文件，跳过对比")
    rc = run_step("⑨ 文件归档", "organize_local_files", pid_arg, ts_env)
    if rc != 0:
        logger.error("[!] organize_local_files 失败（非致命，完成）")
    if args.skip_fhir:
        logger.warning("\n[跳过] FHIR 输出（--skip-fhir）")
    else:
        rc = run_step("⑨b FHIR 输出", "fhir_exporter", pid_arg, ts_env)
        if rc != 0:
            logger.error("[!] fhir_exporter 失败（非致命，继续）")
    if args.skip_cleanup:
        logger.warning("\n[跳过] 旧产物清理（--skip-cleanup）")
    else:
        logger.info(f"\n⑩ 旧产物清理（保留最近 {args.keep_last} 次）")
        try:
            from lab_analysis.cleanup_runs import cleanup_all, print_summary

            clean_results = cleanup_all(keep_last=args.keep_last, dry_run=False, id_card=deid)
            print_summary(clean_results)
        except Exception as e:
            logger.info(f"  [!] 产物清理失败（非致命）: {e}")
    logger.info(f"\n[{datetime.now().isoformat()}] Pipeline 完成")
    logger.info(f"\n输出目录：{ctx.data_dir}/")
    if ctx.data_dir.exists():
        for f in sorted(ctx.data_dir.iterdir()):
            logger.info(f"  - {f.name}")
