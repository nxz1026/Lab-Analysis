"""tests.test_patient_id — 身份证号脱敏与校验测试"""

import pytest

from lab_analysis.patient_id import decode, encode, validate_id_card


class TestEncodeDecode:
    """AES-GCM 脱敏算法：确定性 + 可逆 + URL 安全"""

    SAMPLE = "110101199003078888"

    def test_roundtrip(self):
        """同一身份证号可还原"""
        obf = encode(self.SAMPLE)
        restored = decode(obf)
        assert restored == self.SAMPLE

    def test_deterministic(self):
        """同一身份证号每次产出同一 deid"""
        assert encode(self.SAMPLE) == encode(self.SAMPLE)

    def test_different_inputs_different_outputs(self):
        """不同身份证号产出不同 deid"""
        assert encode(self.SAMPLE) != encode("320106198709091234")

    def test_url_safe(self):
        """deid 不包含 URL 不安全字符（/ + 等）"""
        obf = encode(self.SAMPLE)
        assert "/" not in obf
        assert "+" not in obf
        assert "=" not in obf

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            encode("")
        with pytest.raises(ValueError):
            decode("")


class TestValidateIdCard:
    """身份证号强制校验"""

    VALID = "110101199003078888"
    VALID_SHORT = "110101900307888"  # 15 位
    INVALID_FORMAT = "12345"

    def test_valid_pass(self):
        assert validate_id_card(self.VALID, interactive=False) == self.VALID

    def test_valid_15_pass(self):
        assert validate_id_card(self.VALID_SHORT, interactive=False) == self.VALID_SHORT

    def test_invalid_noninteractive_returns_none(self):
        assert validate_id_card(self.INVALID_FORMAT, interactive=False) is None
        assert validate_id_card("", interactive=False) is None

    def test_ocr_fallback(self):
        """命令行无效时使用 OCR 提取的有效值"""
        result = validate_id_card("garbage", extracted_id=self.VALID, interactive=False)
        assert result == self.VALID

    def test_mismatch_noninteractive_returns_none(self):
        """命令行与 OCR 值不一致时放弃"""
        result = validate_id_card("110101199003078800", extracted_id=self.VALID, interactive=False)
        assert result is None


class TestChineseIdValidation:
    """底层身份证号格式校验"""

    def test_valid_18(self):
        from lab_analysis.utils import validate_chinese_id as f
        assert f("110101199003078888") is True

    def test_valid_15(self):
        from lab_analysis.utils import validate_chinese_id as f
        assert f("110101900307888") is True

    def test_invalid(self):
        from lab_analysis.utils import validate_chinese_id as f
        assert f("123") is False
        assert f("") is False
        assert f(None) is False
