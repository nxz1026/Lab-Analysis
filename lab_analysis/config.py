"""config.py — 集中配置管理。"""

from __future__ import annotations

import os
from pathlib import Path

# WORK_ROOT 同时决定两件事: data/ 产物根目录, 以及脱敏主密钥 .hermes/master.key
# (见 patient_id._KEY_FILE, 缺失时会自动新建)。
# 因此不能默认 Path.cwd(): pip install 后的 `lab-analysis` 命令会从用户任意目录启动,
# 同一份代码在不同 cwd 下会解析出两个 data/ 树和两个互不可解密的 master key,
# 使同一患者得到两个不同的 deid。默认改为项目根目录 (含 pyproject.toml), 环境变量仍优先。
# 注意: config 被 utils 导入, 不能 import utils (循环), 故直接用 pathlib 计算。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORK_ROOT = Path(os.environ.get("WORK_ROOT") or _PROJECT_ROOT).resolve()

# ── 目录命名常量 ──────────────────────────────────────────────────────
DIR_DATA = "data"
DIR_ANALYZED = "02_analyzed"
DIR_LITERATURE = "03_literature"
DIR_REPORTS = "04_reports"
DIR_IMAGING = "05_imaging"
DIR_RAW = "raw"


def get(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()
