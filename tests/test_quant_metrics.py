"""lab_analysis.quant_metrics 6 指标纯函数单元测试。

不依赖真实 patient 数据 / 文件 I/O, 直接用 inline 字符串验证。
"""

from __future__ import annotations

import pytest

from lab_analysis.quant_metrics import (
    KEY_ENTITIES,
    count_entity,
    metric_confidence,
    metric_entity_f1,
    metric_entity_recall_breakdown,
    metric_failure_rate,
    metric_feedback_delta,
    metric_section_coverage,
)


# -------------------- 工具函数 --------------------


def test_count_entity_case_insensitive():
    assert count_entity("CRP is high", "crp") == 1
    assert count_entity("CrP CrP", "CRP") == 2


def test_count_entity_zero():
    assert count_entity("no match here", "XYZ") == 0


def test_key_entities_is_list():
    assert isinstance(KEY_ENTITIES, list)
    assert "CRP" in KEY_ENTITIES
    assert "慢性胰腺炎" in KEY_ENTITIES


# -------------------- metric 1: entity_f1 --------------------


def test_entity_f1_perfect_match():
    text = "CRP WBC 慢性胰腺炎 胰腺"
    result = metric_entity_f1(text, text)
    assert result["available"] is True
    assert result["tp"] == 4
    assert result["fp"] == 0
    assert result["fn"] == 0
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0


def test_entity_f1_partial_match():
    std = "CRP WBC 慢性胰腺炎"
    dspy = "CRP WBC 胰腺"
    result = metric_entity_f1(std, dspy)
    # CRP, WBC → TP; 慢性胰腺炎 → FN; 胰腺 → TP
    # 实际 std 提到的 4 个实体: CRP WBC 慢性胰腺炎 胰腺 (胰腺在 dspy 中)
    # dspy 提到 3 个: CRP WBC 胰腺
    # 交集 = 3 (CRP WBC 胰腺), std 独有 = 1 (慢性胰腺炎)
    # TP=3, FN=1, FP=0
    assert result["tp"] == 3
    assert result["fn"] == 1
    assert result["fp"] == 0
    assert result["recall"] == 0.75


def test_entity_f1_dspy_extra():
    std = "CRP"
    dspy = "CRP WBC NEUT#"
    result = metric_entity_f1(std, dspy)
    # TP=1 (CRP), FP=2 (WBC NEUT#), FN=0
    assert result["tp"] == 1
    assert result["fp"] == 2
    assert result["fn"] == 0


def test_entity_f1_empty_text():
    assert metric_entity_f1("", "some text")["available"] is False
    assert metric_entity_f1("some text", "")["available"] is False
    assert metric_entity_f1("", "")["available"] is False


# -------------------- metric 2: section_coverage --------------------


def test_section_coverage_all_filled():
    sections = {k: "x" for k in [
        "title", "basic_info", "lab_analysis", "mri_analysis",
        "multidisciplinary", "diagnosis", "consistency",
        "action_plan", "followup", "prognosis",
    ]}
    result = metric_section_coverage(sections)
    assert result["available"] is True
    assert result["n_nonempty"] == 10
    assert result["coverage_rate"] == 1.0


def test_section_coverage_partial():
    sections = {"title": "x", "basic_info": "x", "diagnosis": "x"}
    result = metric_section_coverage(sections)
    assert result["n_nonempty"] == 3
    assert result["coverage_rate"] == 0.3


def test_section_coverage_whitespace_only():
    """只有空白的 section 算 empty。"""
    sections = {"title": "   ", "basic_info": "x"}
    result = metric_section_coverage(sections)
    assert result["per_section"]["title"]["nonempty"] is False
    assert result["per_section"]["basic_info"]["nonempty"] is True
    assert result["n_nonempty"] == 1


def test_section_coverage_empty_input():
    assert metric_section_coverage({})["available"] is False


# -------------------- metric 3: failure_rate --------------------


def test_failure_rate_low_confidence():
    dspy_data = {"confidence": 0.4}
    sections = {"title": "x"}
    result = metric_failure_rate(dspy_data, sections)
    assert result["is_failure"] is True
    assert "low confidence: 0.4" in result["reasons"]


def test_failure_rate_missing_confidence():
    result = metric_failure_rate({}, {"title": "x"})
    assert result["is_failure"] is True
    assert "confidence missing" in result["reasons"]


