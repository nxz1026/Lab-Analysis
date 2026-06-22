"""6 指标量化评估的纯函数集合。

从 examples/dspy_quant_eval.py 抽出, 便于:
    1. CI 跑 inline 字符串测试 (不需要真实 patient 数据)
    2. dual_mode_pipeline / MCP tool 等多入口复用
    3. 单元测试覆盖每个 metric 的边界情况

7 个指标:
    1. 关键实体 F1            (std 报告作为 ground truth, 看 dspy 召回率)
    2. 章节覆盖度             (9 个 section 哪些非空)
    3. DSPy 失败率            (confidence < 0.6 / 缺失 / 全空)
    4. 实体召回率细分         (dspy 召回了 std 报告的哪些关键实体)
    5. 置信度分布 & 校准      (dspy.confidence + std 评分卡一致性)
    6. 人工反馈 Δconfidence   (来自 feedback.json corrections 列表)
    7. 跨模态印证准确率       (dspy 一致性段是否引用 std top_hypo + 关键 lab entity)
"""

from __future__ import annotations

from typing import Any


# 关键实体列表 (与 compare_report_modes 保持一致)
KEY_ENTITIES: list[str] = [
    "hs-CRP",
    "CRP",
    "WBC",
    "NEUT#",
    "MONO%",
    "RDW-SD",
    "RDW-CV",
    "PCT",
    "PLT",
    "急性期",
    "缓解期",
    "过渡期",
    "炎症",
    "慢性胰腺炎",
    "胰腺",
]


# ── 工具函数 ──────────────────────────────────────────────────


def count_entity(text: str, entity: str) -> int:
    """大文本中实体出现次数 (大小写不敏感)。"""
    return text.lower().count(entity.lower())


# ── 6 指标实现 ────────────────────────────────────────────────


def metric_entity_f1(std_text: str, dspy_text: str) -> dict[str, Any]:
    """1. 关键实体 F1。

    ground truth = std 报告里的实体 (视为基线/正确)。
    对每个 KEY_ENTITIES, 算 dspy 是否也提到了。
        TP = std & dspy 都提到
        FP = dspy 提到但 std 没提 (可能是噪声)
        FN = std 提到但 dspy 漏掉
    """
    if not std_text or not dspy_text:
        return {"available": False, "reason": "std 或 dspy 文本缺失"}

    tp = fp = fn = 0
    per_entity: dict[str, dict[str, int]] = {}
    for ent in KEY_ENTITIES:
        in_std = count_entity(std_text, ent) > 0
        in_dspy = count_entity(dspy_text, ent) > 0
        if in_std and in_dspy:
            tp += 1
        elif in_dspy and not in_std:
            fp += 1
        elif in_std and not in_dspy:
            fn += 1
        per_entity[ent] = {
            "in_std": int(in_std),
            "in_dspy": int(in_dspy),
        }

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "available": True,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "n_entities": len(KEY_ENTITIES),
        "per_entity": per_entity,
    }


def metric_section_coverage(dspy_sections: dict[str, str]) -> dict[str, Any]:
    """2. 章节覆盖度: 9 个 section 哪些非空。"""
    if not dspy_sections:
        return {"available": False, "reason": "dspy sections 缺失"}

    expected = [
        "title",
        "basic_info",
        "lab_analysis",
        "mri_analysis",
        "multidisciplinary",
        "diagnosis",
        "consistency",
        "action_plan",
        "followup",
        "prognosis",
    ]
    coverage: dict[str, dict[str, Any]] = {}
    n_nonempty = 0
    for k in expected:
        v = dspy_sections.get(k, "") or ""
        nonempty = bool(v and v.strip())
        if nonempty:
            n_nonempty += 1
        coverage[k] = {"nonempty": nonempty, "length": len(v)}

    return {
        "available": True,
        "n_expected": len(expected),
        "n_nonempty": n_nonempty,
        "coverage_rate": round(n_nonempty / len(expected), 4),
        "per_section": coverage,
    }


def metric_failure_rate(dspy_data: dict, dspy_sections: dict[str, str]) -> dict[str, Any]:
    """3. DSPy 失败率: confidence 缺失/低/全空 section。"""
    failures: list[str] = []
    conf = dspy_data.get("confidence")
    if conf is None:
        failures.append("confidence missing")
    elif not (0.0 <= conf <= 1.0):
        failures.append(f"confidence out of range: {conf}")
    elif conf < 0.6:
        failures.append(f"low confidence: {conf}")

    if dspy_sections:
        all_empty = all(not (v or "").strip() for v in dspy_sections.values())
        if all_empty:
            failures.append("all sections empty")

    return {
        "available": True,
        "confidence": conf,
        "is_failure": bool(failures),
        "reasons": failures,
    }


def metric_entity_recall_breakdown(std_text: str, dspy_text: str) -> dict[str, Any]:
    """4. 实体召回率细分: dspy 召回了 std 报告里哪些关键实体。

    临床意义: std 报告里出现的关键实体 (CRP, 慢性胰腺炎等), dspy 必须也提到。
    """
    if not std_text or not dspy_text:
        return {"available": False, "reason": "std 或 dspy 文本缺失"}

    std_entities = [e for e in KEY_ENTITIES if count_entity(std_text, e) > 0]
    recalled = [e for e in std_entities if count_entity(dspy_text, e) > 0]
    missed = [e for e in std_entities if e not in recalled]

    rate = len(recalled) / len(std_entities) if std_entities else 0.0
    return {
        "available": True,
        "n_std_entities": len(std_entities),
        "n_recalled": len(recalled),
        "recall_rate": round(rate, 4),
        "recalled": recalled,
        "missed": missed,
    }


