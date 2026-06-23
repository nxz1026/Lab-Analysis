"""DSPy 编译缓存命中率埋点。

使用方式 (在被埋点的模块内):

    from ._cache_metrics import record_hit, record_miss

    if compiled_model_path.exists():
        record_hit("lab_data_extractor")
        module.load(compiled_model_path)
    else:
        record_miss("lab_data_extractor")
        module = ModuleCls()

数据落盘到 `logs/dspy_cache_metrics.json` 以便跨进程累计。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

_METRICS_FILE = Path(os.environ.get("DSPY_CACHE_METRICS_FILE", "logs/dspy_cache_metrics.json"))

# 模块级锁 + 文件锁替代品 (简单原子写入足够)
_lock = threading.Lock()

# 内存缓存 (避免每次都读盘)
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if _METRICS_FILE.is_file():
        try:
            _cache = json.loads(_METRICS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _cache = _empty()
    else:
        _cache = _empty()
    return _cache


def _empty() -> dict:
    return {"modules": {}, "totals": {"hit": 0, "miss": 0, "load_fail": 0}}


def _flush() -> None:
    if _cache is None:
        return
    _METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _METRICS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_METRICS_FILE)


def _bump(module: str, key: str) -> None:
    with _lock:
        data = _load()
        m = data["modules"].setdefault(module, {"hit": 0, "miss": 0, "load_fail": 0})
        m[key] += 1
        data["totals"][key] += 1
        _flush()


def record_hit(module: str) -> None:
    """Cache hit: compiled .json exists AND load() succeeded."""
    _bump(module, "hit")


def record_miss(module: str) -> None:
    """Cache miss: compiled .json does not exist."""
    _bump(module, "miss")


def record_load_fail(module: str) -> None:
    """Cache file exists but load() raised — treated separately."""
    _bump(module, "load_fail")


def get_stats() -> dict:
    """Return a snapshot of current metrics (read-only copy)."""
    with _lock:
        data = _load()
        return json.loads(json.dumps(data))


def reset() -> None:
    """Clear the in-memory cache and delete the on-disk file."""
    global _cache
    with _lock:
        _cache = _empty()
        if _METRICS_FILE.is_file():
            _METRICS_FILE.unlink()
