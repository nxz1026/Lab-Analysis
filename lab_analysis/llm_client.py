#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_client.py — 统一的 LLM / Vision API 客户端

目的
====
消除 lab_analysis 各模块中重复出现的「读 .env → 拼 headers → requests.post → 解析 choices」模式。
本模块提供三个层级的能力：

1. ``load_api_key(name)`` —— 统一的密钥读取（环境变量优先，等价于依赖 __init__.py 的 load_dotenv）。
2. ``call_chat(...)`` —— OpenAI 兼容的 chat/completions 调用，覆盖：
     - DeepSeek (deepseek-chat)
     - 智谱 GLM-4V (glm-4v-flash，含多模态 image_url)
3. ``call_dashscope_multimodal(...)`` —— 阿里 DashScope 原生 multimodal-generation 调用（qwen-vl-plus），
   其 payload/response 形态与 OpenAI 不兼容（多一层 ``input`` / ``output`` 包裹）。

不在本模块管辖范围：
- DSPy 的 ``dspy.LM(...)`` 配置（那是 LiteLLM 层，保留在各 *_dspy.py 模块内）。
- PubMed E-utilities（非 LLM，见 literature_searcher.py）。

设计原则
========
- 单次职责：本模块只负责「发请求 + 取文本」，**不构造 prompt、不解析业务 JSON**。
- 行为保持向后兼容：默认重试、超时、temperature/max_tokens 与原各处实现一致。
- .env 读取统一走 ``load_dotenv``（已在 lab_analysis/__init__.py 完成），本模块不再重复解析 .env 文件。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import requests

from lab_analysis.utils import api_retry_decorator

# ── 各 Provider 的默认配置 ──────────────────────────────────────────────
# 集中维护，避免散落在调用方。
_PROVIDERS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/chat/completions",
        "env_var": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
        "default_max_tokens": 4096,
        "default_temperature": 0.3,
        "default_timeout": 60,
    },
    "zhipu": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "env_var": "ZHIPU_API_KEY",
        "default_model": "glm-4v-flash",
        "default_max_tokens": 1024,  # GLM-4V-Flash 上限 1024
        "default_temperature": None,
        "default_timeout": 120,
    },
}
_DASHSCOPE_MULTIMODAL_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
)
_USER_AGENT = "Hermes-Lab-Analyzer/1.0"


# ── 密钥读取 ────────────────────────────────────────────────────────────


def load_api_key(env_var: str, *, required: bool = True) -> Optional[str]:
    """读取 API 密钥。

    统一逻辑：``os.environ`` 优先（已由 ``lab_analysis/__init__.py`` 的
    ``load_dotenv()`` 从 .env 注入），不再在各处重复解析 .env 文件。

    Args:
        env_var:   环境变量名（如 ``"DEEPSEEK_API_KEY"``）。
        required:  为 True 且缺失时抛 ``RuntimeError``；为 False 时返回 None。
    """
    val = os.environ.get(env_var, "").strip()
    if val:
        return val
    if required:
        raise RuntimeError(f"未找到环境变量 {env_var}。请在 .env 或运行环境中配置。")
    return None


def _resolve_provider(provider: str) -> dict:
    """根据 provider 名取配置，并校验。"""
    if provider not in _PROVIDERS:
        raise ValueError(f"未知 provider: {provider!r}，可选: {list(_PROVIDERS)}")
    return _PROVIDERS[provider]


# ── OpenAI 兼容 chat 调用（DeepSeek / 智谱 GLM-4V）─────────────────────


