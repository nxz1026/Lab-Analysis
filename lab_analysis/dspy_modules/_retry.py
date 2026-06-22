"""DSPy module retry + fallback helper.

Provides:
    safe_predict(predictor, **kwargs): call predictor with retry (3x exponential backoff).
        Raises SafeCallError on persistent failure.
    make_empty_prediction(signature_cls): build an empty dspy.Prediction with
        output fields zero-initialised — used as fallback when LLM keeps failing.
    SafeCallError: custom exception to distinguish retry-exhausted failures.
"""

from __future__ import annotations

import logging
import time
import typing
from typing import Any, Callable

import dspy

_LOG = logging.getLogger(__name__)

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_BASE = 1.5


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
    """Call a DSPy predictor with retry + exponential backoff.

    Args:
        predictor: dspy.ChainOfThought / Predict / etc.
        max_retries: total attempts (including the first).
        backoff_base: seconds for exponential backoff base.
        module_name: for log lines.
        **kwargs: forwarded to predictor.

    Raises:
        SafeCallError: when all retries are exhausted.
    """
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return predictor(**kwargs)
        except Exception as exc:  # noqa: BLE001 — we want to catch all LLM errors
            last_exc = exc
            if attempt >= max_retries:
                break
            sleep_for = backoff_base ** attempt
            _LOG.warning(
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
        args = tuple(a for a in typing.get_args(annotation) if a is not type(None))
        if len(args) == 1 and type(None) in typing.get_args(annotation):
            # Optional[T] → None
            return None
        # bare Union, fall through to str
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
    return ""


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
        # dspy 3.x: __dspy_field_type in json_schema_extra
        is_output = (field.json_schema_extra or {}).get("__dspy_field_type") == "output"
        if not is_output:
            continue
        defaults[name] = _default_for(field.annotation)
    return dspy.Prediction(**defaults)