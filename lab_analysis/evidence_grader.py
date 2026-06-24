#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
evidence_grader.py — 论文证据等级打分模块

设计原则：
1. 纯函数化：不调 LLM/MCP，可重复、可单元测试
2. 场景化权重：early_diagnosis / differential_diagnosis / prognosis 三种
3. 可解释：每个分数维度都输出 reason，避免黑盒
4. 不依赖外部：纯本地规则打分

用法：
    from lab_analysis.evidence_grader import grade_paper, rank_papers

    ranked = rank_papers(papers, scenario="differential_diagnosis", top_k=5)
    for p in ranked:
        print(p.tier, p.score, p.title, p.reasons)
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

from . import _log

logger = _log.get_logger(__name__)

# ---------------------------------------------------------------------------
# 样本量评分阈值配置
# ---------------------------------------------------------------------------
# (最小样本数, 得分, 描述后缀)
SAMPLE_SIZE_BANDS: list[tuple[int, float, str]] = [
    (1000, 1.0, "（大样本）"),
    (500, 0.9, ""),
    (200, 0.75, ""),
    (100, 0.65, ""),
    (50, 0.5, "（中等）"),
    (20, 0.35, "（小样本）"),
]
SAMPLE_SIZE_FALLBACK_SCORE: float = 0.25
SAMPLE_SIZE_FALLBACK_LABEL: str = "（极小）"
SAMPLE_SIZE_MIN_YEAR: int = 1900  # 小于此值视为年份而非样本量

# ---------------------------------------------------------------------------
# 场景权重配置
# ---------------------------------------------------------------------------
ScenarioName = Literal["early_diagnosis", "differential_diagnosis", "prognosis"]

SCENARIO_WEIGHTS: dict[str, dict[str, float]] = {
    # 早期诊断：偏重新颖性 + 时效
    "early_diagnosis": {
        "topic_match": 0.35,
        "evidence_level": 0.25,
        "recency": 0.20,
        "sample_size": 0.10,
        "parse_quality": 0.10,
    },
    # 鉴别诊断：偏对比研究 + 样本量
    "differential_diagnosis": {
        "topic_match": 0.30,
        "evidence_level": 0.25,
        "recency": 0.10,
        "sample_size": 0.25,
        "parse_quality": 0.10,
    },
    # 预后：偏证据等级 + 大样本长期
    "prognosis": {
        "topic_match": 0.25,
        "evidence_level": 0.35,
        "recency": 0.10,
        "sample_size": 0.20,
        "parse_quality": 0.10,
    },
}

# ---------------------------------------------------------------------------
# 主题关键词库（topic → 关键词集合）
# ---------------------------------------------------------------------------
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "sepsis_gn_gp": [
        "gram-negative",
        "gram-positive",
        "gn sepsis",
        "gp sepsis",
        "procalcitonin",
        "pct",
        "c-reactive protein",
        "crp",
        "biomarker",
        "differential",
        "distinguish",
        "sepsis",
    ],
    "infection": [
        "infection",
        "infectious",
        "bacterial",
        "viral",
        "pathogen",
        "sepsis",
        "antibiotic",
    ],
    "inflammation": [
        "inflammation",
        "inflammatory",
        "crp",
        "biomarker",
        "cytokine",
        "il-6",
        "tnf",
        "acute phase",
        "interleukin",
    ],
    "biomarker": [
        "biomarker",
        "biological marker",
        "diagnostic marker",
        "prognostic marker",
        "predictive marker",
        "serum marker",
    ],
    "clinical_trial": [
        "clinical trial",
        "randomized controlled trial",
        "rct",
        "phase iii",
        "phase 3",
        "double-blind",
        "placebo-controlled",
    ],
    "meta_analysis": [
        "meta-analysis",
        "systematic review",
        "pooled analysis",
        "evidence synthesis",
        "meta-regression",
    ],
    "cohort_study": [
        "cohort",
        "prospective",
        "longitudinal",
        "follow-up",
        "observational",
        "registry",
    ],
    "rdw": [
        "rdw",
        "red cell distribution width",
        "mortality",
        "prognostic",
        "inflammation",
    ],
}


# ---------------------------------------------------------------------------
# 输出数据结构
# ---------------------------------------------------------------------------
@dataclass
class GradedPaper:
    pmid: str
    title: str
    score: float
    tier: str  # S / A / B / C
    reasons: list[str]
    scenario: str
    subscores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 5 个打分维度（每个独立可测）
# ---------------------------------------------------------------------------
def score_topic_match(paper: dict, topic: str = "sepsis_gn_gp") -> tuple[float, str]:
    """主题匹配度：标题+摘要里命中关键词的比例"""
    keywords = TOPIC_KEYWORDS.get(topic, TOPIC_KEYWORDS["sepsis_gn_gp"])
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    hits = sum(1 for kw in keywords if kw in text)
    # 至少 2 个关键词命中才算相关
    if hits == 0:
        return 0.0, f"主题关键词 0 命中 ({len(keywords)} 关键词库)"
    if hits == 1:
        return 0.3, f"主题关键词 1/{len(keywords)} 命中"
    if hits <= 3:
        return 0.6, f"主题关键词 {hits}/{len(keywords)} 命中"
    if hits <= 5:
        return 0.8, f"主题关键词 {hits}/{len(keywords)} 命中"
    return 1.0, f"主题关键词 {hits}/{len(keywords)} 高命中"


