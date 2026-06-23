"""quant_eval_gate.py 阈值检查测试.

覆盖:
- 6 个 check_* 纯函数 PASS/FAIL/SKIP
- evaluate() 整体判定
- 边界值 (f1=0.7, coverage=0.8 等)
- main() 入口 exit 0/1
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.quant_eval_gate import (  # noqa: E402
    DEFAULT_THRESHOLDS,
    check_confidence,
    check_entity_f1,
    check_entity_recall,
    check_failure_rate,
    check_feedback_delta,
    check_section_coverage,
    evaluate,
)

# ---- 6 个 check_* 函数 ----


def test_check_entity_f1_pass():
    r = check_entity_f1({"available": True, "f1": 0.88}, f1_min=0.7)
    assert r.passed is True
    assert r.actual == 0.88
    assert r.threshold == 0.7
    assert r.skipped is False


def test_check_entity_f1_fail():
    r = check_entity_f1({"available": True, "f1": 0.5}, f1_min=0.7)
    assert r.passed is False
    assert "0.5000" in r.reason


def test_check_entity_f1_boundary():
    """f1 恰好等于阈值 = PASS (>=)."""
    r = check_entity_f1({"available": True, "f1": 0.7}, f1_min=0.7)
    assert r.passed is True


def test_check_entity_f1_skipped():
    r = check_entity_f1({"available": False, "reason": "no std text"}, f1_min=0.7)
    assert r.passed is True  # skipped 不算 FAIL
    assert r.skipped is True


def test_check_section_coverage_pass():
    r = check_section_coverage({"available": True, "coverage_rate": 1.0}, coverage_min=0.8)
    assert r.passed is True


def test_check_section_coverage_fail():
    r = check_section_coverage({"available": True, "coverage_rate": 0.6}, coverage_min=0.8)
    assert r.passed is False


def test_check_failure_rate_ok():
    r = check_failure_rate({"available": True, "is_failure": False, "confidence": 0.9})
    assert r.passed is True
    assert r.actual is False


def test_check_failure_rate_failed():
    r = check_failure_rate(
        {"available": True, "is_failure": True, "confidence": 0.3, "reasons": ["low conf"]}
    )
    assert r.passed is False


def test_check_entity_recall_pass():
    r = check_entity_recall(
        {"available": True, "recall_rate": 0.92, "n_std_entities": 12, "n_recalled": 11},
        recall_min=0.7,
    )
    assert r.passed is True


def test_check_confidence_pass():
    r = check_confidence(
        {"available": True, "dspy_confidence": 0.88, "std_top_confidence": 0.85},
        confidence_min=0.6,
    )
    assert r.passed is True


def test_check_confidence_below_threshold():
    r = check_confidence({"available": True, "dspy_confidence": 0.4}, confidence_min=0.6)
    assert r.passed is False


def test_check_feedback_delta_pass():
    r = check_feedback_delta(
        {
            "available": True,
            "avg_delta_confidence": 0.1,
            "max_delta": 0.2,
            "min_delta": -0.1,
        },
        abs_max=0.3,
    )
    assert r.passed is True


def test_check_feedback_delta_exceeds():
    r = check_feedback_delta({"available": True, "avg_delta_confidence": -0.5}, abs_max=0.3)
    assert r.passed is False


# ---- evaluate() 整合 ----


def test_evaluate_all_pass():
    report = {
        "deid": "TEST",
        "metrics": {
            "entity_f1": {"available": True, "f1": 0.9},
            "section_coverage": {"available": True, "coverage_rate": 1.0},
            "failure_rate": {"available": True, "is_failure": False},
            "entity_recall": {"available": True, "recall_rate": 0.95},
            "confidence": {"available": True, "dspy_confidence": 0.85},
            "feedback_delta": {"available": True, "avg_delta_confidence": 0.05},
        },
    }
    g = evaluate(report)
    assert g.overall_pass is True
    assert sum(1 for r in g.results if r.passed) == 7


def test_evaluate_mixed_skip():
    """部分 metric 不可用应 skip, 不阻塞 overall_pass."""
    report = {
        "deid": "TEST",
        "metrics": {
            "entity_f1": {"available": True, "f1": 0.9},
            "section_coverage": {"available": True, "coverage_rate": 1.0},
            "failure_rate": {"available": True, "is_failure": False},
            "entity_recall": {"available": True, "recall_rate": 0.95},
            "confidence": {"available": True, "dspy_confidence": 0.85},
            "feedback_delta": {"available": False, "reason": "无 data"},
        },
    }
    g = evaluate(report)
    assert g.overall_pass is True
    n_skip = sum(1 for r in g.results if r.skipped)
    assert n_skip == 2


def test_evaluate_one_fails_others_pass():
    report = {
        "deid": "TEST",
        "metrics": {
            "entity_f1": {"available": True, "f1": 0.4},  # FAIL
            "section_coverage": {"available": True, "coverage_rate": 1.0},
            "failure_rate": {"available": True, "is_failure": False},
            "entity_recall": {"available": True, "recall_rate": 0.95},
            "confidence": {"available": True, "dspy_confidence": 0.85},
            "feedback_delta": {"available": False},
        },
    }
    g = evaluate(report)
    assert g.overall_pass is False
    d = g.to_dict()
    assert d["n_failed"] == 1
    assert d["n_passed"] == 4
    assert d["n_skipped"] == 2


def test_default_thresholds_all_defined():
    assert "f1_min" in DEFAULT_THRESHOLDS
    assert "coverage_min" in DEFAULT_THRESHOLDS
    assert "recall_min" in DEFAULT_THRESHOLDS
    assert "confidence_min" in DEFAULT_THRESHOLDS
    assert "feedback_delta_abs_max" in DEFAULT_THRESHOLDS


# ---- CLI main() 入口 ----


def test_cli_pass_fixture(tmp_path: Path):
    """PASS fixture → exit 0."""
    src = PROJECT_ROOT / "tests" / "fixtures" / "quant_eval_sample_pass.json"
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "quant_eval_gate.py"),
            "--report-path",
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout
    # PASS fixture: 5 真 pass + 1 skip (feedback_delta 无 corrections)
    assert "5/7 passed" in result.stdout
    assert "2 skipped" in result.stdout


def test_cli_fail_fixture(tmp_path: Path):
    """FAIL fixture → exit 1 + 含 '❌ FAIL'."""
    src = PROJECT_ROOT / "tests" / "fixtures" / "quant_eval_sample_fail.json"
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "quant_eval_gate.py"),
            "--report-path",
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_cli_missing_report():
    """report 不存在 → exit 2 (用法错)."""
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "quant_eval_gate.py"),
            "--report-path",
            "/nonexistent/path.json",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "不存在" in result.stdout or "不存在" in result.stderr


def test_cli_dry_run_always_exit_0():
    """dry-run 模式不管 PASS/FAIL 都 exit 0."""
    src = PROJECT_ROOT / "tests" / "fixtures" / "quant_eval_sample_fail.json"
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "quant_eval_gate.py"),
            "--report-path",
            str(src),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "FAIL" in result.stdout  # 仍打印 FAIL


def test_cli_writes_gate_result_sidecar():
    """跑完应在 report 同目录写 quant_eval_gate_result.json."""
    src = PROJECT_ROOT / "tests" / "fixtures" / "quant_eval_sample_pass.json"
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "quant_eval_gate.py"),
            "--report-path",
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    sidecar = src.parent / "quant_eval_gate_result.json"
    assert sidecar.exists()
    d = json.loads(sidecar.read_text(encoding="utf-8"))
    assert d["overall_pass"] is True
    assert d["n_total"] == 7
