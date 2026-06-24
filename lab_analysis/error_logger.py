"""
error_logger.py - 错误日志记录模块

提供统一的错误日志记录功能，便于问题追溯和调试。

用法：
    from lab_analysis.error_logger import log_error, log_warning

    try:
        # 可能出错的代码
        result = some_api_call()
    except Exception as e:
        log_error("API调用失败", exc_info=e, context={"api": "deepseek"})
"""

from __future__ import annotations

import logging
import os
import re
import sys
import traceback
from collections import deque
from pathlib import Path
from typing import Any

from . import _log
from .utils import WORK_ROOT

logger = _log.get_logger(__name__)
ERROR_LOG_FILE = WORK_ROOT / "error.log"


def _init_error_logger(log_file: Path | None = None) -> logging.Logger:
    elog = logging.getLogger("lab_analysis_error")
    elog.setLevel(logging.WARNING)
    if log_file is None:
        log_file = ERROR_LOG_FILE
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    _log.add_file_handler(elog, log_file, level=logging.WARNING, formatter=formatter)
    if os.environ.get("DEBUG_ERROR_LOG", "0") == "1":
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.ERROR)
        console_handler.setFormatter(formatter)
        elog.addHandler(console_handler)
    return elog


def setup_error_logger(log_file: Path | None = None) -> logging.Logger:
    return _init_error_logger(log_file)


def log_error(
    message: str,
    exc_info: Exception | None = None,
    context: dict[str, Any] | None = None,
    module: str = "unknown",
):
    """
    记录错误日志

    Args:
        message: 错误描述信息
        exc_info: 异常对象（可选）
        context: 上下文信息字典（可选）
        module: 模块名称

    Example:
        >>> log_error("API调用失败", exc_info=e, context={"api": "deepseek", "patient_id": "123"})
    """
    logger = setup_error_logger()
    error_details = [f"[{module}] {message}"]
    if context:
        context_str = ", ".join((f"{k}={v}" for k, v in context.items()))
        context_str = re.sub(r"\b\d{17}[\dXx]\b", "[REDACTED_ID]", context_str)
        error_details.append(f"Context: {context_str}")
    if exc_info:
        error_details.append(f"Exception: {type(exc_info).__name__}: {str(exc_info)}")
        tb_str = "".join(
            traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__)
        )
        error_details.append(f"Traceback:\n{tb_str}")
    full_message = "\n".join(error_details)
    logger.error(full_message)
    logger.info(f"\n[FAIL] [ERROR] {message}")
    if exc_info:
        logger.info(f"   {type(exc_info).__name__}: {exc_info}")


def log_warning(message: str, context: dict[str, Any] | None = None, module: str = "unknown"):
    """
    记录警告日志

    Args:
        message: 警告描述信息
        context: 上下文信息字典（可选）
        module: 模块名称
    """
    logger = setup_error_logger()
    warning_details = [f"[{module}] [WARNING] {message}"]
    if context:
        context_str = ", ".join((f"{k}={v}" for k, v in context.items()))
        warning_details.append(f"Context: {context_str}")
    full_message = "\n".join(warning_details)
    logger.warning(full_message)
    logger.info(f"\n[WARN]  [WARNING] {message}")


def log_pipeline_error(
    step_name: str,
    patient_id: str,
    exc_info: Exception,
    additional_context: dict[str, Any] | None = None,
):
    """
    记录 Pipeline 步骤错误（专用函数）

    Args:
        step_name: Pipeline 步骤名称
        patient_id: 患者ID
        exc_info: 异常对象
        additional_context: 额外上下文信息
    """
    context = {"step": step_name, "patient_id": patient_id}
    if additional_context:
        context.update(additional_context)
    log_error(
        message=f"Pipeline 步骤 '{step_name}' 执行失败",
        exc_info=exc_info,
        context=context,
        module="pipeline",
    )


def get_recent_errors(n: int = 100) -> list:
    """
    获取最近的 N 条错误日志

    Args:
        n: 返回的错误数量，默认 100

    Returns:
        错误日志行列表
    """
    if not ERROR_LOG_FILE.exists():
        return []
    try:
        result = deque(maxlen=n)
        with open(ERROR_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                result.append(line.rstrip("\n").rstrip("\r"))
        return list(result)
    except Exception:
        return []


def clear_error_log():
    """清空错误日志文件"""
    if ERROR_LOG_FILE.exists():
        ERROR_LOG_FILE.write_text("", encoding="utf-8")
        logger.info(f"[OK] 已清空错误日志: {ERROR_LOG_FILE}")
