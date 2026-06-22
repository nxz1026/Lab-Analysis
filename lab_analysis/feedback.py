"""feedback.py — 交互式反馈回路

记录用户对评分卡诊断假设的纠正，用于调整后续评分权重。

用法:
    python -m lab_analysis.feedback --id-card <deid> --show
    python -m lab_analysis.feedback --id-card <deid> --correct \\
        --original "慢性胰腺炎（活动期）" --corrected "急性胰腺炎"
    python -m lab_analysis.feedback --id-card <deid> --clear
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from lab_analysis.utils import WORK_ROOT

# ── 反馈数据结构 ──────────────────────────────────────────────────

FeedbackData = dict[str, Any]
"""反馈文件结构:
{
    "patient_id": str,
    "generated": str (ISO datetime),
    "corrections": [
        {
            "run_timestamp": str,
            "original_hypothesis": str,
            "original_confidence": float,
            "corrected_hypothesis": str,
            "corrected_confidence": float,
            "user_comment": str,
            "corrected_at": str,
        }
    ],
    "confidence_adjustments": {
        "<rule_name>": float,   # 增量调整，正值上调，负值下调
    },
}
"""


def _feedback_path(deid: str) -> Path:
    return WORK_ROOT / "data" / deid / "feedback.json"


def load_feedback(deid: str) -> FeedbackData:
    """加载患者的反馈记录。文件不存在时返回空模板。"""
    path = _feedback_path(deid)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "patient_id": deid,
        "generated": datetime.now().isoformat(),
        "corrections": [],
        "confidence_adjustments": {},
    }


def save_feedback(feedback: FeedbackData):
    """保存反馈记录。"""
    path = _feedback_path(feedback["patient_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feedback, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [OK] 反馈已保存: {path}")


def record_correction(
    deid: str,
    original_hypothesis: str,
    corrected_hypothesis: str,
    original_confidence: float = 0.0,
    corrected_confidence: float = 0.0,
    user_comment: str = "",
    run_timestamp: str = "",
) -> FeedbackData:
    """记录一次诊断假设纠正。

    Args:
        deid: 脱敏患者 ID。
        original_hypothesis: 原始诊断假设文本。
        corrected_hypothesis: 用户纠正后的诊断。
        original_confidence: 原始置信度。
        corrected_confidence: 用户认为的置信度。
        user_comment: 用户备注。
        run_timestamp: 运行批次时间戳。

    Returns:
        更新后的反馈数据。
    """
    feedback = load_feedback(deid)
    correction = {
        "run_timestamp": run_timestamp or datetime.now().strftime("%Y%m%d_%H%M%S"),
        "original_hypothesis": original_hypothesis,
        "original_confidence": original_confidence,
        "corrected_hypothesis": corrected_hypothesis,
        "corrected_confidence": corrected_confidence
        if corrected_confidence is not None
        else original_confidence,
        "user_comment": user_comment or "",
        "corrected_at": datetime.now().isoformat(),
    }
    feedback["corrections"].append(correction)
    feedback["generated"] = datetime.now().isoformat()

    # 尝试自动调整对应规则的置信度
    _auto_adjust_confidence(feedback, correction)

    save_feedback(feedback)
    return feedback


def _auto_adjust_confidence(feedback: FeedbackData, correction: dict):
    """根据纠正记录自动调整规则置信度增量。

    策略:
        - 用户纠正了假设，说明原规则在该场景可能过强 → 下调
        - 用户给出了更高的置信度 → 规则置信度上调
    """
    rule_map = {
        "慢性胰腺炎（活动期）": "chronic_pancreatitis_active",
        "慢性胰腺炎（缓解期）": "chronic_pancreatitis_remission",
        "系统性炎症/感染": "systemic_inflammation_infection",
        "指标波动显著（需关注稳定性）": "high_variability_risk",
        "影像-检验结论不一致": "imaging_lab_conflict",
        "文献证据充分支持当前诊疗方向": "literature_well_supported",
        "非炎症性血液系统异常": "rdw_elevated_only",
    }

    orig = correction.get("original_hypothesis", "")
    rule = rule_map.get(orig)
    if not rule:
        return

    conf_diff = correction.get("corrected_confidence", 0) - correction.get("original_confidence", 0)
    adjustment = feedback["confidence_adjustments"]

    if conf_diff > 0.1:
        adjustment[rule] = adjustment.get(rule, 0) + 0.05
    elif conf_diff < -0.1:
        adjustment[rule] = adjustment.get(rule, 0) - 0.05

    # 如果纠正的假设与原假设完全不同 → 下调原规则
    if (
        correction.get("corrected_hypothesis")
        and correction["corrected_hypothesis"] != orig
        and orig
    ):
        adjustment[rule] = adjustment.get(rule, 0) - 0.10


def get_confidence_adjustments(deid: str) -> dict[str, float]:
    """获取该患者的置信度调整表，供 scoring_card 使用。"""
    feedback = load_feedback(deid)
    return feedback.get("confidence_adjustments", {})


def clear_feedback(deid: str):
    """清除患者的反馈记录。"""
    path = _feedback_path(deid)
    if path.exists():
        path.unlink()
        print(f"  [OK] 已清除反馈: {path}")
    else:
        print(f"  [INFO] 无反馈记录: {path}")


def print_feedback(feedback: FeedbackData):
    """打印反馈记录。"""
    print(f"\n=== 反馈记录: {feedback['patient_id']} ===\n")
    corrections = feedback.get("corrections", [])
    if not corrections:
        print("  (无纠正记录)")
    else:
        for i, c in enumerate(corrections, 1):
            print(f"  [{i}] {c['run_timestamp']}")
            print(
                f"      原假设: {c['original_hypothesis']} (置信度 {c['original_confidence']:.0%})"
            )
            print(
                f"      纠正为: {c['corrected_hypothesis']} (置信度 {c['corrected_confidence']:.0%})"
            )
            if c.get("user_comment"):
                print(f"      备注: {c['user_comment']}")

    adjustments = feedback.get("confidence_adjustments", {})
    if adjustments:
        print("\n  置信度调整:")
        for rule, adj in adjustments.items():
            arrow = "↑" if adj > 0 else "↓" if adj < 0 else "→"
            print(f"    {rule}: {arrow} {adj:+.2f}")


def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="诊断假设反馈记录工具")
    parser.add_argument("--id-card", required=True, help="脱敏 ID")
    parser.add_argument("--show", action="store_true", help="查看当前反馈")
    parser.add_argument("--correct", action="store_true", help="记录纠正")
    parser.add_argument("--original", default="", help="原始诊断假设")
    parser.add_argument("--corrected", default="", help="纠正后的诊断")
    parser.add_argument("--confidence", type=float, default=None, help="置信度 (0-1)")
    parser.add_argument("--comment", default="", help="用户备注")
    parser.add_argument("--clear", action="store_true", help="清除反馈")
    args = parser.parse_args()

    if args.show:
        feedback = load_feedback(args.id_card)
        print_feedback(feedback)
    elif args.correct:
        record_correction(
            args.id_card,
            original_hypothesis=args.original,
            corrected_hypothesis=args.corrected,
            corrected_confidence=args.confidence,
            user_comment=args.comment,
        )
    elif args.clear:
        clear_feedback(args.id_card)
    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
