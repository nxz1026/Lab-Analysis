"""tests.test_exceptions — 共享异常常量单测。"""

from __future__ import annotations

from lab_analysis._exceptions import SAFE_EXCEPTIONS


class TestSafeExceptions:
    def test_is_tuple(self):
        assert isinstance(SAFE_EXCEPTIONS, tuple)

    def test_contains_common_exceptions(self):
        assert ValueError in SAFE_EXCEPTIONS
        assert TypeError in SAFE_EXCEPTIONS
        assert KeyError in SAFE_EXCEPTIONS
        assert AttributeError in SAFE_EXCEPTIONS
        assert OSError in SAFE_EXCEPTIONS
        assert RuntimeError in SAFE_EXCEPTIONS

    def test_all_are_exception_classes(self):
        for exc in SAFE_EXCEPTIONS:
            assert isinstance(exc, type) and issubclass(exc, Exception)
