"""_phi_filter.py — 全局 PHI 脱敏日志过滤器"""
import logging
import re

_PHI_ID_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)|(?<!\d)\d{15}(?!\d)")


def strip_phi(text: str) -> str:
    return _PHI_ID_PATTERN.sub("[PHI_REDACTED]", text)


def redact_record(record: logging.LogRecord) -> None:
    """就地脱敏一条 LogRecord 的 msg 与 args。

    必须同时处理 args: ``log.info("身份证: %s", pid)`` 的明文保存在 args 里,
    只脱敏 msg 会整个漏掉。
    """
    if isinstance(getattr(record, "msg", None), str):
        record.msg = strip_phi(record.msg)
    args = getattr(record, "args", None)
    if isinstance(args, tuple):
        record.args = tuple(strip_phi(a) if isinstance(a, str) else a for a in args)
    elif isinstance(args, dict):
        record.args = {k: (strip_phi(v) if isinstance(v, str) else v) for k, v in args.items()}


class PHIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        redact_record(record)
        return True


_INSTALLED = False


def install_global_phi_redaction() -> None:
    """进程级安装 PHI 脱敏, 幂等。

    为什么不用 ``logging.getLogger().addFilter(...)``
    ------------------------------------------------
    Python 的 logger filter 只对**经由该 logger 自身**产生的 record 生效;
    子 logger 的 record 只会向祖先的 *handler* 传播, **不经过祖先的 filter**。
    全项目统一用 ``get_logger(__name__)``, 所以挂在 root logger 上的 filter
    永远不会被执行 —— 实测子 logger 原样输出 18 位身份证号。

    LogRecord factory 是 record 生成的唯一入口, 与 logger/handler 如何接线无关,
    因此 lastResort、第三方 handler、pytest caplog 同样受保护。
    """
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    base_factory = logging.getLogRecordFactory()

    def _phi_record_factory(*args, **kwargs):
        record = base_factory(*args, **kwargs)
        redact_record(record)
        return record

    logging.setLogRecordFactory(_phi_record_factory)
