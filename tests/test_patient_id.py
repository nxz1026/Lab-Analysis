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


class TestDecodeKey:
    """_decode_key 容错解码"""

    def test_urlsafe_with_padding(self):
        import base64

        from lab_analysis.patient_id import _decode_key
        raw = b"hello world test"
        encoded = base64.urlsafe_b64encode(raw).decode("ascii")
        assert _decode_key(encoded) == raw

    def test_urlsafe_without_padding(self):
        import base64

        from lab_analysis.patient_id import _decode_key
        raw = b"hello world test"
        encoded = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
        assert _decode_key(encoded) == raw

    def test_standard_base64_fallback(self):
        import base64

        from lab_analysis.patient_id import _decode_key
        # 标准 base64 可能带 +/ 而 urlsafe 带 -_
        raw = b"\xfb\xff\xfe"  # 触发 urlsafe/标准 分支
        encoded = base64.b64encode(raw).decode("ascii")
        # urlsafe 失败则走标准
        assert _decode_key(encoded) == raw

    def test_strip_whitespace(self):
        import base64

        from lab_analysis.patient_id import _decode_key
        raw = b"abc"
        encoded = base64.urlsafe_b64encode(raw).decode("ascii")
        assert _decode_key(f"  {encoded}\n") == raw


class TestLoadMasterKey:
    """_load_or_create_master_key 路径覆盖"""

    def test_env_var_takes_priority(self, tmp_path, monkeypatch):
        import base64

        import lab_analysis.patient_id as pid
        from lab_analysis.patient_id import _load_or_create_master_key

        env_key = base64.urlsafe_b64encode(b"x" * 32).decode("ascii")
        monkeypatch.setenv("LAB_DEID_KEY", env_key)
        # 置一个错误的 file，验证 env 优先级
        monkeypatch.setattr(pid, "_KEY_FILE", tmp_path / "nope.key")
        key = _load_or_create_master_key()
        assert key == b"x" * 32

    def test_env_var_wrong_length_raises(self, monkeypatch):
        import base64

        from lab_analysis.patient_id import _load_or_create_master_key

        bad = base64.urlsafe_b64encode(b"x" * 16).decode("ascii")
        monkeypatch.setenv("LAB_DEID_KEY", bad)
        with pytest.raises(ValueError, match="必须为 32 字节"):
            _load_or_create_master_key()

    def test_existing_key_file(self, tmp_path, monkeypatch):
        import base64

        import lab_analysis.patient_id as pid

        monkeypatch.delenv("LAB_DEID_KEY", raising=False)
        key_file = tmp_path / "master.key"
        key_file.write_text(
            base64.urlsafe_b64encode(b"y" * 32).decode("ascii"), encoding="utf-8"
        )
        monkeypatch.setattr(pid, "_KEY_FILE", key_file)
        from lab_analysis.patient_id import _load_or_create_master_key

        assert _load_or_create_master_key() == b"y" * 32

    def test_existing_key_file_wrong_length(self, tmp_path, monkeypatch):
        import base64

        import lab_analysis.patient_id as pid

        monkeypatch.delenv("LAB_DEID_KEY", raising=False)
        key_file = tmp_path / "master.key"
        # 16 字节 = 合法 base64 但 decode 后不是 32 字节
        key_file.write_text(
            base64.urlsafe_b64encode(b"x" * 16).decode("ascii"), encoding="utf-8"
        )
        monkeypatch.setattr(pid, "_KEY_FILE", key_file)
        from lab_analysis.patient_id import _load_or_create_master_key

        with pytest.raises(ValueError, match="必须为 32 字节"):
            _load_or_create_master_key()

    def test_auto_generate_new_key(self, tmp_path, monkeypatch):
        import lab_analysis.patient_id as pid

        monkeypatch.delenv("LAB_DEID_KEY", raising=False)
        monkeypatch.setattr(pid, "_KEY_FILE", tmp_path / ".hermes" / "master.key")
        from lab_analysis.patient_id import _load_or_create_master_key

        key = _load_or_create_master_key()
        assert len(key) == 32
        assert (tmp_path / ".hermes" / "master.key").exists()
