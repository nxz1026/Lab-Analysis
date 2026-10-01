"""DSPy module retry + fallback helper.

Provides:
    safe_predict(predictor, **kwargs): call predictor with retry (3x exponential
        backoff with jitter). Only transient failures (connection/timeout/5xx/
        rate-limit) are retried; anything else fails fast — all failures still
        surface as SafeCallError so callers can fall back.
    make_empty_prediction(signature_cls): build an empty dspy.Prediction with
        output fields zero-initialised — used as fallback when LLM keeps failing.
        ⚠️ 兜底结果必须用 is_empty_prediction() 识别, 否则会被当成正常结果落盘。
    SafeCallError: custom exception to distinguish retry-exhausted failures.
"""

from __future__ import annotations

import random
import time
import typing
from typing import Any, Callable

import dspy

from .. import _log
from ..retry import is_retryable

logger = _log.get_logger(__name__)
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE = 1.5
# 抖动系数区间：避免多患者并发时在同一时刻集体重试
_JITTER_RANGE = (0.5, 1.5)
_JITTER_RNG = random.SystemRandom()


class SafeCallError(RuntimeError):
    """Raised when a DSPy predictor fails after exhausting retries."""


def safe_predict(
    predictor: Callable[..., dspy.Prediction],
    *,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    backoff_base: float = _DEFAULT_BACKOFF_BASE,
    module_name: str = "dspy_module",
    **kwargs: Any,
) -> dspy.Prediction:
    """Call a DSPy predictor with retry + jittered exponential backoff.

    Only transient failures are retried; non-retryable ones (bad request, missing
    API key, ...) break out immediately instead of burning the backoff budget.
    Every failure is still reported as SafeCallError.

    Args:
        predictor: dspy.ChainOfThought / Predict / etc.
        max_retries: total attempts (including the first).
        backoff_base: seconds for exponential backoff base.
        module_name: for log lines.
        **kwargs: forwarded to predictor.

    Raises:
        SafeCallError: when all retries are exhausted, or on a non-retryable error.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return predictor(**kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries or not is_retryable(exc):
                break
            # 抖动退避：并发患者不锁步重试
            sleep_for = (backoff_base**attempt) * _JITTER_RNG.uniform(*_JITTER_RANGE)
            logger.warning(
                "[%s] attempt %d/%d failed (%s); retrying in %.1fs",
                module_name,
                attempt,
                max_retries,
                type(exc).__name__,
                sleep_for,
            )
            time.sleep(sleep_for)
    raise SafeCallError(
        f"[{module_name}] predictor failed after {max_retries} attempts: {last_exc}"
    ) from last_exc


def _default_for(annotation: Any) -> Any:
    """Pick a sensible zero-value for an annotation.

    Handles Optional[T] / Union[T, None] by returning None.
    """
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        args = tuple((a for a in typing.get_args(annotation) if a is not type(None)))
        if len(args) == 1 and type(None) in typing.get_args(annotation):
            return None
        if len(args) == 1:
            return _default_for(args[0])
    if annotation is float:
        return 0.0
    if annotation is int:
        return 0
    if annotation is bool:
        return False
    if annotation is dict:
        return {}
    if annotation is list:
        return []
    if annotation is str:
        return ""
    return None


def is_empty_prediction(pred: Any) -> bool:
    """判断一个 Prediction 是否是「LLM 失败后的全零兜底」。

    兜底预测的所有字符串字段都是空串、置信度是 0.0, 数值上是「合法」的:
    下游会照常把它套进完整报告模板, 产出一份格式完美但正文为空的临床报告。
    调用方必须用这个函数把它识别出来, 显式标记降级或直接失败。
    """
    data = getattr(pred, "__dict__", None) or {}
    if not data:
        return True
    saw_text = False
    for name, value in data.items():
        if name.startswith("_"):
            continue
        if isinstance(value, str):
            saw_text = True
            if value.strip():
                return False
        elif isinstance(value, float) and value:
            return False
    # 没有任何非空文本 → 视为兜底空预测
    return saw_text or not data


def make_empty_prediction(signature_cls: type[dspy.Signature]) -> dspy.Prediction:
    """Build an empty dspy.Prediction with all output fields zero-initialised.

    Args:
        signature_cls: a dspy.Signature subclass (Pydantic model).

    Returns:
        dspy.Prediction with output fields set to "" / None / 0.0 / empty-dict.
    """
    fields = getattr(signature_cls, "model_fields", {})
    defaults: dict[str, Any] = {}
    for name, field in fields.items():
        is_output = (field.json_schema_extra or {}).get("__dspy_field_type") == "output"
        if not is_output:
            continue
        defaults[name] = _default_for(field.annotation)
    return dspy.Prediction(**defaults)