def call_chat(
    provider: str,
    *,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    image_b64: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: Optional[int] = None,
    api_key: Optional[str] = None,
) -> str:
    """调用 OpenAI 兼容的 chat/completions 接口，返回 assistant 文本。

    覆盖 DeepSeek（纯文本）与智谱 GLM-4V（多模态）。

    Args:
        provider:       ``"deepseek"`` 或 ``"zhipu"``。
        user_prompt:    用户消息文本（业务 prompt）。
        system_prompt:  可选 system 消息（DeepSeek 文献/报告解读使用）。
        image_b64:      可选图片 base64（**不含** data-URL 前缀）。
                        传入时自动构造 OpenAI 多模态 content（覆盖 GLM-4V 用途）。
        model/temperature/max_tokens/timeout:  None 表示用 provider 默认值。
        api_key:        显式密钥；None 时按 provider 的 env_var 读取。

    Returns:
        assistant 回复文本（``choices[0].message.content``）。

    Raises:
        RuntimeError: 密钥缺失。
        requests.HTTPError: HTTP 非 2xx。
    """
    cfg = _resolve_provider(provider)
    key = api_key or load_api_key(cfg["env_var"])

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if image_b64:
        # 多模态：OpenAI image_url 形态（GLM-4V 用此）
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }
        )
    else:
        messages.append({"role": "user", "content": user_prompt})

    payload: dict[str, Any] = {
        "model": model or cfg["default_model"],
        "messages": messages,
    }
    # 仅在显式或默认非 None 时写入，避免向不支持这些字段的 provider 发送 None
    temp = cfg["default_temperature"] if temperature is None else temperature
    if temp is not None:
        payload["temperature"] = temp
    mt = cfg["default_max_tokens"] if max_tokens is None else max_tokens
    if mt is not None:
        payload["max_tokens"] = mt

    resp = requests.post(
        cfg["base_url"],
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
        json=payload,
        timeout=cfg["default_timeout"] if timeout is None else timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


def call_chat_with_retry(
    provider: str, *, max_attempts: int = 3, min_wait: float = 2.0, max_wait: float = 30.0, **kwargs
) -> str:
    """``call_chat`` 的指数退避重试封装（tenacity 缺失时为透传）。

    保留与原 ``literature_interpreter.call_deepseek`` 一致的默认退避参数。
    """
    decorated = api_retry_decorator(
        max_attempts=max_attempts,
        min_wait=min_wait,
        max_wait=max_wait,
        description=f"{provider} chat",
    )(lambda: call_chat(provider, **kwargs))
    return decorated()


# ── DashScope 原生 multimodal 调用（qwen-vl-plus）───────────────────────


def call_dashscope_multimodal(
    *,
    image_b64: str,
    text_prompt: str,
    model: str = "qwen-vl-plus",
    timeout: int = 120,
    api_key: Optional[str] = None,
) -> str:
    """调用 DashScope 原生 multimodal-generation 接口，返回 assistant 文本。

    注意 DashScope 原生 API 的 payload/response 形态与 OpenAI **不**兼容：
      - 请求多一层 ``input`` 包裹；content 项用 ``{"image": ...}`` / ``{"text": ...}``。
      - 响应多一层 ``output`` 包裹。

    Args:
        image_b64:  图片 base64（**不含** data-URL 前缀；本函数自动拼接）。
        text_prompt: 文本提示（含业务指令）。
        model/timeout/api_key: 同 call_chat。
    """
    key = api_key or load_api_key("DASHSCOPE_API_KEY")
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{image_b64}"},
                        {"text": text_prompt},
                    ],
                }
            ]
        },
    }
    resp = requests.post(
        _DASHSCOPE_MULTIMODAL_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", "")


# ── 辅助：从可能含 ```json 代码块标记的文本中提取 JSON ──────────────────

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def strip_code_fence(text: str) -> str:
    """去除 LLM 回复中常见的 ```json ... ``` / ``` ... ``` 代码块标记。

    多个调用方（vision_extractor、extract_lab_data）各自实现了这段，
    在此统一以便复用。
    """
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def parse_json_response(text: str) -> dict:
    """从 LLM 文本回复解析 JSON，自动剥离代码块标记。

    解析失败时抛 ``json.JSONDecodeError``（调用方可捕获后重试）。
    """
    cleaned = strip_code_fence(text)
    return json.loads(cleaned)
