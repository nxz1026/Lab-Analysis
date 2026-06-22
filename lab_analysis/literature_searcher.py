#!/usr/bin/env python3
"""
文献检索模块 — 对接 PubMed E-utilities
用法: python literature_searcher.py [--topic TOPIC] [--n N] [--out JSON]
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from lab_analysis.utils import api_retry_decorator

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))

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

# 指标 → PubMed 查询模板映射（用于自动生成搜索策略）
# 键为 analysis_results.json 中 abnormal_summary 的指标名
# 值为 (condition_fn, query_template) 元组；condition_fn(results) 返回 bool
_METRIC_QUERY_RULES: list[tuple[str, callable, str]] = [
    (
        "hs-CRP",
        lambda r: "hs-CRP" in r.get("abnormal_summary", {}),
        '"chronic pancreatitis" AND ("hs-CRP" OR "high-sensitivity CRP")',
    ),
    (
        "RDW-SD",
        lambda r: (
            "RDW-SD" in r.get("abnormal_summary", {}) or "RDW-CV" in r.get("abnormal_summary", {})
        ),
        '"red cell distribution width" "chronic pancreatitis" prognostic',
    ),
    (
        "WBC",
        lambda r: "WBC" in r.get("abnormal_summary", {}),
        "leukocytosis chronic pancreatitis biomarker",
    ),
    (
        "CRP",
        lambda r: (
            "CRP" in r.get("abnormal_summary", {}) and "hs-CRP" not in r.get("abnormal_summary", {})
        ),
        '"C-reactive protein" pancreatitis severity biomarker',
    ),
    (
        "急性期",
        lambda r: "急性期" in r.get("inflammation_classification", {}).get("labels", []),
        '"acute pancreatitis" biomarker PCT CRP severity',
    ),
    (
        "NEUT#",
        lambda r: "NEUT#" in r.get("abnormal_summary", {}),
        "neutrophilia pancreatitis infection biomarker",
    ),
    (
        "PCT",
        lambda r: "PCT" in r.get("abnormal_summary", {}),
        "procalcitonin pancreatitis infection biomarker",
    ),
]


def auto_generate_queries(analysis_results: dict) -> dict:
    """根据分析结果中的异常指标自动生成 PubMed 搜索策略。

    Args:
        analysis_results: _compute_stats() 产出的 results dict。
            至少需要 ``abnormal_summary`` 和 ``inflammation_classification`` 两个键。

    Returns:
        ``{strategy_name: {"query": str, "retmax": int, "sort": str}, ...}``
        空 dict 表示无异常指标可生成。
    """
    queries = {}
    for name, condition, query in _METRIC_QUERY_RULES:
        if condition(analysis_results):
            auto_name = f"auto_{name.lower().replace('-', '_').replace('#', 'n')}"
            queries[auto_name] = {
                "query": query,
                "retmax": 6,
                "sort": "relevance",
            }
    return queries


@api_retry_decorator(max_attempts=3, min_wait=1.0, max_wait=20.0, description="PubMed ESearch")
def esearch(query: str, retmax: int = 8, sort: str = "relevance", date_filter: str = "5") -> dict:
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
    req = urllib.request.Request(url, headers={"User-Agent": "Hermes-Lab-Analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


@api_retry_decorator(max_attempts=3, min_wait=1.0, max_wait=20.0, description="PubMed EFetch")
def efetch(pmids: list[str]) -> str:
    """efetch: 用 PMID 抓摘要文本"""
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
        raw_blocks = re.split(r"\n(?=\d+\. [A-Z])", raw_text)
        for idx, block in enumerate(raw_blocks):
            block = block.strip()
            if not block:
                continue
            lines = block.split("\n")
            pmid = pmids[idx] if idx < len(pmids) else ""
            papers.append(_parse_one_paper(lines, pmid))
        return papers

    # 多篇格式：定位所有 PMID 行，用它们做边界
    # 找所有 "PMID: NNN" 的行首位置
    pmid_positions = [m.start() for m in re.finditer(r"^PMID:", raw_text, re.MULTILINE)]

    if not pmid_positions:
        return papers

    for i, pos in enumerate(pmid_positions):
        # 文章内容区域：上一 PMID 行之后 到 本 PMID 行之前
        start = pmid_positions[i - 1] + len(raw_text.split("\n")[i - 1]) + 1 if i > 0 else 0
        end = pos
        content = raw_text[start:end].strip()
        lines = content.split("\n")
        pmid_m = re.search(r"PMID:\s*(\d+)", raw_text[pos : pos + 30])
        pmid = pmid_m.group(1) if pmid_m else (pmids[i] if i < len(pmids) else "")
        papers.append(_parse_one_paper(lines, pmid))

    return papers


def _parse_one_paper(lines: list[str], pmid: str) -> dict:
    """从单篇的 lines 列表 + pmid 提取一篇论文的各字段。"""
    # 年份：找第一个 19xx/20xx
    year = ""
    for line in lines[:10]:
        m = re.search(r"\b(19|20)\d{2}\b", line)
        if m:
            year = m.group(0)
            break

    # 期刊名
    journal = ""
    # 单篇序号格式：第一行 "N. Journal. YYYY Mon;..."
    if lines:
        first = re.sub(r"^\d+\.\s*", "", lines[0].strip())
        m_j = re.match(r"^([^.]+\.[A-Za-z\s]+\d{4})", first)
        if m_j:
            journal = m_j.group(1).strip().rstrip(".")
    # 多篇格式：DOI/PMID 行之前的第一行
    if not journal:
        for i, line in enumerate(lines[:10]):
            ls = line.strip()
            if re.match(r"^(doi:|DOI:|PMID:|pmid:)", ls):
                cand = lines[i - 1].strip().rstrip(".").rstrip(";").strip()
                if 3 < len(cand) < 120 and not cand.startswith("Copyright"):
                    journal = cand
                    break

    # 标题（摘要段之后第一行超长句）
    title = ""
    for i, line in enumerate(lines):
        ls = line.strip()
        if (
            i > 0
            and len(ls) > 30
            and not ls.startswith("Author")
            and not ls.startswith("(")
            and not ls.startswith("doi")
            and not ls.startswith("DOI")
            and not ls.startswith("PMID")
            and not ls.startswith("PMCID")
            and not ls.startswith("Conflict")
            and "Author information" not in ls
            and ls[0].isupper()
        ):
            title = ls
            break

    # 摘要
    abstract_parts = []
    in_abs = False
    for line in lines:
        ls = line.strip()
        if re.match(
            r"^(BACKGROUND:|METHODS:|RESULTS:|CONCLUSIONS:|Abstract |"
            r"PURPOSE OF REVIEW:|PURPOSE:|SUMMARY:)",
            ls,
        ):
            in_abs = True
            abstract_parts.append(ls)
        elif in_abs:
            if ls == "" and len(abstract_parts) > 2:
                break
            if re.match(r"^(doi:|DOI:|PMID:|PMCID:|Copyright|\(c\))", ls):
                break
            if len(ls) > 10:
                abstract_parts.append(ls)
    abstract = " ".join(abstract_parts)

    return {"pmid": pmid, "title": title, "abstract": abstract, "year": year, "journal": journal}


def search_strategy(
    strategy_name: str, retmax: int, date_filter: str = "5", strategies_source: dict | None = None
) -> dict:
    """执行单个检索策略"""
    strategies = strategies_source if strategies_source is not None else SEARCH_STRATEGIES
    if strategy_name not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    cfg = strategies[strategy_name]
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
    parser.add_argument(
        "--topic", default="all", help="检索主题：all（默认）/ inflammation / rdw_prognostic 等"
    )
    parser.add_argument("--n", type=int, default=6, help="每策略返回 PMID 数")
    parser.add_argument(
        "--years", type=int, default=5, help="限制近 N 年内的文献（默认5，设为0则不过滤）"
    )
    parser.add_argument("--id-card", default=None, help="脱敏ID(由 pipeline 传入)")
    parser.add_argument("--out", default=None, help="输出 JSON 路径")
    parser.add_argument(
        "--auto-queries", action="store_true", help="根据异常指标自动生成搜索词追加到检索策略中"
    )
    parser.add_argument(
        "--analysis-results",
        default=None,
        help="analysis_results.json 路径（--auto-queries 时需指定）",
    )
    args = parser.parse_args()

    if args.id_card:
        import os

        raw_ts = os.environ.get("ANALYSIS_TS", "")
        ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or args.id_card)
        lit_dir = WORK_ROOT / "data" / args.id_card / ts / "03_literature"
        args.out = args.out or str(lit_dir / "literature_results.json")
        # pipeline 模式下自动定位 analysis_results.json
        if args.auto_queries and not args.analysis_results:
            analyzed_dir = WORK_ROOT / "data" / args.id_card / ts / "02_analyzed"
            candidate = analyzed_dir / "analysis_results.json"
            if candidate.exists():
                args.analysis_results = str(candidate)

    # 自动生成搜索策略
    if args.auto_queries and args.analysis_results:
        ana_path = Path(args.analysis_results)
        if ana_path.exists():
            ana_data = json.loads(ana_path.read_text(encoding="utf-8"))
            auto_strategies = auto_generate_queries(ana_data)
            if auto_strategies:
                print(f"[AUTO] 根据异常指标自动生成 {len(auto_strategies)} 个搜索策略:")
                for name, cfg in auto_strategies.items():
                    print(f"       {name}: {cfg['query']}")
                # 合并到 SEARCH_STRATEGIES（不修改全局，只作用于本次）
                merged_strategies = {**SEARCH_STRATEGIES, **auto_strategies}
            else:
                print("[AUTO] 未发现异常指标，仅使用默认搜索策略")
                merged_strategies = SEARCH_STRATEGIES
        else:
            print(f"[WARNING] --analysis-results 文件不存在: {ana_path}")
            merged_strategies = SEARCH_STRATEGIES
    else:
        merged_strategies = SEARCH_STRATEGIES

    all_topics = list(merged_strategies.keys())
    topics = all_topics if args.topic == "all" else [args.topic]
    for t in topics:
        if t not in merged_strategies:
            print(f"Unknown topic: {t}")
            sys.exit(1)

    results = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "searches": [],
        "all_papers": [],
    }

    date_filter = str(args.years)
    for topic in topics:
        sr = search_strategy(
            topic, retmax=args.n, date_filter=date_filter, strategies_source=merged_strategies
        )
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
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 生成 Markdown 版
    md_path = str(Path(out_path).with_suffix(".md"))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 文献检索结果\n\n")
        f.write(
            f"**检索时间**: {results['generated']}  |  **唯一文献数**: {results['total_unique_papers']}\n\n"
        )
        f.write("## 检索策略\n\n")
        for sr in results["searches"]:
            f.write(
                f"- **[{sr['strategy']}]** {sr['total_results']} total → {sr['pmids_returned']} returned\n"
            )
        f.write("\n## 文献列表\n\n")
        for i, p in enumerate(results["all_papers"], 1):
            f.write(f"### {i}. {p['title']}\n\n")
            f.write(
                f"- **PMID**: {p['pmid']}  |  **Year**: {p.get('year', 'N/A')}  |  **Journal**: {p.get('journal', 'N/A')}\n"
            )
            f.write(f"- **来源**: {p.get('source', 'N/A')}  |  [PubMed链接]({p.get('url', '')})\n")
            abstract = p.get("abstract", "")
            if abstract:
                f.write(f"- **摘要**: {abstract}\n")
            f.write("\n")
    print(f"[OK] Markdown 已保存: {md_path}")

    print(f"\n[DONE] 检索完成: {results['total_unique_papers']} 篇唯一文献")
    print(f"   输出: {out_path}")
    for sr in results["searches"]:
        print(
            f"   [{sr['strategy']}] {sr['total_results']} total → {sr['pmids_returned']} returned"
        )


if __name__ == "__main__":
    main()