def metric_confidence(dspy_data: dict, std_scoring: dict) -> dict[str, Any]:
    """5. 置信度分布 & 校准: dspy.confidence + std 评分卡一致性。

    校准 = std_scoring.top_hypotheses[0].confidence vs dspy.confidence
        接近 (差 < 0.15) 算 good, 差距大算 poor
    """
    dspy_conf = dspy_data.get("confidence")
    std_top_conf = None
    try:
        hyps = std_scoring.get("top_hypotheses", [])
        if hyps:
            std_top_conf = hyps[0].get("confidence")
    except (AttributeError, KeyError, TypeError):
        pass

    calibration = None
    if dspy_conf is not None and std_top_conf is not None:
        diff = abs(dspy_conf - std_top_conf)
        if diff < 0.1:
            calibration = "excellent"
        elif diff < 0.2:
            calibration = "good"
        elif diff < 0.3:
            calibration = "fair"
        else:
            calibration = "poor"
        return {
            "available": True,
            "dspy_confidence": dspy_conf,
            "std_top_confidence": std_top_conf,
            "abs_diff": round(diff, 4),
            "calibration": calibration,
        }

    return {
        "available": True,
        "dspy_confidence": dspy_conf,
        "std_top_confidence": std_top_conf,
        "abs_diff": None,
        "calibration": "N/A (缺一项)",
    }


def metric_feedback_delta(feedback_data: dict) -> dict[str, Any]:
    """6. 人工反馈 Δconfidence: feedback.json corrections 列表。

    Δ = corrected_confidence - original_confidence。
    聚合: avg / max / min / n_corrections。
    """
    corrections = feedback_data.get("corrections", [])
    if not corrections:
        # 无 corrections 也算 available=True (n=0, gate 阈值 |0| ≤ 0.30 自动 PASS)
        # 这样 HTML 始终能展示 n_corrections=0 统计, 避免被 SKIP 样式淹没
        return {
            "available": True,
            "n_corrections": 0,
            "n_rewrites": 0,
            "avg_delta_confidence": 0.0,
            "max_delta": 0.0,
            "min_delta": 0.0,
        }

    deltas: list[float] = []
    same_text_count = 0
    for c in corrections:
        orig = c.get("original_confidence", 0) or 0
        corr = c.get("corrected_confidence", 0) or 0
        deltas.append(corr - orig)
        if c.get("corrected_hypothesis") and c["corrected_hypothesis"] != c.get(
            "original_hypothesis", ""
        ):
            same_text_count += 1

    avg = sum(deltas) / len(deltas) if deltas else 0.0
    return {
        "available": True,
        "n_corrections": len(corrections),
        "n_rewrites": same_text_count,
        "avg_delta_confidence": round(avg, 4),
        "max_delta": round(max(deltas), 4) if deltas else 0.0,
        "min_delta": round(min(deltas), 4) if deltas else 0.0,
        "adjustments": feedback_data.get("confidence_adjustments", {}),
    }

# ── #7 跨模态印证准确率 (合规要求) ──────────────────────────────


def metric_cross_modality_consistency(
    dspy_sections: dict[str, str] | None,
    std_scoring: dict | None,
) -> dict[str, Any]:
    """7. 跨模态印证: dspy 一致性段是否引用 std top_hypothesis + 关键 lab 实体.

    临床意义: dspy 必须把 MRI 影像所见 + Lab 检验数据互相印证,
        不能只看一边下诊断. 算 accuracy:
        - consistency 段非空 (基础分 0.3)
        - mention std top_hypothesis.name (0.3)
        - mention 至少 1 个 KEY_ENTITIES (0.4)
        满分 1.0.
    """
    if not dspy_sections:
        return {"available": False, "reason": "dspy_sections 缺失"}
    consistency_text = (dspy_sections.get("consistency") or "").strip()
    if not consistency_text:
        return {"available": False, "reason": "dspy consistency 段缺失"}

    score = 0.3  # 基础分: 段非空
    components: dict[str, bool] = {"nonempty": True}

    # 1) mention std top_hypothesis
    mentioned_top = False
    top_name = None
    if std_scoring:
        hyps = std_scoring.get("top_hypotheses", []) or []
        if hyps:
            top = hyps[0]
            top_name = str(top.get("name") or top.get("hypothesis") or "")
            if top_name and top_name in consistency_text:
                mentioned_top = True
                score += 0.3
    components["mentions_top_hypothesis"] = mentioned_top

    # 2) mention 至少 1 个 KEY_ENTITIES
    mentioned_entity = False
    matched_entities: list[str] = []
    for ent in KEY_ENTITIES:
        if count_entity(consistency_text, ent) > 0:
            matched_entities.append(ent)
            mentioned_entity = True
    if mentioned_entity:
        score += 0.4
    components["mentions_key_entity"] = mentioned_entity

    return {
        "available": True,
        "top_hypothesis": top_name,
        "mentions_top_hypothesis": mentioned_top,
        "mentions_key_entity": mentioned_entity,
        "matched_entities": matched_entities,
        "consistency_length": len(consistency_text),
        "accuracy": round(min(score, 1.0), 4),
    }
