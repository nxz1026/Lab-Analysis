"""
config.py — 统一配置管理，替换各模块分散的 env 加载逻辑。

所有模块统一从本模块导入配置，不再各自重复加载 .env。
"""
from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional

# ── dotenv 初始化（一次性）─────────────────────────────────────────

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass

# ── 路径配置 ────────────────────────────────────────────────────────

WORK_ROOT: Path = Path(os.environ.get("WORK_ROOT", Path.cwd()))
ORIGIN_DATA_DIR: Path = Path(os.environ.get("ORIGIN_DATA_DIR", WORK_ROOT / "raw"))

# ── API Keys ─────────────────────────────────────────────────────────

DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
DASHSCOPE_API_KEY: str = os.environ.get("DASHSCOPE_API_KEY", "")
ZHIPU_API_KEY:     str = os.environ.get("ZHIPU_API_KEY",     "")
TAVILY_API_KEY:    str = os.environ.get("TAVILY_API_KEY",    "")

# ── 患者信息（报告生成时由调用方通过环境变量注入）─────────────────

PATIENT_NAME:    str = os.environ.get("PATIENT_NAME",    "患者")
PATIENT_AGE_SEX: str = os.environ.get("PATIENT_AGE_SEX", "成年男性")
PATIENT_EXAM_ID: str = os.environ.get("PATIENT_EXAM_ID", "ANONYMIZED")

# ── 分析时间戳（pipeline 内部传递用）───────────────────────────────

ANALYSIS_TS: str = os.environ.get("ANALYSIS_TS", "")

# ── 辅助函数 ────────────────────────────────────────────────────────

def get_required_key(name: str) -> str:
    """读取必需的配置项，缺失则抛出 ValueError。"""
    val = os.environ.get(name, "").strip()
    if not val:
        raise ValueError(f"缺少必需的环境变量: {name}")
    return val

def get_optional_key(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()

@lru_cache(maxsize=1)
def get_wiki_root() -> Path:
    return WORK_ROOT