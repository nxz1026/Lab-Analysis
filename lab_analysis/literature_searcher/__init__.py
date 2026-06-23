"""literature_searcher — 对接 PubMed E-utilities 的文献检索模块。

用法:
    python -m lab_analysis.literature_searcher [--topic TOPIC] [--n N] [--out JSON]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .. import _log
from .parser import parse_papers
from .pubmed import efetch, esearch
from .strategies import SEARCH_STRATEGIES, auto_generate_queries

logger = _log.get_logger(__name__)

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))

__all__ = [
    "esearch",
    "efetch",
    "parse_papers",
    "auto_generate_queries",
    "SEARCH_STRATEGIES",
    "search_strategy",
    "WORK_ROOT",
]


def search_strategy(
    strategy_name: str,
    retmax: int,
    date_filter: str = "5",
    strategies_source: dict | None = None,
) -> dict:
    """执行单个检索策略。"""
    strategies = strategies_source if strategies_source is not None else SEARCH_STRATEGIES
    if strategy_name not in strategies:
        raise ValueError(f"Unknown strategy: {strategy_name}")

    cfg = strategies[strategy_name]
    logger.info(f"  Searching [{strategy_name}]: {cfg['query']}  [近{date_filter}年]")

    result = esearch(cfg["query"], retmax=retmax, sort=cfg["sort"], date_filter=date_filter)
    count = int(result.get("esearchresult", {}).get("count", 0))
    pmids = result["esearchresult"]["idlist"]

    papers: list[dict] = []
    if pmids:
        time.sleep(1.2)
        raw_text = efetch(pmids)
        papers = parse_papers(raw_text, pmids)
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


def main() -> None:
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
        "--auto-queries",
        action="store_true",
        help="根据异常指标自动生成搜索词追加到检索策略中",
    )
    parser.add_argument(
        "--analysis-results",
        default=None,
        help="analysis_results.json 路径（--auto-queries 时需指定）",
    )
    args = parser.parse_args()

    if args.id_card:
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
                logger.info(f"[AUTO] 根据异常指标自动生成 {len(auto_strategies)} 个搜索策略:")
                for name, cfg in auto_strategies.items():
                    logger.info(f"       {name}: {cfg['query']}")
                merged_strategies = {**SEARCH_STRATEGIES, **auto_strategies}
            else:
                logger.info("[AUTO] 未发现异常指标，仅使用默认搜索策略")
                merged_strategies = SEARCH_STRATEGIES
        else:
            logger.info(f"[WARNING] --analysis-results 文件不存在: {ana_path}")
            merged_strategies = SEARCH_STRATEGIES
    else:
        merged_strategies = SEARCH_STRATEGIES

    all_topics = list(merged_strategies.keys())
    topics = all_topics if args.topic == "all" else [args.topic]
    for t in topics:
        if t not in merged_strategies:
            logger.info(f"Unknown topic: {t}")
            sys.exit(1)

    results: dict = {
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
    seen: set = set()
    unique: list[dict] = []
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
            f"**检索时间**: {results['generated']}  |  "
            f"**唯一文献数**: {results['total_unique_papers']}\n\n"
        )
        f.write("## 检索策略\n\n")
        for sr in results["searches"]:
            f.write(
                f"- **[{sr['strategy']}]** "
                f"{sr['total_results']} total → {sr['pmids_returned']} returned\n"
            )
        f.write("\n## 文献列表\n\n")
        for i, p in enumerate(results["all_papers"], 1):
            f.write(f"### {i}. {p['title']}\n\n")
            f.write(
                f"- **PMID**: {p['pmid']}  |  "
                f"**Year**: {p.get('year', 'N/A')}  |  "
                f"**Journal**: {p.get('journal', 'N/A')}\n"
            )
            f.write(f"- **来源**: {p.get('source', 'N/A')}  |  [PubMed链接]({p.get('url', '')})\n")
            abstract = p.get("abstract", "")
            if abstract:
                f.write(f"- **摘要**: {abstract}\n")
            f.write("\n")
    logger.info(f"[OK] Markdown 已保存: {md_path}")

    logger.info(f"\n[DONE] 检索完成: {results['total_unique_papers']} 篇唯一文献")
    logger.info(f"   输出: {out_path}")
    for sr in results["searches"]:
        print(
            f"   [{sr['strategy']}] {sr['total_results']} total → {sr['pmids_returned']} returned"
        )


if __name__ == "__main__":
    main()
