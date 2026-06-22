"""tests/test_llm_client_extra.py — llm_client 补充测试

覆盖 load_api_key / _resolve_provider / call_chat (mocked) /
call_chat_with_retry / call_dashscope_multimodal (mocked) /
strip_code_fence / parse_json_response。
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import requests

# ── load_api_key ────────────────────────────────────────────────────


class TestLoadApiKey:
    def test_required_missing_raises(self, monkeypatch):
        monkeypatch.delenv("MY_TEST_KEY", raising=False)
        from lab_analysis.llm_client import load_api_key
        with pytest.raises(RuntimeError, match="未找到环境变量"):
            load_api_key("MY_TEST_KEY")

    def test_required_present(self, monkeypatch):
        monkeypatch.setenv("MY_TEST_KEY", "  abc123  ")
        from lab_analysis.llm_client import load_api_key
        assert load_api_key("MY_TEST_KEY") == "abc123"

    def test_optional_missing_returns_none(self, monkeypatch):
        monkeypatch.delenv("MY_TEST_KEY", raising=False)
        from lab_analysis.llm_client import load_api_key
        assert load_api_key("MY_TEST_KEY", required=False) is None


# ── _resolve_provider ───────────────────────────────────────────────


class TestResolveProvider:
    def test_known_provider(self):
        from lab_analysis.llm_client import _resolve_provider
        cfg = _resolve_provider("deepseek")
        assert cfg["env_var"] == "DEEPSEEK_API_KEY"
        assert "base_url" in cfg

    def test_unknown_provider_raises(self):
        from lab_analysis.llm_client import _resolve_provider
        with pytest.raises(ValueError, match="未知 provider"):
            _resolve_provider("nonexistent_provider")


# ── call_chat (mocked) ──────────────────────────────────────────────


class TestCallChat:
    def _mock_response(self, content: str = "hello", status: int = 200):
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = {"choices": [{"message": {"content": content}}]}
        resp.raise_for_status = MagicMock()
        return resp

    def test_basic_deepseek(self, monkeypatch):
        from lab_analysis import llm_client

        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
        resp = self._mock_response("hi from deepseek")
        with patch.object(llm_client.requests, "post", return_value=resp) as p:
            result = llm_client.call_chat("deepseek", user_prompt="hi")
        assert result == "hi from deepseek"
        # 验证 base_url 用的是 deepseek
        args, kwargs = p.call_args
        assert "deepseek" in args[0]

    def test_zhipu_with_image(self, monkeypatch):
        from lab_analysis import llm_client

        monkeypatch.setenv("ZHIPU_API_KEY", "fake")
        resp = self._mock_response("zhipu reply")
        with patch.object(llm_client.requests, "post", return_value=resp) as p:
            result = llm_client.call_chat(
                "zhipu", user_prompt="看图", image_b64="BASE64DATA"
            )
        assert result == "zhipu reply"
        args, kwargs = p.call_args
        payload = kwargs["json"]
        # 多模态 content 应是 list
        assert isinstance(payload["messages"][-1]["content"], list)
        assert payload["messages"][-1]["content"][0]["type"] == "image_url"
        assert "BASE64DATA" in payload["messages"][-1]["content"][0]["image_url"]["url"]

    def test_system_prompt_included(self, monkeypatch):
        from lab_analysis import llm_client

        monkeypatch.setenv("DEEPSEEK_API_KEY", "fake")
        resp = self._mock_response("ok")
        with patch.object(llm_client.requests, "post", return_value=resp) as p:
            llm_client.call_chat(
                "deepseek",
                user_prompt="u",
                system_prompt="你是医生",
            )
        payload = p.call_args.kwargs["json"]
        assert payload["messages"][0] == {"role": "system", "content": "你是医生"}
        assert payload["messages"][1] == {"role": "user", "content": "u"}

    def test_explicit_api_key_overrides_env(self):
        from lab_analysis import llm_client

        resp = self._mock_response("explicit")
        with patch.object(llm_client.requests, "post", return_value=resp) as p:
            llm_client.call_chat(
                "deepseek",
                user_prompt="hi",
                api_key="explicit-key",
            )
        headers = p.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer explicit-key"

    def test_explicit_temperature_and_model(self):
        from lab_analysis import llm_client

        resp = self._mock_response("ok")
        with patch.object(llm_client.requests, "post", return_value=resp) as p:
            llm_client.call_chat(
                "deepseek",
                user_prompt="hi",
                temperature=0.7,
                max_tokens=2048,
                model="custom-model",
                api_key="k",
            )
        payload = p.call_args.kwargs["json"]
        assert payload["model"] == "custom-model"
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 2048

    def test_missing_default_temperature_omits_field(self):
        """zhipu 的 default_temperature=None，payload 不应有 temperature 字段"""
        from lab_analysis import llm_client

        resp = self._mock_response("ok")
        with patch.object(llm_client.requests, "post", return_value=resp) as p:
            llm_client.call_chat("zhipu", user_prompt="hi", api_key="k")
        payload = p.call_args.kwargs["json"]
        assert "temperature" not in payload

    def test_http_error_propagates(self):
        from lab_analysis import llm_client

        resp = self._mock_response(status=500)
        resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        with (
            patch.object(llm_client.requests, "post", return_value=resp),
            pytest.raises(requests.HTTPError),
        ):
            llm_client.call_chat("deepseek", user_prompt="hi", api_key="k")


# ── call_chat_with_retry ────────────────────────────────────────────


class TestCallChatWithRetry:
    def test_succeeds_first_try(self):
        from lab_analysis import llm_client

        resp = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        resp.raise_for_status = MagicMock()
        with patch.object(llm_client.requests, "post", return_value=resp):
            result = llm_client.call_chat_with_retry(
                "deepseek", user_prompt="hi", api_key="k"
            )
        assert result == "ok"


# ── call_dashscope_multimodal (mocked) ──────────────────────────────


class TestDashScopeMultimodal:
    def test_basic(self):
        from lab_analysis import llm_client

        resp = MagicMock()
        resp.json.return_value = {
            "output": {
                "choices": [
                    {"message": {"content": [{"text": "qwen reply"}]}}
                ]
            }
        }
        resp.raise_for_status = MagicMock()
        with patch.object(llm_client.requests, "post", return_value=resp) as p:
            result = llm_client.call_dashscope_multimodal(
                image_b64="IMG", text_prompt="看图", api_key="k"
            )
        # 生产代码只取 .content 原样返回，不做 list→str 转换
        # 调用方需要自己 .content[0]["text"] 提取
        assert result == [{"text": "qwen reply"}]
        payload = p.call_args.kwargs["json"]
        assert "input" in payload
        assert "messages" in payload["input"]
        assert payload["input"]["messages"][0]["role"] == "user"
        assert "IMG" in str(payload["input"]["messages"][0]["content"])

    def test_empty_content(self):
        from lab_analysis import llm_client

        resp = MagicMock()
        resp.json.return_value = {
            "output": {"choices": [{"message": {"content": "just a string"}}]}
        }
        resp.raise_for_status = MagicMock()
        with patch.object(llm_client.requests, "post", return_value=resp):
            result = llm_client.call_dashscope_multimodal(
                image_b64="x", text_prompt="p", api_key="k"
            )
        assert result == "just a string"

    def test_custom_model_and_timeout(self):
        from lab_analysis import llm_client

        resp = MagicMock()
        resp.json.return_value = {"output": {"choices": [{"message": {"content": ""}}]}}
        resp.raise_for_status = MagicMock()
        with patch.object(llm_client.requests, "post", return_value=resp) as p:
            llm_client.call_dashscope_multimodal(
                image_b64="x", text_prompt="p",
                model="qwen-vl-max", timeout=300, api_key="k",
            )
        payload = p.call_args.kwargs["json"]
        assert payload["model"] == "qwen-vl-max"
        assert p.call_args.kwargs["timeout"] == 300


# ── strip_code_fence ────────────────────────────────────────────────


class TestStripCodeFence:
    def test_no_fence(self):
        from lab_analysis.llm_client import strip_code_fence
        assert strip_code_fence("plain text") == "plain text"

    def test_json_fence(self):
        from lab_analysis.llm_client import strip_code_fence
        assert strip_code_fence("```json\n{\"a\": 1}\n```") == '{"a": 1}'

    def test_bare_fence(self):
        from lab_analysis.llm_client import strip_code_fence
        assert strip_code_fence("```\nhello\n```") == "hello"

    def test_strips_outer_whitespace(self):
        from lab_analysis.llm_client import strip_code_fence
        assert strip_code_fence("  ```json\n{}\n```  ") == "{}"


# ── parse_json_response ─────────────────────────────────────────────


class TestParseJsonResponse:
    def test_plain_json(self):
        from lab_analysis.llm_client import parse_json_response
        assert parse_json_response('{"a": 1, "b": [2,3]}') == {"a": 1, "b": [2, 3]}

    def test_fenced_json(self):
        from lab_analysis.llm_client import parse_json_response
        text = '```json\n{"k": "v"}\n```'
        assert parse_json_response(text) == {"k": "v"}

    def test_invalid_json_raises(self):
        from lab_analysis.llm_client import parse_json_response
        with pytest.raises(json.JSONDecodeError):
            parse_json_response("not json at all")

    def test_chinese_values(self):
        from lab_analysis.llm_client import parse_json_response
        text = '```json\n{"诊断": "胰腺炎"}\n```'
        assert parse_json_response(text) == {"诊断": "胰腺炎"}