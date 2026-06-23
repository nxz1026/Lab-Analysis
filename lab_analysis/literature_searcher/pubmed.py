"""literature_searcher.pubmed — PubMed E-utilities API 客户端。"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime

from lab_analysis.utils import api_retry_decorator

_USER_AGENT = "Hermes-Lab-Analyzer/1.0"


@api_retry_decorator(max_attempts=3, min_wait=1.0, max_wait=20.0, description="PubMed ESearch")
def esearch(query: str, retmax: int = 8, sort: str = "relevance", date_filter: str = "5") -> dict:
    """esearch: 搜索 PMID 列表。

    Args:
        date_filter: 年份数，默认 5 即近 5 年。设为 0 则不过滤。
    """
    # 近 N 年过滤：Date - Publication 字段限制
    if date_filter and int(date_filter) > 0:
        n_years_ago = datetime.now().year - int(date_filter)
        date_clause = f' AND ("{n_years_ago}"[Date - Publication] : "2099"[Date - Publication])'
        query = query + date_clause

    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "term": query,
            "retmax": retmax,
            "sort": sort,
            "retmode": "json",
        }
    )
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
        return json.loads(resp.read())


@api_retry_decorator(max_attempts=3, min_wait=1.0, max_wait=20.0, description="PubMed EFetch")
def efetch(pmids: list[str]) -> str:
    """efetch: 用 PMID 抓摘要文本。"""
    if not pmids:
        return ""
    ids = ",".join(pmids)
    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "id": ids,
            "rettype": "abstract",
            "retmode": "text",
        }
    )
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})  # noqa: S310
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")
