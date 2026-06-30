"""tests.test_phi_filter — PHI 脱敏过滤器单测。"""

from __future__ import annotations

import logging

from lab_analysis._phi_filter import PHIFilter, strip_phi


def test_strip_phi_18_digit_id():
    assert strip_phi("身份证号110101199001011234") == "身份证号[PHI_REDACTED]"


def test_strip_phi_18_digit_with_x():
    assert strip_phi("11010119900101123X") == "[PHI_REDACTED]"


def test_strip_phi_18_digit_with_lower_x():
    assert strip_phi("11010119900101123x") == "[PHI_REDACTED]"


def test_strip_phi_15_digit_id():
    assert strip_phi("110101990010112") == "[PHI_REDACTED]"


def test_strip_phi_short_number():
    assert strip_phi("12345") == "12345"


def test_strip_phi_normal_text():
    assert strip_phi("正常文本无敏感信息") == "正常文本无敏感信息"


def test_strip_phi_empty():
    assert strip_phi("") == ""


def test_phifilter_filter_redacts():
    rec = logging.LogRecord("test", logging.INFO, "", 0, "身份证号110101199001011234", {}, None)
    f = PHIFilter()
    assert f.filter(rec)
    assert rec.msg == "身份证号[PHI_REDACTED]"
