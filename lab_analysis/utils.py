#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
utils.py - 通用工具函数

提供项目中多个模块共享的工具函数，包括：
- 路径构建
- 环境变量管理
- 日志功能
- 身份证号验证
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

try:
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
        before_log,
        after_log,
    )
    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

# 工作区根目录
WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))


def is_windows() -> bool:
    """检测当前操作系统是否为 Windows"""
    return sys.platform == "win32"


def fix_console_encoding():
    """
    修复 Windows 控制台编码，确保中文正常输出。

    Windows 默认控制台编码为 GBK（代码页 936），Python 3.7+ 提供
    ``reconfigure(encoding='utf-8')`` 方法安全地更改编码，无需替换流对象。
    在 Linux/macOS 上无操作。
    """
    if not is_windows():
        return
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def build_paths(patient_id: str) -> dict:
    """
    根据 patient_id 和 ANALYSIS_TS 环境变量构建路径字典
    
    Args:
        patient_id: 患者ID（脱敏后）
    
    Returns:
        包含各种路径的字典
    """
    raw_ts = os.environ.get("ANALYSIS_TS", patient_id)
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts
    
    data_dir = WORK_ROOT / "data" / patient_id / ts
    
    return {
        "data_dir": data_dir,
        "patient_id": patient_id,
        "timestamp": ts,
        "raw_papers": WORK_ROOT / "raw" / f"patient_{patient_id}" / "papers",
        "raw_lab": WORK_ROOT / "raw" / f"patient_{patient_id}" / "lab",
        "raw_imaging": WORK_ROOT / "raw" / f"patient_{patient_id}" / "imaging",
        "output_dir": data_dir,
        "analyzed_dir": data_dir / "02_analyzed",  # 添加 analyzed_dir
    }


def get_project_root() -> Path:
    """获取项目根目录（包含 pyproject.toml）"""
    return Path(__file__).resolve().parent.parent


def get_env_var(name: str, default=None, required: bool = False):
    """
    获取环境变量
    
    Args:
        name: 环境变量名
        default: 默认值
        required: 是否必需，如果为True且变量不存在则抛出异常
    
    Returns:
        环境变量值
    """
    value = os.environ.get(name, default)
    if required and value is None:
        raise EnvironmentError(f"必需的环境变量 {name} 未设置")
    return value


def validate_chinese_id(id_number: str) -> bool:
    """
    验证中国大陆身份证号格式
    
    Args:
        id_number: 身份证号
    
    Returns:
        是否有效
    """
    if not id_number:
        return False
    
    # 18位身份证：17位数字 + 1位数字或X
    pattern_18 = r'^\d{17}[\dXx]$'
    # 15位身份证：15位数字
    pattern_15 = r'^\d{15}$'
    
    return bool(re.match(pattern_18, id_number) or re.match(pattern_15, id_number))


def parse_metadata_table(text: str) -> dict:
    """
    解析 Markdown 表格格式的 metadata（| 字段 | 值 |）
    
    Args:
        text: metadata 文本
    
    Returns:
        解析后的字典
    """
    row = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line or line.startswith("|字段"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3 and parts[1]:
            key = parts[1].strip()
            val = parts[2].strip()
            if key:
                row[key] = val
    return row


def append_to_json_log(log_file: Path, record: dict):
    """
    追加记录到JSON日志文件
    
    Args:
        log_file: 日志文件路径
        record: 要追加的记录
    """
    if log_file.exists():
        log = json.loads(log_file.read_text(encoding="utf-8"))
    else:
        log = {"records": []}
    
    log["records"].append(record)
    log["last_updated"] = datetime.now().isoformat()
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def print_progress(current: int, total: int, prefix: str = "", suffix: str = "", bar_length: int = 30):
    """
    打印进度条
    
    Args:
        current: 当前进度
        total: 总数量
        prefix: 前缀文本
        suffix: 后缀文本
        bar_length: 进度条长度
    """
    if total == 0:
        return
    fraction = current / total
    filled = int(bar_length * fraction)
    bar = "=" * filled + "-" * (bar_length - filled)
    percent = f"{fraction * 100:.1f}%"
    print(f"\r{prefix} |{bar}| {percent} {suffix}", end="", flush=True)
    if current >= total:
        print()


def ensure_dirs(*dirs: Path):
    """
    确保目录存在，不存在则创建
    
    Args:
        dirs: 目录路径列表
    """
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def api_retry_decorator(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_on_exceptions: tuple = (Exception,),
    description: str = "API调用"
):
    """
    API 重试装饰器 - 使用指数退避策略
    
    Args:
        max_attempts: 最大重试次数（包括首次尝试）
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）
        retry_on_exceptions: 需要重试的异常类型元组
        description: API 描述（用于日志）
    
    Returns:
        装饰器函数
    
    Example:
        @api_retry_decorator(max_attempts=3, description="智谱AI")
        def call_zhipu_api(...):
            ...
    """
    if not HAS_TENACITY:
        # 如果 tenacity 未安装，返回原函数
        def dummy_decorator(func):
            return func
        return dummy_decorator
    
    def decorator(func: Callable) -> Callable:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_on_exceptions),
            reraise=True,
        )(func)
    
    return decorator