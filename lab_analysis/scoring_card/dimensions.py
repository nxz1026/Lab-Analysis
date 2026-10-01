"""scoring_card.dimensions — 5 维评分函数。

⚠️ 维度极性 (极易搞反, 渲染与加权都必须区分)
- **越高越差**: ``inflammation`` (炎症活动度)、``lab_abnormality`` (实验室异常度)
- **越高越好**: ``literature_support``、``imaging_consistency``、``variability_stability``

统一取值表见 ``io._DIM_HIGHER_IS_BETTER``; 置信度加权与综合评估前必须先经
``hypotheses._normalized_dim_scores()`` 归一化。新增维度时两处必须同步更新。
"""

from __future__ import annotations

from .types import DimensionScores


def score_inflammation(results: dict) -> float:
    """炎症活动度评分 (0-100)。**越高越差**。

    基于 hs-CRP 分期、趋势、急性期占比。
    """
    inflam = results.get("inflammation_classification", {})
    labels = inflam.get("labels", [])
    reg = results.get("linear_regression", {})

    score = 50.0  # 基线

    # 最近一次炎症分期
    if labels:
        latest = labels[-1]
        if latest == "急性期":
            score += 30
        elif latest == "过渡期":
            score += 10
        elif latest == "缓解期":
            score -= 10

    # hs-CRP 趋势
    hs_crp = reg.get("hs-CRP", {})
    if hs_crp.get("trend") == "上升" and hs_crp.get("r2", 0) >= 0.7:
        score += 15
    elif hs_crp.get("trend") == "下降" and hs_crp.get("r2", 0) >= 0.7:
        score -= 10

    # 急性期占比
    if labels:
        acute_ratio = labels.count("急性期") / len(labels)
        score += acute_ratio * 20

    return max(0.0, min(100.0, score))


def score_lab_abnormality(results: dict, alerts: list[dict]) -> float:
    """实验室异常度评分 (0-100)。**越高越差**。

    基于异常指标数量、Z-score 严重异常、告警级别。
    """
    abnormal = results.get("abnormal_summary", {})
    zscores = results.get("zscore_outliers", {})

    score = 0.0

    # 异常指标数量（最多 40 分）
    n_abnormal = len(abnormal)
    score += min(40, n_abnormal * 8)

    # 严重 Z-score 异常（整项最多 30 分）
    # 必须先累加再封顶: 在循环内逐个 min(30, ...) 会让 n 个指标累计出 30*n,
    # 该维度很快饱和到 100 并失去区分度
    n_severe = sum(info.get("outliers_severe", {}).get("count", 0) for info in zscores.values())
    score += min(30, n_severe * 15)

    # CRITICAL 告警（最多 30 分）
    n_critical = sum(1 for a in alerts if a.get("level") == "CRITICAL")
    score += min(30, n_critical * 10)

    return max(0.0, min(100.0, score))


def score_literature_support(lit_filtered: dict) -> float:
    """文献证据支持度评分 (0-100)。

    基于 top 论文的 tier 加权平均。
    """
    papers = lit_filtered.get("filtered_papers", [])
    if not papers:
        return 0.0

    tier_weights = {"S": 1.0, "A": 0.8, "B": 0.5, "C": 0.2}
    scores = []
    for p in papers:
        grade = p.get("grade", {})
        tier = grade.get("tier", "C")
        paper_score = grade.get("score", 0)
        scaled = paper_score * 100 * tier_weights.get(tier, 0.3)
        scores.append(scaled)

    if not scores:
        return 0.0
    return max(0.0, min(100.0, sum(scores) / len(scores)))


def score_imaging_consistency(mri_results: dict) -> float:
    """影像一致性评分 (0-100)。

    基于 MRI 检查结果中成功/存疑/失败的比例。

    ⚠️ 只有真正做了「报告印证」的结果才有意义。qwen_vl_report_check* 只在调用成功
    时才追加一条 result, 失败的不写; 若没有纸质报告文本 (cross_checked=False) 就
    只做纯影像描述。此时 confirmed/total 恒为 1.0, 公式给出 130 → 截断成 100,
    反而显示「影像一致性 ✅ 良好」—— 这比没数据更糟。必须显式返回中值。
    """
    checks = []
    if isinstance(mri_results, dict):
        checks = mri_results.get("results", []) or mri_results.get("checks", [])

    if not checks:
        return 50.0  # 无影像数据时给中值

    if isinstance(mri_results, dict) and mri_results.get("cross_checked") is False:
        return 50.0  # 未做报告印证: 无对照基准, 不能给高分

    total = len(checks)
    if total == 0:
        return 50.0

    confirmed = sum(1 for c in checks if c.get("status") in ("success", "consistent"))
    conflicted = sum(1 for c in checks if c.get("status") in ("fail", "conflict"))

    return max(0.0, min(100.0, (confirmed / total) * 80 - (conflicted / total) * 30 + 50))


def score_variability_risk(results: dict) -> float:
    """变异风险评分 (0-100)。越高表示风险越低（越稳定）。"""
    cv_data = results.get("cv_stability", {})
    if not cv_data:
        return 50.0

    high = sum(1 for v in cv_data.values() if v.get("risk_level") == "高")
    total = len(cv_data)
    if total == 0:
        return 50.0

    risk_ratio = high / total
    # 转换: 高变异比例越高 → 分数越低
    return max(0.0, min(100.0, 100 - risk_ratio * 100))


def compute_dimension_scores(
    results: dict,
    alerts: list[dict],
    lit_filtered: dict,
    mri_results: dict,
) -> DimensionScores:
    """计算全部 5 维评分。"""
    return {
        "inflammation": round(score_inflammation(results), 1),
        "lab_abnormality": round(score_lab_abnormality(results, alerts), 1),
        "literature_support": round(score_literature_support(lit_filtered), 1),
        "imaging_consistency": round(score_imaging_consistency(mri_results), 1),
        "variability_stability": round(score_variability_risk(results), 1),
    }