def test_failure_rate_all_empty_sections():
    result = metric_failure_rate({"confidence": 0.9}, {"a": "", "b": "  "})
    assert "all sections empty" in result["reasons"]


def test_failure_rate_ok():
    result = metric_failure_rate({"confidence": 0.85}, {"title": "x"})
    assert result["is_failure"] is False
    assert result["reasons"] == []


# -------------------- metric 4: entity_recall_breakdown --------------------


def test_entity_recall_full():
    std = "CRP WBC 慢性胰腺炎 胰腺"
    dspy = "CRP WBC 慢性胰腺炎 胰腺 缓解期"
    result = metric_entity_recall_breakdown(std, dspy)
    assert result["n_std_entities"] == 4
    assert result["n_recalled"] == 4
    assert result["recall_rate"] == 1.0
    # "缓解期" 不在 std 中, 所以不在 std_entities / recalled
    assert "缓解期" not in result["recalled"]
    assert "缓解期" not in result["missed"]


def test_entity_recall_partial():
    std = "CRP WBC 慢性胰腺炎"
    dspy = "CRP WBC"
    result = metric_entity_recall_breakdown(std, dspy)
    assert result["n_recalled"] == 2
    assert "慢性胰腺炎" in result["missed"]


def test_entity_recall_empty():
    assert metric_entity_recall_breakdown("", "x")["available"] is False
    assert metric_entity_recall_breakdown("x", "")["available"] is False


# -------------------- metric 5: confidence (calibration) --------------------


def test_confidence_excellent():
    dspy = {"confidence": 0.85}
    std = {"top_hypotheses": [{"confidence": 0.88}]}
    result = metric_confidence(dspy, std)
    assert result["calibration"] == "excellent"
    assert result["abs_diff"] == 0.03


def test_confidence_good():
    dspy = {"confidence": 0.85}
    std = {"top_hypotheses": [{"confidence": 0.70}]}  # diff = 0.15
    result = metric_confidence(dspy, std)
    # 0.10 <= diff < 0.20 → good
    assert result["calibration"] == "good"
    assert result["abs_diff"] == 0.15


def test_confidence_poor():
    dspy = {"confidence": 0.9}
    std = {"top_hypotheses": [{"confidence": 0.5}]}
    result = metric_confidence(dspy, std)
    assert result["calibration"] == "poor"


def test_confidence_missing_dspy():
    std = {"top_hypotheses": [{"confidence": 0.8}]}
    result = metric_confidence({}, std)
    assert result["calibration"] == "N/A (缺一项)"
    assert result["abs_diff"] is None


def test_confidence_missing_std():
    dspy = {"confidence": 0.8}
    result = metric_confidence(dspy, {})
    assert result["calibration"] == "N/A (缺一项)"


# -------------------- metric 6: feedback_delta --------------------


def test_feedback_delta_with_corrections():
    feedback = {
        "corrections": [
            {"original_confidence": 0.5, "corrected_confidence": 0.7},
            {"original_confidence": 0.6, "corrected_confidence": 0.8},
        ]
    }
    result = metric_feedback_delta(feedback)
    assert result["available"] is True
    assert result["n_corrections"] == 2
    assert result["avg_delta_confidence"] == 0.2
    assert result["max_delta"] == 0.2
    assert result["min_delta"] == 0.2


def test_feedback_delta_no_corrections():
    result = metric_feedback_delta({})
    assert result["available"] is False
    assert result["n_corrections"] == 0


def test_feedback_delta_n_rewrites():
    feedback = {
        "corrections": [
            {
                "original_confidence": 0.5,
                "corrected_confidence": 0.7,
                "original_hypothesis": "A",
                "corrected_hypothesis": "B",  # 改写了
            },
            {
                "original_confidence": 0.5,
                "corrected_confidence": 0.7,
                "original_hypothesis": "X",
                "corrected_hypothesis": "X",  # 只改 confidence, 不算 rewrite
            },
        ]
    }
    result = metric_feedback_delta(feedback)
    assert result["n_rewrites"] == 1


def test_feedback_delta_negative_delta():
    feedback = {
        "corrections": [
            {"original_confidence": 0.8, "corrected_confidence": 0.6},  # Δ = -0.2
        ]
    }
    result = metric_feedback_delta(feedback)
    assert result["avg_delta_confidence"] == -0.2
    assert result["max_delta"] == -0.2
    assert result["min_delta"] == -0.2