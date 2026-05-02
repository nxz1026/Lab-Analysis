#!/usr/bin/env python3
"""
文献检索模块 — 对接 PubMed E-utilities
用法: python literature_searcher.py [--topic TOPIC] [--n N] [--out JSON]
"""

import json
import sys
import urllib.request
import urllib.parse
import time
import re
from datetime import datetime

# ---------------------------------------------------------------------------
# 检索策略配置
# ---------------------------------------------------------------------------
SEARCH_STRATEGIES = {
    "inflammation": {
        "query": "inflammation biomarker CRP review",
        "retmax": 8,
        "sort": "relevance",
    },
    "rdw_prognostic": {
        "query": "red cell distribution width inflammation biomarker review",
        "retmax": 8,
        "sort": "relevance",
    },
    "procalcitonin_sepsis": {
        "query": "procalcitonin CRP sepsis diagnosis meta-analysis",
        "retmax": 8,
        "sort": "relevance",
    },
    "crp_wbc_dissociation": {
        "query": "CRP WBC dissociation sepsis",
        "retmax": 6,
        "sort": "relevance",
    },
    "chronic_pancreatitis": {
        "query": "chronic pancreatitis inflammation biomarker",
        "retmax": 6,
        "sort": "relevance",
    },
    "monocyte_inflammation": {
        "query": "monocyte C-reactive protein acute inflammation",
        "retmax": 6,
        "sort": "relevance",
    },
    "rdw_mortality": {
        "query": "RDW systemic inflammation mortality prognostic",
        "retmax": 6,
        "sort": "relevance",
    },
    "sepsis_gram_negative_positive": {
        "query": "procalcitonin CRP gram-negative gram-positive sepsis",
        "retmax": 6,
        "sort": "relevance",
    },
}


def esearch(query: str, retmax: int = 8, sort: str = "relevance",
             date_filter: str = "5") -> dict:
    """esearch: 搜索 PMID 列表

    Args:
        date_filter: 年份数，默认5即近5年。设为0则不过滤。
    """
    import urllib.parse
    # 近 N 年过滤：Date - Publication 字段限制
    if date_filter and int(date_filter) > 0:
        n_years_ago = datetime.now().year - int(date_filter)
        date_clause = f' AND ("{n_years_ago}"[Date - Publication] : "2099"[Date - Publication])'
        query = query + date_clause

    params = urllib.parse.urlencode({
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "sort": sort,
        "retmode": "json",
    })
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes-Lab-Analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def efetch(pmids: list[str]) -> str:
    """efetch: 用 PMID 抓摘要文本"""
    if not pmids:
        return ""
    ids = ",".join(pmids)
    params = urllib.parse.urlencode({
        "db": "pubmed",
        "id": ids,
        "rettype": "abstract",
        "retmode": "text",
    })
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes-Lab-Analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_papers(raw_text: str, pmids: list[str] = None) -> list[dict]:
    """解析 efetch 原始文本为结构化论文列表

    提取字段：pmid, title, abstract, year, journal

    efetch rettype=abstract 实际返回格式（两种）：
    - 单篇：`1. Journal. YYYY...` 开篇，无 PMID 行
    - 多篇：`内容\n\nPMID: xxx\n内容\nPMID: yyy\n内容\nPMID: zzz`，
      即 article content 后紧跟一个空行再接 "PMID: xxx"，中间无换行分隔符

    解析策略：先找到所有 "PMID: N" 的位置，用它来划分文章内容边界，
    每篇内容 = 前一个 PMID 位置之后 到 当前 PMID 位置之前 的文本。
    """
    pmids = pmids or []
    papers = []

    if "\nPMID:" not in raw_text:
        # 单篇/序号格式：按 "\n(?=\d+\. [A-Z])" 分隔
        raw_blocks = re.split(r'\n(?=\d+\. [A-Z])', raw_text)
        for idx, block in enumerate(raw_blocks):
            block = block.strip()
            if not block:
                continue
            lines = block.split('\n')
            pmid = pmids[idx] if idx < len(pmids) else ""
            papers.append(_parse_one_paper(lines, pmid))
        return papers

    # 多篇格式：定位所有 PMID 行，用它们做边界
    # 找所有 "PMID: NNN" 的行首位置
    pmid_positions = [m.start() for m in re.finditer(r'^PMID:', raw_text, re.MULTILINE)]

    if not pmid_positions:
        return papers

    for i, pos in enumerate(pmid_positions):
        # 文章内容区域：上一 PMID 行之后 到 本 PMID 行之前
        start = pmid_positions[i - 1] + len(raw_text.split('\n')[i - 1]) + 1 \
            if i > 0 else 0
        end = pos
        content = raw_text[start:end].strip()
        lines = content.split('\n')
        pmid_m = re.search(r'PMID:\s*(\d+)', raw_text[pos:pos + 30])
        pmid = pmid_m.group(1) if pmid_m else (pmids[i] if i < len(pmids) else "")
        papers.append(_parse_one_paper(lines, pmid))

    return papers