def score_evidence_level(paper: dict) -> tuple[float, str]:
    """证据等级：从标题/摘要推断研究类型"""
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
    # 优先级从高到低
    if re.search(r"\b(meta[-\s]?analysis|systematic\s+review)\b", text):
        return 1.0, "meta-analysis / systematic review"
    if re.search(r"\b(randomized|randomised|rct)\b", text):
        return 0.9, "RCT"
    if re.search(r"\b(cohort|prospective|longitudinal)\b", text):
        return 0.7, "cohort / prospective"
    if re.search(r"\b(case[-\s]?control|retrospective)\b", text):
        return 0.55, "case-control / retrospective"
    if re.search(r"\b(cross[-\s]?sectional)\b", text):
        return 0.5, "cross-sectional"
    if re.search(r"\b(case\s+report)\b", text):
        return 0.3, "case report"
    if re.search(r"\b(review|narrative)\b", text):
        return 0.4, "narrative review"
    # 有 abstract 但未识别出研究类型 → 推测为原创研究
    if paper.get("abstract"):
        return 0.5, "原创研究（未识别具体类型）"
    return 0.2, "无摘要，研究类型未知"


def score_recency(paper: dict) -> tuple[float, str]:
    """时效性：基于发表年份"""
    year_str = paper.get("year", "")
    if not year_str or not year_str.isdigit():
        return 0.3, "年份缺失"
    year = int(year_str)
    current_year = datetime.now().year
    delta = current_year - year
    if delta <= 0:
        return 1.0, f"{year}（当年）"
    if delta == 1:
        return 0.95, f"{year}（1 年前）"
    if delta == 2:
        return 0.85, f"{year}（2 年前）"
    if delta == 3:
        return 0.75, f"{year}（3 年前）"
    if delta <= 5:
        return 0.6, f"{year}（{delta} 年前）"
    if delta <= 10:
        return 0.4, f"{year}（{delta} 年前，偏旧）"
    return 0.2, f"{year}（{delta} 年前，过旧）"


def score_sample_size(paper: dict) -> tuple[float, str]:
    """样本量：从摘要提取最大数字作为样本量估计"""
    abstract = paper.get("abstract", "")
    if not abstract:
        return 0.3, "无摘要无法评估样本量"
    # 匹配所有 2-5 位数字
    nums = [int(n) for n in re.findall(r"\b(\d{2,5})\b", abstract)]
    if not nums:
        return 0.4, "摘要中未提取到样本数字"
    # 取最大数字（通常是患者数/事件数）
    n = max(nums)
    # 排除明显是年份的数字（如 2024, 2023）
    current_year = datetime.now().year
    if SAMPLE_SIZE_MIN_YEAR <= n <= current_year + 10:
        sorted_nums = sorted(set(nums), reverse=True)
        n = sorted_nums[1] if len(sorted_nums) > 1 else 50
    for threshold, score, label in SAMPLE_SIZE_BANDS:
        if n >= threshold:
            return score, f"n≈{n}{label}"
    return SAMPLE_SIZE_FALLBACK_SCORE, f"n≈{n}{SAMPLE_SIZE_FALLBACK_LABEL}"


def score_parse_quality(paper: dict) -> tuple[float, str]:
    """解析质量：标题/摘要/期刊/年份是否齐全"""
    title = bool(paper.get("title", "").strip())
    abstract = bool(paper.get("abstract", "").strip())
    journal = bool(paper.get("journal", "").strip())
    year = bool(paper.get("year", "").strip())
    missing = []
    if not title:
        missing.append("标题")
    if not abstract:
        missing.append("摘要")
    if not journal:
        missing.append("期刊")
    if not year:
        missing.append("年份")
    if not missing:
        return 1.0, "四要素齐全"
    if len(missing) == 1:
        return 0.7, f"缺 {missing[0]}"
    if len(missing) == 2:
        return 0.5, f"缺 {missing[0]}+{missing[1]}"
    return 0.3, f"缺 {'+'.join(missing)}"


# ---------------------------------------------------------------------------
# 综合打分
# ---------------------------------------------------------------------------
def _tier_from_score(score: float) -> str:
    if score >= 0.75:
        return "S"
    if score >= 0.60:
        return "A"
    if score >= 0.45:
        return "B"
    return "C"


