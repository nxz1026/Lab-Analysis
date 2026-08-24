"""config.py — 集中配置管理。"""

from __future__ import annotations

import os
from pathlib import Path

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd())).resolve()


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()
