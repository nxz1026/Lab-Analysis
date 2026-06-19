#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
literature_filter.py — 对 PubMed 检索结果做 evidence-grading 二次筛选

输入：literature_searcher.py 输出的 literature_results.json
输出：literature_filtered.json（含 grade 字段 + 排序后 top-k）

用法：
    # 手动指定输入输出路径
    python -m lab_analysis.literature_filter --in data/.../literature_results.json --top-k 8

    # pipeline 模式（传入 --id-card 和环境变量 ANALYSIS_TS 自动定位路径）
    ANALYSIS_TS=20260612_185152 python -m lab_analysis.literature_filter --id-card 846552421134373347
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from lab_analysis.utils import WORK_ROOT
from lab_analysis.evidence_grader import (
    GradedPaper,
    ScenarioName,
    TOPIC_KEYWORDS,
    rank_papers,
)


def filter_literature(
    literature_json_path: str | Path,
    scenario: ScenarioName = "differential_diagnosis",
    topic: str = "sepsis_gn_gp",
    top_k: Optional[int] = None,
    output_path: Optional[str | Path] = None,
) -> dict:
    """对 literature_results.json 做 evidence-grading 过滤。

    Args:
        literature_json_path: literature_searcher.py 输出文件
        scenario: 场景权重（early_diagnosis / differential_diagnosis / prognosis）
        topic: 主题关键词库（sepsis_gn_gp / inflammation / rdw）
        top_k: 返回前 k 篇；None 表示全部排序
        output_path: 输出 JSON 路径；None 表示在输入路径同目录加 .filtered.json

    Returns:
        {
            "input_file": ...,
            "scenario": ...,
            "topic": ...,
            "total_papers": N,
            "kept_papers": K,
            "filtered_papers": [ {原paper字段 + grade子字段}, ... ],
            "kicked_summary": { "parse_failed": [...], "offtopic": [...], "low_quality": [...] }
        }
    """
    inp = Path(literature_json_path)
    data = json.loads(inp.read_text(encoding="utf-8"))
    papers = data.get("all_papers", [])

    if not papers:
        return {
            "input_file": str(inp),
            "scenario": scenario,
            "topic": topic,
            "total_papers": 0,
            "kept_papers": 0,
            "filtered_papers": [],
            "kicked_summary": {},
        }

    # 全量打分（不只 top_k）
    from lab_analysis.evidence_grader import grade_paper
    all_graded = [grade_paper(p, scenario=scenario, topic=topic) for p in papers]
    all_graded.sort(key=lambda x: x.score, reverse=True)

    # 截取 top_k
    kept = all_graded if top_k is None else all_graded[:top_k]

    # 拼接原 paper 字段 + grade 子字段
    pmid_to_paper = {p["pmid"]: p for p in papers}
    filtered_papers = []
    for g in kept:
        original = pmid_to_paper.get(g.pmid, {})
        merged = {**original, "grade": g.to_dict()}
        filtered_papers.append(merged)

    # 踢出分类汇总
    kicked = all_graded[len(kept):] if top_k else []
    kicked_summary = _classify_kicked(kicked, pmid_to_paper)

    result = {
        "input_file": str(inp),
        "scenario": scenario,
        "topic": topic,
        "total_papers": len(papers),
        "kept_papers": len(kept),
        "filtered_papers": filtered_papers,
        "kicked_summary": kicked_summary,
    }

    # 输出
    if output_path is None:
        output_path = inp.parent / f"{inp.stem}.filtered.json"
    Path(output_path).write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    result["output_file"] = str(output_path)
    return result


