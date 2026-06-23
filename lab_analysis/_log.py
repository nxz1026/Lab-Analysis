"""统一 logger 配置。

全项目 print() 应统一改用 logging。等级:

- ERROR  → 阻断性错误(exit / 数据缺失 / 校验失败)
- WARNING → 可恢复 / 跳过的非致命问题(单条样本失败、缓存 miss)
- INFO    → 阶段进度、统计、关键节点
- DEBUG   → 详细中间状态(默认关闭,LOG_LEVEL=DEBUG 开启)

使用:
    from . import _log
    log = _log.get_logger(__name__)
    log.info("start")

格式定制 (环境变量):
    LOG_LEVEL   = DEBUG | INFO | WARNING | ERROR (默认 INFO)
    LOG_FORMAT  = 自定义 format 字符串 (默认见下方)
    LOG_DATEFMT = 自定义 datefmt (默认 "%Y-%m-%d %H:%M:%S")

落盘:
    handler = _log.add_file_handler(log, "logs/pipeline_xxx.log")
    log.info("...")   # 同时走 stderr + 文件

结构化 JSON:
    handler = _log.add_file_handler(log, "logs/audit.json", formatter=_log.JsonFormatter())
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

_CONFIGURED = False

# 默认格式: "<时间> [<LEVEL>] <logger名>: <消息>"
DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _resolve_level(level: str | int | None) -> int:
    if level is None:
        level = os.environ.get("LOG_LEVEL", "INFO").upper()
    if isinstance(level, str):
        return getattr(logging, level, logging.INFO)
    return level


def _resolve_format() -> tuple[str, str]:
    fmt = os.environ.get("LOG_FORMAT", DEFAULT_FORMAT)
    datefmt = os.environ.get("LOG_DATEFMT", DEFAULT_DATEFMT)
    return fmt, datefmt


class JsonFormatter(logging.Formatter):
    """结构化 JSON 输出, 用于审计 / 上传到日志聚合系统。

    每行一个 JSON 对象, 字段: ts / level / logger / message / module / lineno.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, DEFAULT_DATEFMT),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "lineno": record.lineno,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure(level: str | int | None = None) -> None:
    """配置 root logger,通常只在入口处调用一次。

    重复调用幂等。
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    lvl = _resolve_level(level)
    fmt, datefmt = _resolve_format()
    # 不使用 force=True,避免覆盖 pytest caplog / 其他 handler
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=lvl,
            format=fmt,
            datefmt=datefmt,
            stream=sys.stderr,
        )
    else:
        root.setLevel(lvl)
    # 抑制 DSPy / LiteLLM 的过度啰嗦,只保留 WARNING+
    for noisy in ("LiteLLM", "DSPy", "dspy", "litellm", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取 logger,首次调用会触发 configure()。"""
    configure()
    return logging.getLogger(name)


def reset() -> None:
    """测试/重置用,清空 _CONFIGURED 标志以便重新配置。"""
    global _CONFIGURED
    _CONFIGURED = False


def add_file_handler(
    logger: logging.Logger,
    log_file: str | Path,
    *,
    level: str | int | None = None,
    formatter: logging.Formatter | None = None,
) -> logging.Handler:
    """统一 FileHandler 添加接口, 保证格式与控制台一致。

    Args:
        logger:   目标 logger (通常是 get_logger(...) 的返回值)
        log_file: 输出文件路径, 父目录会自动创建
        level:    handler 级别, 默认继承 logger 级别
        formatter: 自定义 formatter, 缺省用与控制台同步的纯文本

    Returns:
        新建的 FileHandler (调用方需自行 remove, 见 remove_handler)
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding="utf-8")
    if formatter is None:
        fmt, datefmt = _resolve_format()
        formatter = logging.Formatter(fmt, datefmt=datefmt)
    handler.setFormatter(formatter)
    if level is not None:
        handler.setLevel(_resolve_level(level))
    logger.addHandler(handler)
    return handler


def remove_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    """从 logger 上移除指定 handler (主要用于测试清理)。"""
    logger.removeHandler(handler)
    handler.close()