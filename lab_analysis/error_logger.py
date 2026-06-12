#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# 工作区根目录
WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))

# 错误日志文件路径
ERROR_LOG_FILE = WORK_ROOT / "error.log"


def setup_error_logger(log_file: Optional[Path] = None) -> logging.Logger:
    """
    配置错误日志记录器
    
    Args:
        log_file: 日志文件路径，默认为 WORK_ROOT/error.log
    
    Returns:
        配置好的 logger 实例
    """
    if log_file is None:
        log_file = ERROR_LOG_FILE
    
    # 确保日志目录存在
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 创建 logger
    logger = logging.getLogger("lab_analysis_error")
    logger.setLevel(logging.ERROR)
    
    # 避免重复添加 handler
    if not logger.handlers:
        # 文件 handler
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.ERROR)
        
        # 格式化器
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        
        # 控制台 handler（可选，用于调试）
        if os.environ.get("DEBUG_ERROR_LOG", "0") == "1":
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.ERROR)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
    
    return logger


def log_error(
    message: str,
    exc_info: Optional[Exception] = None,
    context: Optional[Dict[str, Any]] = None,
    module: str = "unknown"
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
    
    # 构建详细错误信息
    error_details = [f"[{module}] {message}"]
    
    # 添加上下文信息
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        error_details.append(f"Context: {context_str}")
    
    # 添加异常信息
    if exc_info:
        error_details.append(f"Exception: {type(exc_info).__name__}: {str(exc_info)}")
        # 添加堆栈跟踪
        tb_str = "".join(traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__))
        error_details.append(f"Traceback:\n{tb_str}")
    
    # 记录日志
    full_message = "\n".join(error_details)
    logger.error(full_message)
    
    # 同时打印到控制台（便于即时发现）
    print(f"\n[FAIL] [ERROR] {message}", file=sys.stderr)
    if exc_info:
        print(f"   {type(exc_info).__name__}: {exc_info}", file=sys.stderr)


def log_warning(
    message: str,
    context: Optional[Dict[str, Any]] = None,
    module: str = "unknown"
):
    """
    记录警告日志
    
    Args:
        message: 警告描述信息
        context: 上下文信息字典（可选）
        module: 模块名称
    """
    logger = setup_error_logger()
    
    # 构建详细信息
    warning_details = [f"[{module}] [WARNING] {message}"]
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        warning_details.append(f"Context: {context_str}")
    
    full_message = "\n".join(warning_details)
    logger.warning(full_message)
    
    # 打印到控制台
    print(f"\n[WARN]  [WARNING] {message}", file=sys.stderr)


def log_pipeline_error(
    step_name: str,
    patient_id: str,
    exc_info: Exception,
    additional_context: Optional[Dict[str, Any]] = None
):
    """
    记录 Pipeline 步骤错误（专用函数）
    
    Args:
        step_name: Pipeline 步骤名称
        patient_id: 患者ID
        exc_info: 异常对象
        additional_context: 额外上下文信息
    """
    context = {
        "step": step_name,
        "patient_id": patient_id,
    }
    if additional_context:
        context.update(additional_context)
    
    log_error(
        message=f"Pipeline 步骤 '{step_name}' 执行失败",
        exc_info=exc_info,
        context=context,
        module="pipeline"
    )


def get_recent_errors(n: int = 10) -> list:
    """
    获取最近的 N 条错误日志
    
    Args:
        n: 返回的错误数量
    
    Returns:
        错误日志行列表
    """
    if not ERROR_LOG_FILE.exists():
        return []
    
    try:
        with open(ERROR_LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return lines[-n:]
    except Exception:
        return []


def clear_error_log():
    """清空错误日志文件"""
    if ERROR_LOG_FILE.exists():
        ERROR_LOG_FILE.write_text("", encoding="utf-8")
        print(f"[OK] 已清空错误日志: {ERROR_LOG_FILE}")