def _classify_kicked(kicked: list[GradedPaper], pmid_to_paper: dict) -> dict:
    """把踢出的论文按踢出原因分类"""
    summary = {"parse_failed": [], "offtopic": [], "low_quality": []}
    for g in kicked:
        original = pmid_to_paper.get(g.pmid, {})
        # 解析失败：缺标题或标题是噪声（IRB/作者列表）
        if not original.get("title") or "approval" in original.get("title", "").lower() \
                or "author" in original.get("title", "").lower()[:30]:
            summary["parse_failed"].append({"pmid": g.pmid, "title": g.title[:60], "score": g.score})
            continue
        # 主题偏移：topic_match 极低
        if g.subscores.get("topic_match", 0) < 0.3:
            summary["offtopic"].append({"pmid": g.pmid, "title": g.title[:60], "score": g.score})
            continue
        # 其它低质量
        summary["low_quality"].append({"pmid": g.pmid, "title": g.title[:60], "score": g.score})
    return summary


def _resolve_input_path(args) -> Path:
    """根据 CLI 参数解析输入 literature_results.json 路径。
    优先级：--in > --id-card（配合 ANALYSIS_TS 环境变量） > 报错
    """
    if args.inp:
        return Path(args.inp)
    if args.id_card:
        raw_ts = os.environ.get("ANALYSIS_TS", "")
        ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or args.id_card)
        lit_dir = WORK_ROOT / "data" / args.id_card / ts / "03_literature"
        candidate = lit_dir / "literature_results.json"
        if not candidate.exists():
            print(f"[ERROR] pipeline 模式下找不到输入文件: {candidate}")
            print(f"  提示：请先运行步骤⑤ literature_searcher，或手动指定 --in")
            sys.exit(1)
        return candidate
    print("[ERROR] 请提供 --in <path> 或 --id-card <deid>")
    sys.exit(1)


def _resolve_output_path(args, inp: Path) -> Path:
    """根据 CLI 参数解析输出路径。"""
    if args.out:
        return Path(args.out)
    return inp.parent / f"{inp.stem}.filtered.json"


def _cli():
    parser = argparse.ArgumentParser(description="文献 evidence-grading 二次筛选")
    parser.add_argument("--in", dest="inp", default=None,
                        help="literature_results.json 路径（与 --id-card 二选一）")
    parser.add_argument("--id-card", default=None,
                        help="脱敏 ID（pipeline 模式，配合 ANALYSIS_TS 环境变量自动定位路径）")
    parser.add_argument("--scenario", default="differential_diagnosis",
                        choices=["early_diagnosis", "differential_diagnosis", "prognosis"])
    parser.add_argument("--topic", default="sepsis_gn_gp", choices=list(TOPIC_KEYWORDS.keys()))
    parser.add_argument("--top-k", type=int, default=None,
                        help="保留前 k 篇；不指定则全部排序但踢出最低分")
    parser.add_argument("--out", default=None, help="输出 JSON 路径")
    args = parser.parse_args()

    inp = _resolve_input_path(args)
    output_path = _resolve_output_path(args, inp)

    result = filter_literature(
        literature_json_path=inp,
        scenario=args.scenario,
        topic=args.topic,
        top_k=args.top_k,
        output_path=output_path,
    )

    print(f"\n=== 文献二次筛选 ===")
    print(f"输入: {result['input_file']}")
    print(f"场景: {result['scenario']} | 主题: {result['topic']}")
    print(f"总数: {result['total_papers']} → 保留: {result['kept_papers']}")
    print(f"输出: {result.get('output_file', 'N/A')}\n")

    print("--- 保留论文 ---")
    for i, p in enumerate(result["filtered_papers"], 1):
        g = p["grade"]
        print(f"  [{i}] {g['tier']} | {g['score']:.3f} | PMID:{p['pmid']} | {p['title'][:80]}")
    print()

    ks = result["kicked_summary"]
    if any(ks.values()):
        print("--- 踢出论文 ---")
        for category, items in ks.items():
            if items:
                print(f"  [{category}] {len(items)} 篇")
                for it in items[:3]:  # 最多展示 3 篇
                    print(f"    - PMID:{it['pmid']} | {it['title'][:60]}")
                if len(items) > 3:
                    print(f"    ... +{len(items) - 3} 篇")


if __name__ == "__main__":
    _cli()