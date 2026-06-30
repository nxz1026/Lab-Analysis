"""_phi_filter.py — 全局 PHI 脱敏日志过滤器"""
import logging
import re

_PHI_ID_PATTERN = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)|(?<!\d)\d{15}(?!\d)")


def strip_phi(text: str) -> str:
    return _PHI_ID_PATTERN.sub("[PHI_REDACTED]", text)


class PHIFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = _PHI_ID_PATTERN.sub("[PHI_REDACTED]", record.msg)
        return True
