"""retry.py — 统一重试机制。"""

from __future__ import annotations

from typing import Callable

import requests

try:
    from tenacity import (
        retry,
        retry_if_exception,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False

# 默认只重试「瞬时」故障：连接被重置/超时这类传输层问题。
# 401/403/请求非法与缺少 API Key 的 RuntimeError 重试无意义，只会白等 3 次指数退避。
DEFAULT_RETRY_EXCEPTIONS: tuple = (requests.ConnectionError, requests.Timeout)

# DSPy 走的是 LiteLLM，抛的是 litellm.exceptions.*，**不是** requests 的子类。
# 若不识别，DSPy 侧 safe_predict 会在第 1 次就判定「不可重试」直接失败，
# 退化成空预测报告 —— 这正是收窄重试时最容易踩的坑。
# 单独收集，缺 litellm（可选依赖）时退化为空元组，不影响其它路径。
try:  # pragma: no cover - 取决于可选依赖是否安装
    from litellm import exceptions as _litellm_exceptions

    _LITELLM_RETRYABLE: tuple = (
        _litellm_exceptions.APIConnectionError,
        _litellm_exceptions.Timeout,
        _litellm_exceptions.RateLimitError,
        _litellm_exceptions.InternalServerError,
        _litellm_exceptions.ServiceUnavailableError,
    )
except Exception:  # noqa: BLE001 - litellm 可能不存在或结构变化
    _LITELLM_RETRYABLE = ()

# 5xx 与 429（限流）属服务端侧的瞬时故障，值得重试；其余 4xx 立即失败。
_RETRYABLE_HTTP_STATUS = 429


def is_retryable(exc: BaseException) -> bool:
    """判断异常是否属于可重试的瞬时故障（供默认策略与 DSPy 侧复用）。"""
    if isinstance(exc, DEFAULT_RETRY_EXCEPTIONS):
        return True
    if _LITELLM_RETRYABLE and isinstance(exc, _LITELLM_RETRYABLE):
        return True
    if isinstance(exc, requests.HTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        return isinstance(status, int) and (status == _RETRYABLE_HTTP_STATUS or status >= 500)
    # LiteLLM 的异常自带 status_code，类比上面的 HTTPError 分支处理
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == _RETRYABLE_HTTP_STATUS or status >= 500
    return False


def api_retry_decorator(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_on_exceptions: tuple = DEFAULT_RETRY_EXCEPTIONS,
    description: str = "API调用",
):
    """
    API 重试装饰器 - 使用指数退避策略

    Args:
        max_attempts: 最大重试次数（包括首次尝试）
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）
        retry_on_exceptions: 需要重试的异常类型元组；保持默认时额外按 HTTP 状态码
            过滤（仅 5xx/429 视为瞬时故障）。显式传入元组的调用方维持原有
            「按类型匹配」语义。
        description: API 描述（用于日志）

    Returns:
        装饰器函数

    Example:
        @api_retry_decorator(max_attempts=3, description="智谱AI")
        def call_zhipu_api(...):
            ...
    """
    if not HAS_TENACITY:

        def dummy_decorator(func):
            return func

        return dummy_decorator

    # 显式传参的调用方保持原语义；默认走「瞬时故障」判定。
    if retry_on_exceptions is DEFAULT_RETRY_EXCEPTIONS:
        retry_strategy = retry_if_exception(is_retryable)
    else:
        retry_strategy = retry_if_exception_type(retry_on_exceptions)

    def decorator(func: Callable) -> Callable:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_strategy,
            reraise=True,
        )(func)

    return decorator
