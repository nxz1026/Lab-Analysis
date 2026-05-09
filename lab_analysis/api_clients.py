"""
api_clients.py — 统一封装所有第三方 API 调用，内置 tenacity 指数退避重试。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import requests
import tenacity

# ── Zhipu AI (glm-4v-flash) ─────────────────────────────────────────────────

ZHIPU_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def _is_zhipu_retryable(resp: requests.Response) -> bool:
    """Zhipu API 在超载/限流时返回 429 或 5xx"""
    return resp.status_code in (429, 500, 502, 503, 504)


@tenacity.retry(
    retry=tenacity.retry_if_response(_is_zhipu_retryable),
    wait=tenacity.wait_exponential(multiplier=2, min=2, max=60),
    stop=tenacity.stop_after_attempt(5),
    reraise=True,
)
def call_zhipu_vision(
    api_key: str,
    image_b64: str,
    prompt: str,
    model: str = "glm-4v-flash",
    timeout: int = 120,
) -> dict:
    """调用智谱 AI GLM-4V 模型处理图片+文字，返回 parsed JSON dict。"""
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    resp = requests.post(
        ZHIPU_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


# ── DeepSeek ────────────────────────────────────────────────────────────────

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"


def _is_deepseek_retryable(resp: requests.Response) -> bool:
    """DeepSeek 在服务器过载时返回 429 或 5xx"""
    return resp.status_code in (429, 500, 502, 503, 504)


@tenacity.retry(
    retry=tenacity.retry_if_response(_is_deepseek_retryable),
    wait=tenacity.wait_exponential(multiplier=2, min=2, max=60),
    stop=tenacity.stop_after_attempt(5),
    reraise=True,
)
def call_deepseek(
    api_key: str,
    messages: list[dict],
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: int = 60,
) -> dict:
    """调用 DeepSeek Chat API，返回完整 response JSON。"""
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Hermes-Lab-Analyzer/1.0",
        },
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


# ── 通义千问 (DASHSCOPE) ────────────────────────────────────────────────────

DASHSCOPE_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


def _is_dashscope_retryable(resp: requests.Response) -> bool:
    """DASHSCOPE 在限流时返回 429"""
    return resp.status_code == 429


@tenacity.retry(
    retry=tenacity.retry_if_response(_is_dashscope_retryable),
    wait=tenacity.wait_exponential(multiplier=2, min=2, max=60),
    stop=tenacity.stop_after_attempt(5),
    reraise=True,
)
def call_dashscope(
    api_key: str,
    messages: list[dict],
    model: str = "qwen-vl-max",
    timeout: int = 120,
) -> dict:
    """调用阿里云通义千问视觉 API。"""
    payload = {"model": model, "messages": messages}
    resp = requests.post(
        DASHSCOPE_API_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


# ── PubMed (NCBI E-utilities) ───────────────────────────────────────────────

PUBMED_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def _is_pubmed_retryable(exc: Exception) -> bool:
    """NCBI E-utilities 在服务繁忙时可能返回 HTTP 429 或临时不可用"""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429
    if isinstance(exc, urllib.error.URLError):
        # Connection refused / reset / timeout 均值得重试
        return True
    return False


@tenacity.retry(
    retry=tenacity.retry_if_exception(_is_pubmed_retryable),
    wait=tenacity.wait_exponential(multiplier=2, min=2, max=30),
    stop=tenacity.stop_after_attempt(5),
    reraise=True,
)
def pubmed_esearch(
    query: str,
    retmax: int = 20,
    date_filter: int | None = None,
    sort: str = "relevance",
) -> dict:
    """
    PubMed esearch：返回 {"esultult": {"idlist": [...], "count": "N", ...}}
    """
    n_years_ago = None
    if date_filter:
        n_years_ago = __import__("datetime").datetime.now().year - date_filter

    date_clause = ""
    if n_years_ago is not None:
        date_clause = f' AND ("{n_years_ago}"[Date - Publication] : "2099"[Date - Publication])'
    query = query + date_clause

    params = urllib.request.urlencode({
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "sort": sort,
        "retmode": "json",
    })
    url = f"{PUBMED_ESEARCH_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes-Lab-Analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


@tenacity.retry(
    retry=tenacity.retry_if_exception(_is_pubmed_retryable),
    wait=tenacity.wait_exponential(multiplier=2, min=2, max=30),
    stop=tenacity.stop_after_attempt(5),
    reraise=True,
)
def pubmed_efetch(pmids: list[str]) -> str:
    """
    PubMed efetch：用 PMID 列表抓摘要原文。
    """
    if not pmids:
        return ""
    ids = ",".join(pmids)
    params = urllib.request.urlencode({
        "db": "pubmed",
        "id": ids,
        "rettype": "abstract",
        "retmode": "text",
    })
    url = f"{PUBMED_EFETCH_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes-Lab-Analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")
