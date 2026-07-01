"""config.py — 集中配置管理。"""

from __future__ import annotations

import os
from pathlib import Path

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd())).resolve()

# ── 目录命名常量 ──────────────────────────────────────────────────────
DIR_DATA = "data"
DIR_ANALYZED = "02_analyzed"
DIR_LITERATURE = "03_literature"
DIR_REPORTS = "04_reports"
DIR_IMAGING = "05_imaging"
DIR_RAW = "raw"


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()
