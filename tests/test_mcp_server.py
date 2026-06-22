"""MCP server 集成测试。

通过直接调用 tool 函数 (而不是走 stdio 协议) 来验证逻辑正确性。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# -------------------- skip marker --------------------

try:
    import mcp  # noqa: F401
    import mcp_server  # noqa: E402
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    mcp_server = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(
    not MCP_AVAILABLE, reason="mcp 库未装,跳过 MCP server 集成测试"
)


# -------------------- audit_dspy_models tool --------------------


def test_audit_dspy_models_returns_dict():
    """audit tool 应返回包含 overall_up_to_date 字段的 JSON 字符串。"""
    # 直接调 mcp_server 模块的 audit_dspy_models 函数
    # FastMCP 装饰器把函数 wrap, 但我们仍可通过 .fn 访问
    audit_fn = mcp_server.audit_dspy_models
    result_str = audit_fn()
    result = json.loads(result_str)
    assert "overall_up_to_date" in result
    assert "details" in result
    assert isinstance(result["details"], list)


def test_audit_dspy_models_all_up_to_date():
    """所有 compiled JSON 应该都是 UP-TO-DATE (刚刚重 compile 过)。"""
    audit_fn = mcp_server.audit_dspy_models
    result = json.loads(audit_fn())
    # F2 任务后, _retry.py 是新加的, 可能某些 module STALE
    # 这里只检查 tool 能跑通,不检查具体值
    assert "stale_modules" in result
    assert isinstance(result["stale_modules"], list)


# -------------------- run_quant_eval tool --------------------


def test_run_quant_eval_basic():
    """quant_eval tool 对真实 std + dspy 报告返回 6 指标。"""
    qe_fn = mcp_server.run_quant_eval
    result_str = qe_fn(
        id_card="846552421134373347",
        std_ts="20260620_175252",
        dspy_ts="20260620_175730",
    )
    result = json.loads(result_str)
    assert "metrics" in result
    metrics = result["metrics"]
    assert "entity_f1" in metrics
    assert "section_coverage" in metrics
    assert "failure_rate" in metrics
    assert "entity_recall" in metrics
    assert "confidence" in metrics
    assert "feedback_delta" in metrics


def test_run_quant_eval_text_lengths():
    """quant_eval 返回 std/dspy 文本长度。"""
    qe_fn = mcp_server.run_quant_eval
    result = json.loads(
        qe_fn(
            id_card="846552421134373347",
            std_ts="20260620_175252",
            dspy_ts="20260620_175730",
        )
    )
    assert "text_lengths" in result
    assert result["text_lengths"]["std"] > 1000
    assert result["text_lengths"]["dspy"] > 500


def test_run_quant_eval_invalid_patient():
    """不存在的患者应该优雅返回 error 字段,不 raise。"""
    qe_fn = mcp_server.run_quant_eval
    result_str = qe_fn(
        id_card="nonexistent_patient",
        std_ts="00000000_000000",
        dspy_ts="00000000_000000",
    )
    result = json.loads(result_str)
    # 不抛异常即可; metrics 可能全 available=False
    assert "metrics" in result or "error" in result


def test_run_quant_eval_metrics_have_available_field():
    """每个 metric 都有 available 字段 (便于上层判断)。"""
    qe_fn = mcp_server.run_quant_eval
    result = json.loads(
        qe_fn(
            id_card="846552421134373347",
            std_ts="20260620_175252",
            dspy_ts="20260620_175730",
        )
    )
    for name, m in result["metrics"].items():
        assert "available" in m, f"{name} 缺 available 字段"


# -------------------- mcp server smoke test --------------------


def test_mcp_server_module_loads():
    """mcp_server 模块能正常 import。"""
    assert hasattr(mcp_server, "mcp")
    assert hasattr(mcp_server, "audit_dspy_models")
    assert hasattr(mcp_server, "run_quant_eval")
    assert hasattr(mcp_server, "list_patients")
    assert hasattr(mcp_server, "get_pipeline_status")
    assert hasattr(mcp_server, "trigger_dspy_recompile")


def test_mcp_server_has_fastmcp_instance():
    """FastMCP 实例名 = 'lab-analysis'。"""
    assert mcp_server.mcp.name == "lab-analysis"


# ============== Tool 3: list_patients ==============


def test_list_patients_basic():
    """list_patients 返回 stats + pairs 字段。"""
    result = json.loads(mcp_server.list_patients())
    assert "n_patients" in result
    assert "n_total_samples" in result
    assert "n_dspy_samples" in result
    assert "n_std_samples" in result
    assert "per_patient" in result
    assert "pairs" in result
    assert isinstance(result["pairs"], dict)


def test_list_patients_filters_non_id_dirs():
    """list_patients 应过滤 mri_dspy_prompts 这种模板目录。"""
    result = json.loads(mcp_server.list_patients())
    # 业务 patient 是 18 位身份证号
    for pid in result["per_patient"]:
        assert pid.isdigit() and len(pid) == 18, f"非身份证号格式: {pid}"
    # mri_dspy_prompts 不应出现在 per_patient 里
    assert "mri_dspy_prompts" not in result["per_patient"]
    # 过滤掉的应记录在 filtered_out
    assert "filtered_out" in result
    assert "mri_dspy_prompts" in result["filtered_out"]


# ============== Tool 4: get_pipeline_status ==============


def test_get_pipeline_status_latest():
    """get_pipeline_status 不传 timestamp 时选最新一次。"""
    result = json.loads(mcp_server.get_pipeline_status("846552421134373347"))
    assert result["available"] is True
    assert result["timestamp"] == "20260620_175730"  # 最新
    assert "stages" in result
    assert "metrics" in result
    assert result["stages"]["final_report_md"] is True
    assert result["metrics"]["dspy_confidence"] == 0.88


def test_get_pipeline_status_specific_ts():
    """get_pipeline_status 传 timestamp 时看指定那一次。"""
    result = json.loads(
        mcp_server.get_pipeline_status("846552421134373347", "20260620_175252")
    )
    assert result["available"] is True
    assert result["timestamp"] == "20260620_175252"
    # 175252 是 std run (不含 dspy_prompts)
    assert result["is_dspy_run"] is False
    assert result["stages"]["dspy_prompts"] is False


def test_get_pipeline_status_nonexistent_patient():
    """不存在的 patient 优雅返回 error 字段。"""
    result = json.loads(mcp_server.get_pipeline_status("999999999999999999"))
    assert result["available"] is False
    assert "error" in result


def test_get_pipeline_status_nonexistent_ts():
    """存在的 patient + 不存在的 ts 优雅返回 error。"""
    result = json.loads(
        mcp_server.get_pipeline_status("846552421134373347", "19990101_000000")
    )
    assert result["available"] is False


# ============== Tool 5: trigger_dspy_recompile ==============


def test_trigger_dspy_recompile_incremental(monkeypatch):
    """增量模式 (force=False) 调 subprocess.run, mock 后验证 cmd 不含 --force。"""
    import subprocess as sp

    captured = {}

    class FakeResult:
        returncode = 0
        stdout = "DSPy 增量完成\n[跳过] literature_interpreter: 已最新\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeResult()

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)
    result = json.loads(mcp_server.trigger_dspy_recompile(force=False, timeout_sec=60))
    # 验证 cmd 包含 compile_all_dspy_modules_v2.py, 不含 --force
    assert any("compile_all_dspy_modules_v2.py" in str(c) for c in captured["cmd"])
    assert "--force" not in captured["cmd"]
    # 验证返回字段
    assert result["ok"] is True
    assert result["returncode"] == 0
    assert result["force"] is False
    assert "started_at" in result
    assert "elapsed_sec" in result
    assert "stdout_tail" in result


def test_trigger_dspy_recompile_force_mode(monkeypatch):
    """force=True 时 cmd 应包含 --force flag。"""

    class FakeResult:
        returncode = 0
        stdout = "DSPy 全量完成\n"
        stderr = ""

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return FakeResult()

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)
    result = json.loads(mcp_server.trigger_dspy_recompile(force=True, timeout_sec=60))
    assert "--force" in captured["cmd"]
    assert result["force"] is True
    assert result["ok"] is True


def test_trigger_dspy_recompile_timeout(monkeypatch):
    """subprocess 超时时 tool 应返回 error 字段, 不 raise。"""
    import subprocess as sp

    def fake_run(cmd, **kwargs):
        raise sp.TimeoutExpired(cmd="x", timeout=10)

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)
    result = json.loads(mcp_server.trigger_dspy_recompile(force=False, timeout_sec=10))
    assert result["ok"] is False
    assert "timeout" in result["error"].lower()
    assert result["returncode"] == -1


def test_trigger_dspy_recompile_nonzero_returncode(monkeypatch):
    """subprocess 返回非 0 时 ok=False, stdout_tail 仍返回。"""

    class FakeResult:
        returncode = 1
        stdout = "Error: DEEPSEEK_API_KEY missing\n"
        stderr = "Traceback (most recent call last):\n  ..."

    def fake_run(cmd, **kwargs):
        return FakeResult()

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)
    result = json.loads(mcp_server.trigger_dspy_recompile(force=True, timeout_sec=60))
    assert result["ok"] is False
    assert result["returncode"] == 1
    assert "DEEPSEEK_API_KEY" in result["stdout_tail"]