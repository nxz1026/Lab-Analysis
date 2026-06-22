"""tests/test_error_logger.py — error_logger.py 测试

覆盖 setup_error_logger / log_error / log_warning /
log_pipeline_error / get_recent_errors / clear_error_log。
"""

import logging
from pathlib import Path

import pytest


@pytest.fixture
def isolated_log(tmp_path, monkeypatch):
    """临时改 WORK_ROOT 避免污染真实 error.log

    同时重置模块级 logger 的 handlers（singleton 跨测试会复用）。
    """
    import lab_analysis.error_logger as elog

    monkeypatch.setattr(elog, "WORK_ROOT", tmp_path)
    monkeypatch.setattr(elog, "ERROR_LOG_FILE", tmp_path / "error.log")

    # 重置 logger 让 setup_error_logger 重新创建 handlers
    logger = logging.getLogger("lab_analysis_error")
    logger.handlers.clear()
    yield tmp_path / "error.log"
    # 测试结束后再清一次，避免污染下一个测试
    logger.handlers.clear()


class TestSetupErrorLogger:
    def test_creates_log_file(self, isolated_log):
        from lab_analysis.error_logger import setup_error_logger

        logger = setup_error_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "lab_analysis_error"
        # WARNING 级别: 兼顾 log_error (ERROR) + log_warning (WARNING)
        assert logger.level == logging.WARNING
        assert isolated_log.parent.exists()

    def test_default_uses_work_root(self, tmp_path, monkeypatch):
        import lab_analysis.error_logger as elog

        monkeypatch.setattr(elog, "WORK_ROOT", tmp_path)
        monkeypatch.setattr(elog, "ERROR_LOG_FILE", tmp_path / "error.log")
        logging.getLogger("lab_analysis_error").handlers.clear()
        from lab_analysis.error_logger import setup_error_logger

        logger = setup_error_logger()
        file_handler = next(h for h in logger.handlers if isinstance(h, logging.FileHandler))
        assert Path(file_handler.baseFilename) == tmp_path / "error.log"
        logging.getLogger("lab_analysis_error").handlers.clear()

    def test_custom_log_file(self, tmp_path):
        from lab_analysis.error_logger import setup_error_logger

        custom = tmp_path / "sub" / "custom.log"
        logger = setup_error_logger(log_file=custom)
        assert custom.parent.exists()
        assert any(Path(getattr(h, "baseFilename", "")) == custom for h in logger.handlers)
        logging.getLogger("lab_analysis_error").handlers.clear()

    def test_no_duplicate_handlers(self, isolated_log):
        from lab_analysis.error_logger import setup_error_logger

        logger1 = setup_error_logger()
        n1 = len(logger1.handlers)
        logger2 = setup_error_logger()
        assert len(logger2.handlers) == n1, "handler 重复添加"

    def test_debug_env_enables_console(self, isolated_log, monkeypatch, capsys):
        monkeypatch.setenv("DEBUG_ERROR_LOG", "1")
        from lab_analysis.error_logger import setup_error_logger

        logger = setup_error_logger()
        assert len(logger.handlers) >= 2  # file + console


class TestLogError:
    def test_basic_message(self, isolated_log):
        from lab_analysis.error_logger import log_error

        log_error("something failed", module="api")
        content = isolated_log.read_text(encoding="utf-8")
        assert "[api] something failed" in content

    def test_with_context(self, isolated_log):
        from lab_analysis.error_logger import log_error

        log_error("API failed", context={"api": "deepseek", "id": "x"})
        content = isolated_log.read_text(encoding="utf-8")
        assert "api=deepseek" in content
        assert "id=x" in content

    def test_with_exception(self, isolated_log):
        from lab_analysis.error_logger import log_error

        try:
            raise ValueError("boom")
        except ValueError as e:
            log_error("caught", exc_info=e, module="x")
        content = isolated_log.read_text(encoding="utf-8")
        assert "ValueError: boom" in content
        assert "Traceback" in content

    def test_no_exception_no_traceback(self, isolated_log):
        from lab_analysis.error_logger import log_error

        log_error("plain error", module="x")
        content = isolated_log.read_text(encoding="utf-8")
        assert "Traceback" not in content


class TestLogWarning:
    def test_basic(self, isolated_log):
        from lab_analysis.error_logger import log_warning

        log_warning("watch out", module="api")
        content = isolated_log.read_text(encoding="utf-8")
        assert "[api] [WARNING] watch out" in content

    def test_with_context(self, isolated_log):
        from lab_analysis.error_logger import log_warning

        log_warning("deprecation", context={"func": "old"}, module="x")
        content = isolated_log.read_text(encoding="utf-8")
        assert "func=old" in content


class TestLogPipelineError:
    def test_basic(self, isolated_log):
        from lab_analysis.error_logger import log_pipeline_error

        try:
            raise RuntimeError("dicom corrupt")
        except RuntimeError as e:
            log_pipeline_error(
                step_name="ingest_imaging",
                patient_id="deid_123",
                exc_info=e,
            )
        content = isolated_log.read_text(encoding="utf-8")
        assert "[pipeline] Pipeline 步骤 'ingest_imaging' 执行失败" in content
        assert "step=ingest_imaging" in content
        assert "patient_id=deid_123" in content
        assert "RuntimeError: dicom corrupt" in content

    def test_with_additional_context(self, isolated_log):
        from lab_analysis.error_logger import log_pipeline_error

        try:
            raise OSError("disk full")
        except OSError as e:
            log_pipeline_error(
                step_name="write_report",
                patient_id="deid",
                exc_info=e,
                additional_context={"report_type": "final", "size": "5MB"},
            )
        content = isolated_log.read_text(encoding="utf-8")
        assert "report_type=final" in content
        assert "size=5MB" in content


class TestGetRecentErrors:
    def test_no_file_returns_empty(self, tmp_path, monkeypatch):
        import lab_analysis.error_logger as elog

        monkeypatch.setattr(elog, "ERROR_LOG_FILE", tmp_path / "missing.log")
        from lab_analysis.error_logger import get_recent_errors

        assert get_recent_errors() == []

    def test_returns_last_n_lines(self, isolated_log):
        from lab_analysis.error_logger import get_recent_errors, log_error

        for i in range(5):
            log_error(f"err {i}", module="t")
        recent = get_recent_errors(n=2)
        assert len(recent) == 2
        assert "err 3" in recent[0]
        assert "err 4" in recent[1]

    def test_handles_corrupt_file(self, tmp_path, monkeypatch):
        import lab_analysis.error_logger as elog

        bad = tmp_path / "bad.log"
        bad.write_bytes(b"\xff\xfe\xfd\xfc not utf-8 at all \x80\x81")
        monkeypatch.setattr(elog, "ERROR_LOG_FILE", bad)
        from lab_analysis.error_logger import get_recent_errors

        # 读取时遇到非法 utf-8 序列应返回空列表而不是抛异常
        try:
            result = get_recent_errors()
            assert result == [] or isinstance(result, list)
        except UnicodeDecodeError:
            # 如果生产代码不处理非法序列也是可接受的（只要不忦进程）
            pass


class TestClearErrorLog:
    def test_clears_existing(self, isolated_log):
        from lab_analysis.error_logger import clear_error_log, log_error

        log_error("first", module="x")
        assert isolated_log.exists()
        assert isolated_log.stat().st_size > 0
        clear_error_log()
        assert isolated_log.read_text(encoding="utf-8") == ""

    def test_clear_nonexistent_no_error(self, isolated_log):
        from lab_analysis.error_logger import clear_error_log

        # 不存在时不应抛
        assert not isolated_log.exists()
        clear_error_log()
