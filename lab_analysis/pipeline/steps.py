"""lab_analysis.pipeline.steps — Pipeline 子步骤 (检查 / 启动子进程 / 装饰器)。

装饰器 API:

    from lab_analysis.pipeline.steps import pipeline_step

    @pipeline_step(name="③ 数据加载", fatal=True)
    def run_data_loader(ctx: PipelineContext) -> int:
        # 启动子进程, 返回 rc
        ...

in-process 步骤 (无需子进程) 也可用:

    @pipeline_step(name="② 前置检查", fatal=True)
    def check_patient_data_step(ctx: PipelineContext) -> bool:
        # 返回 True=OK, False=fatal
        ...
"""

from __future__ import annotations

import functools
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from lab_analysis.error_logger import log_error, log_pipeline_error
from lab_analysis.utils import WORK_ROOT

from .. import _log

logger = _log.get_logger(__name__)


def extract_patient_id_from_reports() -> str | None:
    """从已摄入的检验报告 metadata.md 中提取身份证号。"""
    raw_dir = WORK_ROOT / "raw"
    if not raw_dir.exists():
        return None
    for patient_dir in raw_dir.iterdir():
        if not (patient_dir.is_dir() and patient_dir.name.startswith("patient_")):
            continue
        papers_dir = patient_dir / "papers"
        if not papers_dir.exists():
            continue
        for report_dir in sorted(papers_dir.glob("lab_report_*")):
            if not report_dir.is_dir():
                continue
            meta_path = report_dir / "metadata.md"
            if not meta_path.exists():
                continue
            for line in meta_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("|") and ("身份证号" in line or "患者ID" in line):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 3 and parts[2]:
                        id_card = parts[2]
                        from lab_analysis.pipeline.cli import get_deid

                        logger.info(
                            f"[INFO] 从检验报告中提取到身份证号（已脱敏）: {get_deid(id_card)}"
                        )
                        _ret = id_card
                        del id_card
                        return _ret
    return None


def check_patient_data(deid: str) -> bool:
    """检查病人原始数据目录是否存在且有内容。"""
    raw_dir = WORK_ROOT / "raw" / f"patient_{deid}"
    lab_dir = raw_dir / "lab"
    imaging_dir = raw_dir / "imaging"
    papers_dir = raw_dir / "papers"
    errors, warnings = ([], [])
    if not raw_dir.exists():
        errors.append(f"  [ERROR] 病人目录不存在: {raw_dir}")
    else:
        has_lab = lab_dir.exists() and any(lab_dir.iterdir())
        has_papers = papers_dir.exists() and any(papers_dir.iterdir())
        has_imaging = imaging_dir.exists() and any(imaging_dir.iterdir())
        if not has_lab and (not has_papers):
            errors.append(f"  [ERROR] 未找到检验报告: {lab_dir} 或 {papers_dir}")
        if not has_imaging:
            warnings.append(f"  [WARNING] 未找到影像数据: {imaging_dir}（将跳过影像分析）")
    if errors:
        logger.info("\n".join(errors))
        if warnings:
            logger.info("\n".join(warnings))
        logger.info(f"\n当前 {WORK_ROOT / 'raw'} 下的病人目录：")
        raw_parent = WORK_ROOT / "raw"
        if raw_parent.exists():
            for d in sorted(raw_parent.iterdir()):
                if d.is_dir():
                    logger.info(f"  - {d.name}")
        else:
            logger.info("  （raw 目录为空或不存在）")
        return False
    if warnings:
        logger.info("\n".join(warnings))
    return True


def pick_python_exe() -> str:
    """优先使用项目 .venv 中的 Python；否则当前解释器。"""
    win_venv = WORK_ROOT / ".venv" / "Scripts" / "python.exe"
    unix_venv = WORK_ROOT / ".venv" / "bin" / "python"
    if win_venv.is_file():
        return str(win_venv)
    if unix_venv.is_file():
        return str(unix_venv)
    return sys.executable


