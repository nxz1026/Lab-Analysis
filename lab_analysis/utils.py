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

from . import _log
from .retry import HAS_TENACITY, api_retry_decorator

logger = _log.get_logger(__name__)
WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd())).resolve()


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
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
        pass


def build_paths(patient_id: str, timestamp: str | None = None) -> dict:
    """
    根据 patient_id 和可选 timestamp 构建路径字典。

    Args:
        patient_id: 患者ID（脱敏后）
        timestamp: 时间戳（如 20260620_150000）。
                   None 时从 ANALYSIS_TS 环境变量读取（向后兼容）。

    Returns:
         包含各种路径的字典
    """
    if timestamp is None:
        raw_ts = os.environ.get("ANALYSIS_TS", patient_id)
        ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts
    else:
        ts = timestamp
    data_dir = WORK_ROOT / "data" / patient_id / ts
    return {
        "data_dir": data_dir,
        "patient_id": patient_id,
        "timestamp": ts,
        "raw_papers": WORK_ROOT / "raw" / f"patient_{patient_id}" / "papers",
        "raw_lab": WORK_ROOT / "raw" / f"patient_{patient_id}" / "lab",
        "raw_imaging": WORK_ROOT / "raw" / f"patient_{patient_id}" / "imaging",
        "output_dir": data_dir,
        "analyzed_dir": data_dir / "02_analyzed",
    }


def get_project_root() -> Path:
    """获取项目根目录（包含 pyproject.toml）"""
    return Path(__file__).resolve().parent.parent


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
    pattern_18 = "^\\d{17}[\\dXx]$"
    pattern_15 = "^\\d{15}$"
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


def append_to_json_log(log_file: Path, record: dict, root_key: str = "records") -> None:
    log = json.loads(log_file.read_text(encoding="utf-8")) if log_file.exists() else {root_key: []}
    log[root_key].append(record)
    log["last_updated"] = datetime.now().isoformat()
    log_file.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def print_progress(
    current: int, total: int, prefix: str = "", suffix: str = "", bar_length: int = 30
):
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
    # print() 不用 logger 以保留 \r 与 stdout 直接交互
    print(f"\r{prefix} |{bar}| {percent} {suffix}", end="", flush=True)
    if current >= total:
        print()
