"""tests.test_cleanup_runs — 产物清理工具测试"""

import pytest

from lab_analysis.cleanup_runs import (
    _format_size,
    _get_dir_size,
)


@pytest.fixture
def mock_data_dir(tmp_path):
    """模拟 data/<deid>/ 下 N 个时间戳子目录，每个含一个占位文件。"""
    deid = "test_deid_001"
    base = tmp_path / "data" / deid
    for ts in [
        "20260620_000230",
        "20260618_120000",
        "20260615_080000",
        "20260610_090000",
        "20260601_100000",
    ]:
        d = base / ts / "02_analyzed"
        d.mkdir(parents=True)
        (d / "analysis_results.json").write_text('{"test": 1}', encoding="utf-8")
    return tmp_path, deid


@pytest.fixture
def mock_empty_patient(tmp_path):
    """模拟 data/<deid>/ 为空（无时间戳子目录）。"""
    deid = "empty_patient"
    (tmp_path / "data" / deid / "02_analyzed").mkdir(parents=True)
    return tmp_path, deid


# ═════════════════════════════════════════════════════════════════════
# 1. 目录大小计算
# ═════════════════════════════════════════════════════════════════════


class TestGetDirSize:
    def test_returns_positive(self, mock_data_dir):
        tmp, deid = mock_data_dir
        size = _get_dir_size(tmp / "data" / deid / "20260620_000230")
        assert size > 0

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert _get_dir_size(d) == 0


# ═════════════════════════════════════════════════════════════════════
# 2. 大小格式化
# ═════════════════════════════════════════════════════════════════════


class TestFormatSize:
    def test_bytes(self):
        assert "B" in _format_size(512)

    def test_kb(self):
        assert "KB" in _format_size(2048)

    def test_mb(self):
        assert "MB" in _format_size(2 * 1024 * 1024)


# ═════════════════════════════════════════════════════════════════════
# 3. 单患者清理
# ═════════════════════════════════════════════════════════════════════


class TestCleanupPatient:
    def test_keep_last_3(self, mock_data_dir, monkeypatch):
        tmp, deid = mock_data_dir
        monkeypatch.chdir(tmp)
        # 临时改 WORK_ROOT 指向 tmp
        import lab_analysis.cleanup_runs as cr

        original = cr._DATA_DIR
        cr._DATA_DIR = tmp / "data"

        try:
            result = cr.cleanup_patient(deid, keep_last=3, dry_run=True)
            assert len(result["kept"]) == 3
            assert len(result["deleted"]) == 2  # 5 total - 3 kept
            assert result["freed_bytes"] > 0
        finally:
            cr._DATA_DIR = original

    def test_keep_last_10_all_kept(self, mock_data_dir, monkeypatch):
        tmp, deid = mock_data_dir
        import lab_analysis.cleanup_runs as cr

        original = cr._DATA_DIR
        cr._DATA_DIR = tmp / "data"

        try:
            result = cr.cleanup_patient(deid, keep_last=10, dry_run=True)
            assert len(result["kept"]) == 5
            assert len(result["deleted"]) == 0
        finally:
            cr._DATA_DIR = original

    def test_empty_patient_no_crash(self, mock_empty_patient, monkeypatch):
        tmp, deid = mock_empty_patient
        import lab_analysis.cleanup_runs as cr

        original = cr._DATA_DIR
        cr._DATA_DIR = tmp / "data"

        try:
            result = cr.cleanup_patient(deid, keep_last=3, dry_run=True)
            assert result["kept"] == []
            assert result["deleted"] == []
        finally:
            cr._DATA_DIR = original

    def test_dry_run_does_not_delete(self, mock_data_dir, monkeypatch):
        tmp, deid = mock_data_dir
        import lab_analysis.cleanup_runs as cr

        original = cr._DATA_DIR
        cr._DATA_DIR = tmp / "data"

        try:
            cr.cleanup_patient(deid, keep_last=3, dry_run=True)
            # 确认目录还在
            assert (tmp / "data" / deid / "20260601_100000").exists()
        finally:
            cr._DATA_DIR = original


# ═════════════════════════════════════════════════════════════════════
# 4. 全量清理
# ═════════════════════════════════════════════════════════════════════


class TestCleanupAll:
    def test_multiple_patients(self, tmp_path, monkeypatch):
        # 两个患者，各有若干批次
        p1 = tmp_path / "data" / "pat1"
        p2 = tmp_path / "data" / "pat2"
        for p in [p1, p2]:
            for ts in ["20260620_000230", "20260618_120000", "20260615_080000", "20260610_090000"]:
                (p / ts).mkdir(parents=True)
                (p / ts / "file.txt").write_text("x")

        import lab_analysis.cleanup_runs as cr

        original = cr._DATA_DIR
        cr._DATA_DIR = tmp_path / "data"

        try:
            results = cr.cleanup_all(keep_last=2, dry_run=True)
            assert len(results) == 2
            for r in results:
                assert len(r["kept"]) == 2
                assert len(r["deleted"]) == 2
        finally:
            cr._DATA_DIR = original

    def test_id_card_filter(self, tmp_path, monkeypatch):
        p1 = tmp_path / "data" / "pat1"
        p2 = tmp_path / "data" / "pat2"
        for p in [p1, p2]:
            for ts in ["20260620_000230", "20260618_120000", "20260615_080000"]:
                (p / ts).mkdir(parents=True)

        import lab_analysis.cleanup_runs as cr

        original = cr._DATA_DIR
        cr._DATA_DIR = tmp_path / "data"

        try:
            results = cr.cleanup_all(keep_last=2, dry_run=True, id_card="pat1")
            assert len(results) == 1
            assert results[0]["deid"] == "pat1"
        finally:
            cr._DATA_DIR = original
