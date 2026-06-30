"""E2E tests for lab_analysis.pipeline.run.main().

Strategy:
- Mock subprocess.run so no real python -m lab_analysis.xxx is invoked.
- Mock ID extraction / validation to feed a known good ID.
- Verify all step names are visited, and that --skip-* flags skip the
  corresponding step.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from lab_analysis.pipeline import run as run_mod

_VALID_ID = "11010119900307881X"  # valid sample, last char X


def _fake_subprocess_run(*args, **kwargs):
    """Stand-in: pretend the pipeline step ran successfully."""
    return MagicMock(returncode=0, stdout="", stderr="")


def _args(**overrides):
    """Build a Namespace with sensible defaults matching parse_args output."""
    base = dict(
        skip_ingest=True,  # never actually run ingest
        ingest_lab=None,
        ingest_dicom_zip=None,
        ingest_dicom_dir=None,
        ingest_mri_report=None,
        report_date=None,
        report_type=None,
        no_interactive=True,
        skip_llm=False,
        skip_imaging=False,
        skip_lit_filter=False,
        skip_scoring=False,
        skip_fhir=False,
        skip_cleanup=False,
        skip_pdf=False,
        use_dspy=False,
        lit_filter_scenario="differential_diagnosis",
        lit_filter_top_k=8,
        compare_report_modes=False,
        keep_last=3,
        auto_queries=False,
    )
    base.update(overrides)
    return type("A", (), base)()


@pytest.fixture
def fake_id_env(monkeypatch):
    """Patch the ID extraction / validation / context pipeline + patient check."""
    monkeypatch.setattr(run_mod, "extract_patient_id_from_reports", lambda: _VALID_ID)
    monkeypatch.setattr(run_mod, "validate_id_card", lambda x, interactive=True: x)
    monkeypatch.setattr(run_mod, "get_deid", lambda x: "DEID00001")
    monkeypatch.setattr(run_mod, "PipelineContext",
                        lambda deid, timestamp: MagicMock(env_dict=lambda: {"ANALYSIS_TS": timestamp}))
    monkeypatch.setattr(run_mod, "check_patient_data", lambda deid: True)
    # disable logging side effects
    monkeypatch.setattr(run_mod, "_setup_pipeline_logging", lambda ts: None)
    # P1-4: 重置 cleanup 幂等标志, 避免跨测试干扰
    run_mod._cleanup_done_var.set(False)


def test_main_calls_all_standard_steps(monkeypatch, fake_id_env, tmp_path):
    """Happy path: all default steps should be invoked in order."""
    calls: list[str] = []

    def fake_run_step(name, module, *args, **kwargs):
        calls.append(module)
        return 0

    monkeypatch.setattr(run_mod, "run_step", fake_run_step)
    # P2-4: 细化粒度 — 只 patch run_mod 命名空间下的 subprocess.run, 不替换整个 subprocess 模块
    monkeypatch.setattr(run_mod.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(run_mod, "parse_args", lambda: _args())
    monkeypatch.setattr(sys, "argv", ["lab-analysis"])

    # Provide empty data dir so main() doesn't iterate missing files
    with patch.object(run_mod, "WORK_ROOT", tmp_path):
        run_mod.main()

    expected = [
        "data_loader", "data_analyzer", "literature_searcher",
        "literature_filter", "literature_interpreter", "qwen_vl_report_check",
        "gen_final_report", "scoring_card", "organize_local_files",
        "fhir_exporter",
    ]
    assert calls == expected, f"got {calls}"


def test_main_skip_llm_skips_lit_interp(monkeypatch, fake_id_env, tmp_path):
    """--skip-llm drops the lit_interpreter step but imaging still runs."""
    calls: list[str] = []
    monkeypatch.setattr(run_mod, "run_step",
                        lambda n, m, *a, **k: (calls.append(m) or 0))
    # P2-4: 细化粒度 — 只 patch run_mod 命名空间下的 subprocess.run, 不替换整个 subprocess 模块
    monkeypatch.setattr(run_mod.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(run_mod, "parse_args", lambda: _args(skip_llm=True))
    monkeypatch.setattr(sys, "argv", ["lab-analysis"])

    with patch.object(run_mod, "WORK_ROOT", tmp_path):
        run_mod.main()

    assert "literature_interpreter" not in calls
    # imaging depends on lit output in production; code allows it to run
    # unless --skip-imaging is also set
    assert "qwen_vl_report_check" in calls
    # data_loader / data_analyzer / literature_searcher should still run
    assert "data_loader" in calls
    assert "data_analyzer" in calls


def test_main_skip_imaging_runs_lit_interp(monkeypatch, fake_id_env, tmp_path):
    calls: list[str] = []
    monkeypatch.setattr(run_mod, "run_step",
                        lambda n, m, *a, **k: (calls.append(m) or 0))
    # P2-4: 细化粒度 — 只 patch run_mod 命名空间下的 subprocess.run, 不替换整个 subprocess 模块
    monkeypatch.setattr(run_mod.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(run_mod, "parse_args", lambda: _args(skip_imaging=True))
    monkeypatch.setattr(sys, "argv", ["lab-analysis"])

    with patch.object(run_mod, "WORK_ROOT", tmp_path):
        run_mod.main()

    assert "qwen_vl_report_check" not in calls
    assert "literature_interpreter" in calls


def test_main_use_dspy_routes_to_dspy_modules(monkeypatch, fake_id_env, tmp_path):
    """--use-dspy should route interpretation/imaging/report to *_dspy modules."""
    calls: list[str] = []
    monkeypatch.setattr(run_mod, "run_step",
                        lambda n, m, *a, **k: (calls.append(m) or 0))
    # P2-4: 细化粒度 — 只 patch run_mod 命名空间下的 subprocess.run, 不替换整个 subprocess 模块
    monkeypatch.setattr(run_mod.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(run_mod, "parse_args", lambda: _args(use_dspy=True))
    monkeypatch.setattr(sys, "argv", ["lab-analysis"])

    with patch.object(run_mod, "WORK_ROOT", tmp_path):
        run_mod.main()

    assert "literature_interpreter_dspy" in calls
    assert "qwen_vl_report_check_dspy" in calls
    assert "gen_final_report_dspy" in calls
    # the non-dspy counterparts should NOT be invoked
    assert "literature_interpreter" not in calls
    assert "qwen_vl_report_check" not in calls
    assert "gen_final_report" not in calls


def test_main_fails_on_data_loader_error(monkeypatch, fake_id_env, tmp_path):
    """If data_loader step returns non-zero, main() should sys.exit(1) AND
    register cleanup to atexit so the cleanup hook survives process exit.

    P1-4 增强: 验证 sys.exit(1) 路径下, _cleanup_pipeline_state 仍会被注册到 atexit。
    """
    import atexit as atexit_mod

    def failing_run_step(name, module, *args, **kwargs):
        if module == "data_loader":
            sys.exit(1)  # run_step 默认 fatal=True, 失败时直接 sys.exit(1)
        return 0

    cleanup_registered: list = []
    original_register = atexit_mod.register

    def tracking_register(fn, *args, **kwargs):
        if fn is run_mod._cleanup_pipeline_state:
            cleanup_registered.append(fn)
        return original_register(fn, *args, **kwargs)

    monkeypatch.setattr(run_mod, "run_step", failing_run_step)
    # P2-4: 细化粒度 — 只 patch subprocess.run
    monkeypatch.setattr(run_mod.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(run_mod, "parse_args", lambda: _args())
    monkeypatch.setattr(atexit_mod, "register", tracking_register)
    monkeypatch.setattr(sys, "argv", ["lab-analysis"])

    with patch.object(run_mod, "WORK_ROOT", tmp_path), \
         pytest.raises(SystemExit) as exc:
        run_mod.main()
    assert exc.value.code == 1
    # P1-4: fatal 路径下 _cleanup_pipeline_state 必须已注册到 atexit
    assert cleanup_registered, "fatal sys.exit(1) 路径未注册 cleanup 到 atexit"


def test_cleanup_pipeline_state_idempotent(monkeypatch, fake_id_env):
    """_cleanup_pipeline_state 多次调用应幂等 (同一进程多次 main() 不重复 flush)。"""
    flush_calls: list = []
    fake_handler = MagicMock()
    fake_handler.level = 0
    fake_handler.flush = lambda: flush_calls.append(1)
    run_mod._cleanup_done_var.set(False)
    monkeypatch.setattr(run_mod.logger, "handlers", [fake_handler])
    run_mod._cleanup_pipeline_state()
    run_mod._cleanup_pipeline_state()
    assert len(flush_calls) == 1, f"应幂等, 实际 flush 调用 {len(flush_calls)} 次"


def test_cleanup_pipeline_state_handler_flush_failure_swallowed(monkeypatch, fake_id_env):
    """cleanup 期间 handler.flush() 失败不应阻止后续清理。"""
    broken_handler = MagicMock()
    broken_handler.level = 0
    broken_handler.flush.side_effect = OSError("disk full")
    run_mod._cleanup_done_var.set(False)
    monkeypatch.setattr(run_mod.logger, "handlers", [broken_handler])
    run_mod._cleanup_pipeline_state()
    assert run_mod._cleanup_done_var.get() is True
    assert broken_handler.flush.called


def test_main_invalid_id_exits(monkeypatch, tmp_path):
    """validate_id_card returning falsy should sys.exit(1) before any step runs."""
    monkeypatch.setattr(run_mod, "extract_patient_id_from_reports", lambda: "BAD")
    monkeypatch.setattr(run_mod, "validate_id_card", lambda x, interactive=True: None)
    calls: list[str] = []
    monkeypatch.setattr(run_mod, "run_step",
                        lambda n, m, *a, **k: (calls.append(m) or 0))
    monkeypatch.setattr(run_mod, "parse_args", lambda: _args())
    monkeypatch.setattr(sys, "argv", ["lab-analysis"])

    with patch.object(run_mod, "WORK_ROOT", tmp_path), \
         pytest.raises(SystemExit) as exc:
        run_mod.main()
    assert exc.value.code == 1
    assert calls == [], f"no steps should run, got {calls}"


def test_main_skip_lit_filter(monkeypatch, fake_id_env, tmp_path):
    calls: list[str] = []
    monkeypatch.setattr(run_mod, "run_step",
                        lambda n, m, *a, **k: (calls.append(m) or 0))
    # P2-4: 细化粒度 — 只 patch run_mod 命名空间下的 subprocess.run, 不替换整个 subprocess 模块
    monkeypatch.setattr(run_mod.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(run_mod, "parse_args", lambda: _args(skip_lit_filter=True))
    monkeypatch.setattr(sys, "argv", ["lab-analysis"])

    with patch.object(run_mod, "WORK_ROOT", tmp_path):
        run_mod.main()

    assert "literature_filter" not in calls
    # upstream/downstream still present
    assert "literature_searcher" in calls
    assert "literature_interpreter" in calls


def test_main_skip_scoring_runs_main_pipeline(monkeypatch, fake_id_env, tmp_path):
    """--skip-scoring should not affect the main pipeline, only drop scoring_card."""
    calls: list[str] = []
    monkeypatch.setattr(run_mod, "run_step",
                        lambda n, m, *a, **k: (calls.append(m) or 0))
    # P2-4: 细化粒度 — 只 patch run_mod 命名空间下的 subprocess.run, 不替换整个 subprocess 模块
    monkeypatch.setattr(run_mod.subprocess, "run", _fake_subprocess_run)
    monkeypatch.setattr(run_mod, "parse_args", lambda: _args(skip_scoring=True))
    monkeypatch.setattr(sys, "argv", ["lab-analysis"])

    with patch.object(run_mod, "WORK_ROOT", tmp_path):
        run_mod.main()

    assert "scoring_card" not in calls
    assert "gen_final_report" in calls
    assert "data_loader" in calls