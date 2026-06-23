"""tests.test_pipeline_step_decorator — 验证 @pipeline_step 装饰器与 run_step fatal 参数。

覆盖:
- pipeline_step 装饰器: bool / int / None 返回值
- fatal=True 失败 sys.exit(1)
- fatal=False 失败只 log + return rc
- 异常 → sys.exit(1) (fatal=True) 或 return 1 (fatal=False)
- run_step: fatal=False 不终止进程, 返回非零 rc
"""

from __future__ import annotations

import subprocess

import pytest

from lab_analysis.pipeline import steps


class TestPipelineStepBoolReturn:
    def test_bool_true_returns_zero(self, caplog):
        @steps.pipeline_step(name="bool-true")
        def s():
            return True

        with caplog.at_level("INFO"):
            rc = s()
        assert rc == 0

    def test_bool_false_fatal_returns_one_and_exits(self, caplog):
        @steps.pipeline_step(name="bool-false-fatal", fatal=True)
        def s():
            return False

        with caplog.at_level("ERROR"), pytest.raises(SystemExit) as exc:
            s()
        assert exc.value.code == 1

    def test_bool_false_nonfatal_returns_one(self, caplog):
        @steps.pipeline_step(name="bool-false-ok", fatal=False)
        def s():
            return False

        rc = s()
        assert rc == 1


class TestPipelineStepIntReturn:
    def test_int_zero_is_success(self):
        @steps.pipeline_step(name="int-0")
        def s():
            return 0

        assert s() == 0

    def test_int_nonzero_fatal_exits(self):
        @steps.pipeline_step(name="int-2-fatal", fatal=True)
        def s():
            return 2

        with pytest.raises(SystemExit) as exc:
            s()
        assert exc.value.code == 1  # fatal 路径统一返回 1, 不透传非 0/1

    def test_int_nonzero_nonfatal_returns_value(self):
        @steps.pipeline_step(name="int-3-ok", fatal=False)
        def s():
            return 3

        assert s() == 3


class TestPipelineStepNoneReturn:
    def test_none_is_treated_as_success(self):
        @steps.pipeline_step(name="none-ok")
        def s():
            return None

        assert s() == 0


class TestPipelineStepException:
    def test_fatal_exception_exits(self):
        @steps.pipeline_step(name="exc-fatal", fatal=True)
        def s():
            raise RuntimeError("boom")

        with pytest.raises(SystemExit) as exc:
            s()
        assert exc.value.code == 1

    def test_nonfatal_exception_returns_one(self):
        @steps.pipeline_step(name="exc-ok", fatal=False)
        def s():
            raise RuntimeError("boom")

        assert s() == 1


class TestPipelineStepLogging:
    def test_step_logs_start_and_ok(self, caplog):
        @steps.pipeline_step(name="logged-step")
        def s():
            return True

        with caplog.at_level("INFO", logger="lab_analysis.pipeline.steps"):
            s()
        text = caplog.text
        assert "[STEP] logged-step" in text
        assert "[OK] logged-step" in text

    def test_step_logs_duration(self, caplog):
        @steps.pipeline_step(name="slow-step")
        def s():
            return True

        with caplog.at_level("INFO", logger="lab_analysis.pipeline.steps"):
            s()
        assert "(0." in caplog.text  # 含小数值即 "elapsed"


# ---------------------------------------------------------------------------
# run_step fatal 参数 (真实子进程)
# ---------------------------------------------------------------------------
class TestRunStepFatal:
    """用 python -c "raise SystemExit(7)" 作为失败命令。"""

    def _run_with_python_cmd(self, *, cmd_module: str, fatal: bool) -> int:
        """通过 monkeypatch subprocess.run 拦截, 返回值。

        用真实 subprocess 但 cmd_module 改成 sys.executable + '-c' 不行 (run_step 写死 [python, -m, lab_analysis.x])。
        所以改为直接 monkeypatch run_step 内部 subprocess.run。
        """
        return -1  # placeholder

    def test_run_step_fatal_true_exits_on_failure(self, monkeypatch, capsys):
        # 模拟子进程返回 rc=2
        fake_result = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="boom")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        with pytest.raises(SystemExit) as exc:
            steps.run_step("mock-step", "this_module_does_not_exist", fatal=True)
        assert exc.value.code == 1

    def test_run_step_fatal_false_returns_nonzero(self, monkeypatch, capsys):
        fake_result = subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="boom")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        rc = steps.run_step("mock-step", "this_module_does_not_exist", fatal=False)
        assert rc == 2

    def test_run_step_success_returns_zero(self, monkeypatch, capsys):
        fake_result = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok", stderr="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake_result)
        rc = steps.run_step("ok-step", "fake_module", fatal=True)
        assert rc == 0

    def test_run_step_subprocess_exception_fatal(self, monkeypatch):
        def _raise(*a, **kw):
            raise OSError("simulated spawn failure")

        monkeypatch.setattr(subprocess, "run", _raise)
        with pytest.raises(SystemExit):
            steps.run_step("err-step", "fake", fatal=True)

    def test_run_step_subprocess_exception_nonfatal(self, monkeypatch):
        def _raise(*a, **kw):
            raise OSError("simulated spawn failure")

        monkeypatch.setattr(subprocess, "run", _raise)
        rc = steps.run_step("err-step", "fake", fatal=False)
        assert rc == 1  # 异常时统一返回 1


class TestPipelineStepAcceptsArgs:
    def test_passes_args_through(self):
        captured = []

        @steps.pipeline_step(name="with-args")
        def s(x, y, z=None):
            captured.append((x, y, z))
            return True

        rc = s(1, 2, z=3)
        assert rc == 0
        assert captured == [(1, 2, 3)]

    def test_passes_kwargs_through(self):
        captured = []

        @steps.pipeline_step(name="with-kwargs")
        def s(**kw):
            captured.append(kw)
            return True

        rc = s(a=1, b=2)
        assert rc == 0
        assert captured == [{"a": 1, "b": 2}]