def _parse_one_paper(lines: list[str], pmid: str) -> dict:
    """从单篇的 lines 列表 + pmid 提取一篇论文的各字段。"""
    # 年份：找第一个 19xx/20xx
    year = ""
    for line in lines[:10]:
        m = re.search(r'\b(19|20)\d{2}\b', line)
        if m:
            year = m.group(0)
            break

    # 期刊名
    journal = ""
    # 单篇序号格式：第一行 "N. Journal. YYYY Mon;..."
    if lines:
        first = re.sub(r'^\d+\.\s*', '', lines[0].strip())
        m_j = re.match(r'^([^.]+\.[A-Za-z\s]+\d{4})', first)
        if m_j:
            journal = m_j.group(1).strip().rstrip('.')
    # 多篇格式：DOI/PMID 行之前的第一行
    if not journal:
        for i, line in enumerate(lines[:10]):
            ls = line.strip()
            if re.match(r'^(doi:|DOI:|PMID:|pmid:)', ls):
                cand = lines[i - 1].strip().rstrip('.').rstrip(';').strip()
                if 3 < len(cand) < 120 and not cand.startswith('Copyright'):
                    journal = cand
                    break

    # 标题（摘要段之后第一行超长句）
    title = ""
    for i, line in enumerate(lines):
        ls = line.strip()
        if (i > 0 and len(ls) > 30
                and not ls.startswith('Author')
                and not ls.startswith('(')
                and not ls.startswith('doi') and not ls.startswith('DOI')
                and not ls.startswith('PMID') and not ls.startswith('PMCID')
                and not ls.startswith('Conflict')
                and 'Author information' not in ls
                and ls[0].isupper()):
            title = ls
            break

    # 摘要
    abstract_parts = []
    in_abs = False
    for line in lines:
        ls = line.strip()
        if re.match(r'^(BACKGROUND:|METHODS:|RESULTS:|CONCLUSIONS:|Abstract |'
                     r'PURPOSE OF REVIEW:|PURPOSE:|SUMMARY:)', ls):
            in_abs = True
            abstract_parts.append(ls)
        elif in_abs:
            if ls == '' and len(abstract_parts) > 2:
                break
            if re.match(r'^(doi:|DOI:|PMID:|PMCID:|Copyright|\(c\))', ls):
                break
            if len(ls) > 10:
                abstract_parts.append(ls)
    abstract = ' '.join(abstract_parts)[:1000]

    return {"pmid": pmid, "title": title, "abstract": abstract,
            "year": year, "journal": journal}


def search_strategy(strategy_name: str, retmax: int, date_filter: str = "5") -> dict:
    """执行单个检索策略"""
    if strategy_name not in SEARCH_STRATEGIES:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    cfg = SEARCH_STRATEGIES[strategy_name]
    print(f"  Searching [{strategy_name}]: {cfg['query']}  [近{date_filter}年]")

    result = esearch(cfg["query"], retmax=retmax, sort=cfg["sort"], date_filter=date_filter)
    count = int(result.get("esearchresult", {}).get("count", 0))
    pmids = result["esearchresult"]["idlist"]

    papers = []
    if pmids:
        time.sleep(1.2)
        raw_text = efetch(pmids)
        papers = parse_papers(raw_text, pmids)  # <-- 传入 pmids 用于单篇解析
        for p in papers:
            p["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/"
            p["source"] = strategy_name

    return {
        "strategy": strategy_name,
        "query": cfg["query"],
        "total_results": count,
        "pmids_returned": len(pmids),
        "papers": papers,
    }


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="PubMed 文献检索")
    parser.add_argument("--topic", default="all",
                        help="检索主题：all（默认）/ inflammation / rdw_prognostic 等")
    parser.add_argument("--n", type=int, default=6, help="每策略返回 PMID 数")
    parser.add_argument("--years", type=int, default=5,
                        help="限制近 N 年内的文献（默认5，设为0则不过滤）")
    parser.add_argument("--patient-id", default=None, help="诊疗卡号，设置后默认输出到 data/{patient-id}/")
    parser.add_argument("--out", default=None, help="输出 JSON 路径")
    args = parser.parse_args()

    if args.patient_id:
        import os
        ts = os.environ.get("ANALYSIS_TS", args.patient_id)
        default_out = Path.home() / "wiki" / "data" / ts / "literature_results.json"
        args.out = args.out or str(default_out)

    all_topics = list(SEARCH_STRATEGIES.keys())
    topics = all_topics if args.topic == "all" else [args.topic]
    for t in topics:
        if t not in SEARCH_STRATEGIES:
            print(f"Unknown topic: {t}")
            sys.exit(1)

    results = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "searches": [],
        "all_papers": [],
    }

    date_filter = str(args.years)
    for topic in topics:
        sr = search_strategy(topic, retmax=args.n, date_filter=date_filter)
        results["searches"].append(sr)
        results["all_papers"].extend(sr["papers"])

    # 去重
    seen = set()
    unique = []
    for p in results["all_papers"]:
        if p["pmid"] not in seen:
            seen.add(p["pmid"])
            unique.append(p)
    results["all_papers"] = unique
    results["total_unique_papers"] = len(unique)

    out_path = args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 检索完成: {results['total_unique_papers']} 篇唯一文献")
    print(f"   输出: {out_path}")
    for sr in results["searches"]:
        print(f"   [{sr['strategy']}] {sr['total_results']} total → {sr['pmids_returned']} returned")


if __name__ == "__main__":
    main()
