"""tests.test_retry — 统一重试机制单测。"""

from __future__ import annotations

from lab_analysis.retry import HAS_TENACITY, api_retry_decorator


def test_has_tenacity_defined():
    assert isinstance(HAS_TENACITY, bool)


def test_api_retry_decorator_returns_decorator():
    deco = api_retry_decorator(max_attempts=2)
    assert callable(deco)


def test_decorator_identity_when_no_tenacity(monkeypatch):
    monkeypatch.setattr("lab_analysis.retry.HAS_TENACITY", False)
    called = False

    @api_retry_decorator(max_attempts=3)
    def foo():
        nonlocal called
        called = True
        return 42

    result = foo()
    assert result == 42
    assert called


def test_decorator_passes_args():
    @api_retry_decorator(max_attempts=3, description="测试")
    def add(a, b):
        return a + b

    assert add(1, 2) == 3
