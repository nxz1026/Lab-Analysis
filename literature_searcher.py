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


def parse_papers(raw_text: str) -> list[dict]:
    """解析 efetch 原始文本为结构化论文列表

    提取字段：pmid, title, abstract, year, journal
    """
    blocks = re.split(r'\n(?=PMID:)', raw_text)
    papers = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        pmid_m = re.search(r'PMID:\s*(\d+)', block)
        if not pmid_m:
            continue
        pmid = pmid_m.group(1)
        lines = block.split('\n')

        # 提取年份（格式：2024 Jan; / 2024 Mar 15; / 2024;）
        year = ""
        year_m = re.search(r'\b(19|20)\d{2}\b', block)
        if year_m:
            year = year_m.group(0)

        # 提取期刊名（DOI 行之前的第一行通常是期刊缩写）
        journal = ""
        doi_idx = -1
        for i, line in enumerate(lines):
            if re.match(r'^(doi:|DOI:)', line.strip()):
                doi_idx = i
                break
        if doi_idx > 3:
            # 取 DOI 行之前、非标题的那一行
            candidate = lines[doi_idx - 1].strip().rstrip('.').rstrip(';').strip()
            if 3 < len(candidate) < 100 and not candidate.startswith('Copyright'):
                journal = candidate

        # 提取标题
        title = ""
        for i, line in enumerate(lines):
            line = line.strip()
            if (i > 0 and len(line) > 30 and
                not line.startswith('Author') and
                not line.startswith('(') and
                not line.startswith('doi') and
                not line.startswith('DOI') and
                not line.startswith('PMID') and
                not line.startswith('PMCID') and
                not line.startswith('Conflict') and
                'Author information' not in line and
                line[0].isupper()):
                title = line
                break

        # 提取摘要
        abstract_parts = []
        in_abstract = False
        for line in lines:
            ls = line.strip()
            if re.match(r'^(BACKGROUND:|METHODS:|RESULTS:|CONCLUSIONS:|Abstract |PURPOSE OF REVIEW:|PURPOSE:|SUMMARY:)', ls):
                in_abstract = True
                abstract_parts.append(ls)
            elif in_abstract:
                if ls == '' and len(abstract_parts) > 2:
                    break
                if re.match(r'^(doi:|DOI:|PMID:|PMCID:|Copyright|\(c\))', ls):
                    break
                if len(ls) > 10:
                    abstract_parts.append(ls)
        abstract = ' '.join(abstract_parts)[:1000]
        papers.append({
            "pmid": pmid, "title": title, "abstract": abstract,
            "year": year, "journal": journal,
        })
    return papers


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
        papers = parse_papers(raw_text)
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