def grade_paper(
    paper: dict, scenario: ScenarioName = "differential_diagnosis", topic: str = "sepsis_gn_gp"
) -> GradedPaper:
    """对单篇论文打分。返回 GradedPaper。

    Parameters
    ----------
    paper : dict
        PubMed 论文字段字典。期望包含键：
        - pmid : str
        - title : str
        - abstract : str（可选）
        - year : str|int（可选）
        - publication_types : list[str]（可选）
        - 期刊名 / 作者 / 等其他字段（可选）
    scenario : {"early_diagnosis","differential_diagnosis","prognosis"}
        场景权重。不同场景下同篇论文分不同。
    topic : str
        主题词库（见 TOPIC_KEYWORDS 键）。决定 topic_match 维度的命中关键词集合。

    Returns
    -------
    GradedPaper
        含 pmid / title / score / tier / reasons / subscores。

    积分规则
    --------
    5 维独立打分 → 按 SCENARIO_WEIGHTS[scenario] 加权求和 → tier=S/A/B/C
    """
    if not isinstance(paper, dict):
        return GradedPaper(
            pmid="",
            title="",
            score=0.0,
            tier="C",
            reasons=["论文数据不是 dict 类型"],
            scenario=scenario,
            subscores={k: 0.0 for k in SCENARIO_WEIGHTS[scenario]},
        )
    weights = SCENARIO_WEIGHTS[scenario]

    # 5 维打分
    tm_score, tm_reason = score_topic_match(paper, topic)
    ev_score, ev_reason = score_evidence_level(paper)
    rc_score, rc_reason = score_recency(paper)
    ss_score, ss_reason = score_sample_size(paper)
    pq_score, pq_reason = score_parse_quality(paper)

    subscores = {
        "topic_match": tm_score,
        "evidence_level": ev_score,
        "recency": rc_score,
        "sample_size": ss_score,
        "parse_quality": pq_score,
    }
    reasons = [
        f"主题匹配({weights['topic_match']:.2f}): {tm_reason}",
        f"证据等级({weights['evidence_level']:.2f}): {ev_reason}",
        f"时效性({weights['recency']:.2f}): {rc_reason}",
        f"样本量({weights['sample_size']:.2f}): {ss_reason}",
        f"解析质量({weights['parse_quality']:.2f}): {pq_reason}",
    ]

    # 加权汇总
    total = sum(subscores[k] * weights[k] for k in weights)
    return GradedPaper(
        pmid=paper.get("pmid", ""),
        title=paper.get("title", ""),
        score=round(total, 4),
        tier=_tier_from_score(total),
        reasons=reasons,
        scenario=scenario,
        subscores=subscores,
    )


def rank_papers(
    papers: list[dict],
    scenario: ScenarioName = "differential_diagnosis",
    topic: str = "sepsis_gn_gp",
    top_k: int = 5,
) -> list[GradedPaper]:
    """批量打分并按 score 倒序排，返 top_k。

    Parameters
    ----------
    papers : list[dict]
        多篇 PubMed 论文字典列表。
    scenario : {"early_diagnosis","differential_diagnosis","prognosis"}
        场景权重，同 grade_paper。
    topic : str
        主题词库（见 TOPIC_KEYWORDS 键），同 grade_paper。
    top_k : int, default 5
        保留前 k 名。None 或 -1 表示不截取。

    Returns
    -------
    list[GradedPaper]
        按 score 降序排列。tier 依次为 S/A/B/C。

    说明
    ----
    - 同分时按 pmid 字典序排序，保证可重复。
    - 不会剔除原始论文记录；过滤逻辑在 literature_filter.filter_literature。
    """
    graded = [grade_paper(p, scenario, topic) for p in papers]
    graded.sort(key=lambda x: (-x.score, x.pmid))
    return graded[:top_k]


# ---------------------------------------------------------------------------
# CLI 入口（便于临时跑）
# ---------------------------------------------------------------------------
def _cli():
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="论文证据等级打分")
    parser.add_argument("--in", dest="inp", required=True, help="输入 JSON 路径（含 all_papers）")
    parser.add_argument(
        "--scenario", default="differential_diagnosis", choices=list(SCENARIO_WEIGHTS.keys())
    )
    parser.add_argument("--topic", default="sepsis_gn_gp", choices=list(TOPIC_KEYWORDS.keys()))
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--out", default=None, help="输出 JSON 路径")
    args = parser.parse_args()

    data = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    papers = data.get("all_papers", data) if isinstance(data, dict) else data

    ranked = rank_papers(papers, scenario=args.scenario, topic=args.topic, top_k=args.top_k)

    logger.info(f"\n=== Top-{args.top_k} ({args.scenario}) ===\n")
    for i, p in enumerate(ranked, 1):
        logger.info(f"[{i}] {p.tier} | score={p.score:.3f} | PMID:{p.pmid}")
        logger.info(f"    Title: {p.title[:120]}")
        for r in p.reasons:
            logger.info(f"      - {r}")
        logger.info()

    if args.out:
        Path(args.out).write_text(
            json.dumps([p.to_dict() for p in ranked], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"[OK] Saved to {args.out}")


if __name__ == "__main__":
    _cli()