def run_step(
    name: str,
    module: str,
    extra_args: list[str] | None = None,
    env: dict | None = None,
    *,
    fatal: bool = True,
    timeout: int | None = None,
) -> int:
    """以 python -m lab_analysis.<module> 运行单步。

    Args:
        name: 步骤名称 (打印用)
        module: lab_analysis 子模块名 (如 ``data_loader``)
        extra_args: 传给子模块的命令行参数
        env: 额外环境变量, 合并到 os.environ
        fatal: True (默认) → 失败时 sys.exit(1); False → 仅 log error, 返回非零 rc
        timeout: 子进程超时秒数. None (默认) → 从 PIPELINE_STEP_TIMEOUT env 读, 默认 1800s.
                 P1-5: 避免 LLM/OCR/DICOM 遇服务端 hang 时永久挂死.

    Returns:
        subprocess returncode
    """
    root = Path(__file__).resolve().parent.parent.parent
    python = pick_python_exe()
    cmd = [python, "-m", f"lab_analysis.{module}"]
    if extra_args:
        cmd.extend(extra_args)
    if timeout is None:
        try:
            timeout = int(os.environ.get("PIPELINE_STEP_TIMEOUT", "1800"))
        except ValueError:
            timeout = 1800
    logger.info(f"\n{'=' * 60}\n[STEP] {name}\n命令: {' '.join(cmd)}\ntimeout: {timeout}s\n{'=' * 60}")
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    pp = str(root)
    full_env["PYTHONPATH"] = pp + os.pathsep + full_env.get("PYTHONPATH", "")
    start = time.monotonic()
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            cwd=str(root),
            env=full_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        # P1-5: 超时单独处理, 错误信息明确
        log_error(
            message=f"Pipeline 步骤 '{name}' 超时 (> {timeout}s)",
            exc_info=None,
            context={
                "module": module,
                "command": " ".join(cmd),
                "timeout_s": timeout,
                "elapsed_s": round(time.monotonic() - start, 2),
            },
            module="pipeline",
        )
        return _handle_failure(name, module, cmd, 124, elapsed=time.monotonic() - start, fatal=fatal)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        log_pipeline_error(
            step_name=name,
            patient_id=env.get("ANALYSIS_TS", "unknown") if env else "unknown",
            exc_info=e,
            additional_context={"module": module},
        )
        return _handle_failure(name, module, cmd, 1, elapsed=time.monotonic() - start, fatal=fatal)
    elapsed = time.monotonic() - start
    if result.returncode != 0:
        log_error(
            message=f"Pipeline 步骤 '{name}' 执行失败",
            exc_info=None,
            context={
                "module": module,
                "command": " ".join(cmd),
                "returncode": result.returncode,
                "error": (result.stderr or "Unknown error")[:500],
                "elapsed_s": round(elapsed, 2),
            },
            module="pipeline",
        )
        return _handle_failure(
            name, module, cmd, result.returncode, elapsed=elapsed, fatal=fatal
        )
    logger.info(f"[OK] {name} 完成 ({elapsed:.2f}s)")
    return 0


def _handle_failure(
    name: str,
    module: str,
    cmd: list[str],
    rc: int,
    *,
    elapsed: float,
    fatal: bool,
) -> int:
    """统一处理步骤失败: 致命则 sys.exit(1), 否则返回非零 rc。"""
    if fatal:
        logger.error(f"[!] {name} 失败 (rc={rc}, {elapsed:.2f}s), 终止 pipeline")
        raise SystemExit(1)
    logger.error(f"[!] {name} 失败 (rc={rc}, {elapsed:.2f}s), 标记非致命, 继续")
    return rc


# ---------------------------------------------------------------------------
# 装饰器: 包装 in-process 步骤 (不开子进程, 同步调用)
# ---------------------------------------------------------------------------
def pipeline_step(
    *,
    name: str,
    fatal: bool = True,
) -> Callable:
    """统一步骤装饰器: 打印 start / end / duration, 失败 fatal 时 sys.exit(1)。

    装饰的函数应当返回:
    - int      → 直接作为 rc
    - bool     → True = OK (rc=0), False = fatal 时 sys.exit(1), 否则 rc=1
    - None     → 视为 rc=0

    用法:
        @pipeline_step(name="② 前置检查", fatal=True)
        def check_step(ctx) -> bool:
            return ctx.is_valid()
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            logger.info(f"\n{'=' * 60}\n[STEP] {name}\n{'=' * 60}")
            start = time.monotonic()
            try:
                result = fn(*args, **kwargs)
            # P2-5: 用 except Exception 全捕获, 防止遗漏 AssertionError / IndexError / NotImplementedError 等
            # 不影响 fatal sys.exit 路径: SystemExit 是 BaseException, 不会被 except Exception 拦截
            except Exception as e:
                elapsed = time.monotonic() - start
                log_pipeline_error(
                    step_name=name,
                    patient_id=str(kwargs.get("ctx") or (args[0] if args else "unknown")),
                    exc_info=e,
                    additional_context={"fn": fn.__name__},
                )
                if fatal:
                    logger.error(f"[!] {name} 抛异常 ({elapsed:.2f}s), 终止 pipeline")
                    raise SystemExit(1)
                logger.error(f"[!] {name} 抛异常 ({elapsed:.2f}s), 标记非致命")
                return 1
            elapsed = time.monotonic() - start
            if result is None:
                rc = 0
            elif isinstance(result, bool):
                rc = 0 if result else 1
            elif isinstance(result, int):
                rc = result
            else:
                # P1-1: 对非预期类型 raise, 防止 dict/list/str 被静默判为成功
                raise TypeError(
                    f"{name} returned {type(result).__name__}, expected bool/int/None"
                )
            if rc == 0:
                logger.info(f"[OK] {name} 完成 ({elapsed:.2f}s)")
                return rc
            if fatal:
                logger.error(f"[!] {name} 失败 (rc={rc}, {elapsed:.2f}s), 终止 pipeline")
                raise SystemExit(1)
            logger.error(f"[!] {name} 失败 (rc={rc}, {elapsed:.2f}s), 标记非致命, 继续")
            return rc

        return wrapper

    return decorator