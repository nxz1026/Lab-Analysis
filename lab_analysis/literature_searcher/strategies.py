"""literature_searcher.strategies — 检索策略配置 + 自动生成。"""

from __future__ import annotations

from collections.abc import Callable

# 检索策略配置
SEARCH_STRATEGIES: dict[str, dict] = {
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
_METRIC_QUERY_RULES: list[tuple[str, Callable, str]] = [
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
    queries: dict = {}
    for name, condition, query in _METRIC_QUERY_RULES:
        if condition(analysis_results):
            auto_name = f"auto_{name.lower().replace('-', '_').replace('#', 'n')}"
            queries[auto_name] = {
                "query": query,
                "retmax": 6,
                "sort": "relevance",
            }
    return queries
