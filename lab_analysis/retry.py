"""retry.py — 统一重试机制。"""

from __future__ import annotations

from typing import Callable

try:
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

    HAS_TENACITY = True
except ImportError:
    HAS_TENACITY = False


def api_retry_decorator(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_on_exceptions: tuple = (Exception,),
    description: str = "API调用",
):
    """
    API 重试装饰器 - 使用指数退避策略

    Args:
        max_attempts: 最大重试次数（包括首次尝试）
        min_wait: 最小等待时间（秒）
        max_wait: 最大等待时间（秒）
        retry_on_exceptions: 需要重试的异常类型元组
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

    def decorator(func: Callable) -> Callable:
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_on_exceptions),
            reraise=True,
        )(func)

    return decorator
