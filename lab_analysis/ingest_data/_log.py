"""ingest_data._log — 摄入日志持久化 + 模块级 logger。"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from ..utils import WORK_ROOT, append_to_json_log

INGEST_LOG = WORK_ROOT / ".ingest_log.json"
LOG_FILE = WORK_ROOT / ".ingest_debug.log"

logger = logging.getLogger("ingest_data")
logger.setLevel(logging.DEBUG)


def _ensure_handlers() -> None:
    """P1-2: 懒加载 FileHandler/StreamHandler, 避免 import 期占用 .ingest_debug.log.

    重试创建可能被并发 pytest 占用的日志文件; 争用时降级为控制台-only.
    """
    if logger.handlers:
        return
    # Console handler (always)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (best-effort)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except OSError as e:
        # 文件被其他进程占用, 控制台足够。
        logger.debug("ingest_data FileHandler 跳过: %s", e)


def append_log(record: dict) -> None:
    """追加摄入记录到日志。"""
    append_to_json_log(INGEST_LOG, record, root_key="ingested")
