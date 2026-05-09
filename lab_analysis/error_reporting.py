"""
error_reporting.py — 统一错误上报：Sentry（可选）+ 本地 error.log。

启用 Sentry 只需设置环境变量 SENTRY_DSN。
不设置 SENTRY_DSN 时自动降级为本地文件日志。
"""
from __future__ import annotations

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Sentry ────────────────────────────────────────────────────────────────────

_sentry_installed: bool = False
_sentry_sdk: Optional[object] = None

try:
    import sentry_sdk
    from sentry_sdk import capture_exception
    _sentry_installed = True
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]
    capture_exception = None  # type: ignore[assignment]


def _init_sentry() -> bool:
    """尝试验证 Sentry DSN 并初始化，成功返回 True。"""
    if not _sentry_installed:
        return False
    dsns = os.environ.get("SENTRY_DSN", "").strip()
    if not dsns:
        return False
    try:
        sentry_sdk.init(
            dsn=dsns,
            # 生产环境去掉 debug 输出
            debug=False,
            # 只抓未捕获异常（我们已经在各 except 块主动上报）
            default_integrations=False,
            # 可添加 release / environment / tags
            environment=os.environ.get("RUN_ENV", "development"),
        )
        return True
    except Exception:
        return False


_sentry_active: bool = _init_sentry()

# ── 本地 error.log ────────────────────────────────────────────────────────────

ERROR_LOG_PATH: Optional[Path] = None


def _get_error_log_path() -> Path:
    """懒加载 error.log 路径（避免模块加载时 WORK_ROOT 尚未初始化）。"""
    global ERROR_LOG_PATH
    if ERROR_LOG_PATH is None:
        from .config import WORK_ROOT
        ERROR_LOG_PATH = WORK_ROOT / "logs" / "error.log"
        ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    return ERROR_LOG_PATH


def _json_safe(obj):
    """把不可 JSON 序列化的对象转成字符串。"""
    if isinstance(obj, (Path,)):
        return str(obj)
    if hasattr(obj, "__dict__"):
        return str(obj)
    return obj


def _log_to_file(
    level: str,
    error_type: str,
    message: str,
    context: Optional[dict] = None,
    exc_info: Optional[tuple] = None,
) -> None:
    """将错误详情写入 error.log（JSON Lines 格式）。"""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "error_type": error_type,
        "message": message,
        "context": {k: _json_safe(v) for k, v in (context or {}).items()},
    }
    if exc_info and exc_info[0]:
        entry["exc_type"] = exc_info[0].__name__ if exc_info[0] else None
        entry["exc_value"] = str(exc_info[1]) if exc_info[1] else None
        entry["tb"] = traceback.format_exception(*exc_info) if exc_info else None

    log_path = _get_error_log_path()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # 写入失败不崩溃，静默丢弃
        pass


# ── 公开 API ──────────────────────────────────────────────────────────────────

class ErrorContext:
    """
    错误上下文收集器。在 except 块中创建并填充，
    结束时调用 .report() 一次性上报。

    用法：
        try:
            ...
        except Exception as e:
            ErrorContext("步骤描述", {"patient_id": pid, "step": 3}).report(e)

    Attributes:
        step_name: 出错步骤名称
        context: 附加上下文字典（会在日志/Sentry 中展示）
    """

    __slots__ = ("step_name", "context", "_exc_info")

    def __init__(self, step_name: str, context: Optional[dict] = None):
        self.step_name: str = step_name
        self.context: dict = context or {}
        self._exc_info: sys.exc_info = (None, None, None)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self._exc_info = (exc_type, exc_val, exc_tb)
            self.report(exc_val)
        return False  # 不吞掉异常

    def report(self, exc: BaseException) -> None:
        """
        上报异常：同时写 error.log + 发送给 Sentry（若已配置）。
        """
        exc_type = type(exc).__name__
        message = str(exc) or exc_type

        # 1. error.log（始终写入，失败无害）
        _log_to_file(
            level="ERROR",
            error_type=exc_type,
            message=f"[{self.step_name}] {message}",
            context={"step": self.step_name, **self.context},
            exc_info=self._exc_info or (type(exc), exc, exc.__traceback__),
        )

        # 2. Sentry（配置了 DSN 才发，失败也无害）
        if _sentry_active and capture_exception:
            try:
                capture_exception(exc, context={"step": self.step_name, **self.context})
            except Exception:
                pass

        # 3. 同时打一份到 stderr，方便在终端即时看到
        print(f"❗ [{self.step_name}] {exc_type}: {message}", file=sys.stderr)
        if self.context:
            for k, v in self.context.items():
                print(f"   {k} = {v}", file=sys.stderr)


# ── 便捷单次上报 ──────────────────────────────────────────────────────────────

def report_error(
    step_name: str,
    exc: BaseException,
    context: Optional[dict] = None,
) -> None:
    """
    一次性错误上报（pipeline 中各 except 块的快捷调用）。

    等价于：
        ErrorContext(step_name, context).report(exc)
    """
    ErrorContext(step_name, context).report(exc)
