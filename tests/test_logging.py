"""tests.test_logging — 统一日志接口单测。

覆盖:
- _log.configure 幂等性
- LOG_LEVEL / LOG_FORMAT / LOG_DATEFMT 环境变量
- get_logger 返回带正确名字的 logger
- add_file_handler 写盘与格式同步
- remove_handler 清理
- JsonFormatter 结构化输出
"""

from __future__ import annotations

import json
import logging

import pytest

from lab_analysis import _log


@pytest.fixture(autouse=True)
def _reset_log_env(monkeypatch):
    """每个测试都重置 _CONFIGURED 与环境变量, 避免测试间互相污染。"""
    for key in ("LOG_LEVEL", "LOG_FORMAT", "LOG_DATEFMT"):
        monkeypatch.delenv(key, raising=False)
    _log.reset()
    # 清除上一个测试可能挂在 root 上的 handler, 让 basicConfig 能重新生效
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()
    yield
    _log.reset()
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()


def test_configure_is_idempotent():
    _log.configure("INFO")
    handler_count_first = len(logging.getLogger().handlers)
    _log.configure("DEBUG")  # 二次调用不应再加 handler
    handler_count_second = len(logging.getLogger().handlers)
    assert handler_count_first == handler_count_second


def test_get_logger_returns_named_logger():
    log = _log.get_logger("my.module")
    assert isinstance(log, logging.Logger)
    assert log.name == "my.module"


def test_log_level_from_env(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    _log.configure()
    assert logging.getLogger().level == logging.DEBUG


def test_log_format_from_env(monkeypatch, tmp_path):
    """LOG_FORMAT 通过 add_file_handler 的默认 formatter 应用。

    跳过 root logger basicConfig 的格式检查 — pytest caplog 会装自己的 handler,
    让 root handler 测试不稳定。add_file_handler 走 _resolve_format, 是 production 路径。
    """
    custom = "%(levelname)s|%(name)s|%(message)s"
    monkeypatch.setenv("LOG_FORMAT", custom)
    log = _log.get_logger("test.format_env")
    log_file = tmp_path / "fmt.log"
    handler = _log.add_file_handler(log, log_file)
    try:
        log.info("ping")
    finally:
        _log.remove_handler(log, handler)
    # 验证 _resolve_format 能读到 env 变量
    fmt, _ = _log._resolve_format()
    assert fmt == custom
    # 验证实际写出的内容用 custom 格式: 含 "INFO|test.format_env|ping"
    text = log_file.read_text(encoding="utf-8")
    assert "INFO|test.format_env|ping" in text


def test_log_datefmt_from_env(monkeypatch):
    monkeypatch.setenv("LOG_DATEFMT", "%H:%M:%S")
    _log.configure()
    root = logging.getLogger()
    handler = next(h for h in root.handlers if hasattr(h, "stream"))
    assert handler.formatter.datefmt == "%H:%M:%S"  # type: ignore[attr-defined]


def test_add_file_handler_writes_to_disk(tmp_path, caplog):
    log = _log.get_logger("test.file_handler")
    log_file = tmp_path / "subdir" / "out.log"  # 父目录不存在, 应自动创建
    handler = _log.add_file_handler(log, log_file)
    try:
        log.info("hello world")
        log.error("oops")
    finally:
        _log.remove_handler(log, handler)
    assert log_file.is_file()
    text = log_file.read_text(encoding="utf-8")
    assert "hello world" in text
    assert "oops" in text
    # 默认 format 含时间戳 + level + name + message
    assert "[INFO]" in text
    assert "[ERROR]" in text
    assert "test.file_handler" in text


def test_add_file_handler_with_custom_formatter(tmp_path):
    log = _log.get_logger("test.custom_fmt")
    log_file = tmp_path / "audit.log"
    formatter = _log.JsonFormatter()
    handler = _log.add_file_handler(log, log_file, formatter=formatter)
    try:
        log.warning("structured message")
    finally:
        _log.remove_handler(log, handler)
    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    obj = json.loads(lines[0])
    assert obj["level"] == "WARNING"
    assert obj["logger"] == "test.custom_fmt"
    assert obj["message"] == "structured message"
    assert "ts" in obj
    assert "lineno" in obj


def test_remove_handler_cleans_up(tmp_path):
    log = _log.get_logger("test.remove")
    log_file = tmp_path / "remove.log"
    handler = _log.add_file_handler(log, log_file)
    assert handler in log.handlers
    _log.remove_handler(log, handler)
    assert handler not in log.handlers


def test_add_file_handler_respects_level(tmp_path):
    log = _log.get_logger("test.level")
    log_file = tmp_path / "leveled.log"
    handler = _log.add_file_handler(log, log_file, level="ERROR")
    try:
        log.info("should NOT appear")
        log.error("should appear")
    finally:
        _log.remove_handler(log, handler)
    text = log_file.read_text(encoding="utf-8")
    assert "should NOT appear" not in text
    assert "should appear" in text


class TestJsonFormatter:
    def test_basic_fields(self):
        formatter = _log.JsonFormatter()
        record = logging.LogRecord(
            name="x.y",
            level=logging.INFO,
            pathname="/tmp/x.py",
            lineno=42,
            msg="hello",
            args=(),
            exc_info=None,
        )
        line = formatter.format(record)
        obj = json.loads(line)
        assert obj["level"] == "INFO"
        assert obj["logger"] == "x.y"
        assert obj["message"] == "hello"
        assert obj["lineno"] == 42

    def test_unicode_message_round_trip(self):
        formatter = _log.JsonFormatter()
        record = logging.LogRecord(
            name="x",
            level=logging.WARNING,
            pathname="/tmp/x.py",
            lineno=1,
            msg="中文 + emoji = ok",
            args=(),
            exc_info=None,
        )
        line = formatter.format(record)
        obj = json.loads(line)
        assert obj["message"] == "中文 + emoji = ok"

    def test_exc_info_serialized(self):
        formatter = _log.JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError as e:
            record = logging.LogRecord(
                name="x",
                level=logging.ERROR,
                pathname="/tmp/x.py",
                lineno=1,
                msg="failed",
                args=(),
                exc_info=(type(e), e, e.__traceback__),
            )
        line = formatter.format(record)
        obj = json.loads(line)
        assert "exc_info" in obj
        assert "ValueError: boom" in obj["exc_info"]