"""Unit tests for lab_analysis.ingest_data package."""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

import lab_analysis.ingest_data._log as _log_mod
from lab_analysis.ingest_data import batch, dicom, lab
from lab_analysis.ingest_data.batch import print_batch_summary, process_batch
from lab_analysis.ingest_data.dicom import (
    extract_dicom_from_zip,
    ingest_mri_dicom,
    rename_dicom_sequences,
)
from lab_analysis.ingest_data.lab import ingest_lab_image, save_image
from lab_analysis.ingest_data.report import ingest_mri_report

VALID_ID = "11010119900307881X"


@pytest.fixture
def isolated_work_root(tmp_path, monkeypatch):
    """Point WORK_ROOT to a tmp dir, reset ingest log + handlers."""
    monkeypatch.setattr(_log_mod, "WORK_ROOT", tmp_path)
    monkeypatch.setattr(_log_mod, "INGEST_LOG", tmp_path / ".ingest_log.json")
    monkeypatch.setattr(_log_mod, "LOG_FILE", tmp_path / ".ingest_debug.log")
    monkeypatch.setattr(lab, "WORK_ROOT", tmp_path)
    monkeypatch.setattr(dicom, "WORK_ROOT", tmp_path)
    monkeypatch.setattr(batch, "INGEST_LOG", tmp_path / ".ingest_log.json")
    return tmp_path


def _log_path() -> Path:
    """Always read INGEST_LOG fresh from the module (monkeypatch-safe)."""
    return _log_mod.INGEST_LOG


class TestAppendLog:
    def test_creates_file_on_first_append(self, isolated_work_root):
        rec = {"type": "lab_image", "patient_id_obf": "X"}
        _log_mod.append_log(rec)
        assert _log_path().exists()
        data = json.loads(_log_path().read_text(encoding="utf-8"))
        assert data["ingested"] == [rec]
        assert "last_updated" in data

    def test_appends_to_existing(self, isolated_work_root):
        _log_mod.append_log({"a": 1})
        _log_mod.append_log({"b": 2})
        data = json.loads(_log_path().read_text(encoding="utf-8"))
        assert data["ingested"] == [{"a": 1}, {"b": 2}]


class TestSaveImage:
    def test_copies_file_under_patient_lab(self, isolated_work_root, tmp_path):
        src = tmp_path / "src.jpg"
        src.write_bytes(b"fake jpg")
        result = save_image(src, "DEID01", "2026-03-24", "outpatient", "lab")
        expected = isolated_work_root / "raw" / "patient_DEID01" / "lab" / "src.jpg"
        assert expected.exists()
        assert result == str(expected.relative_to(isolated_work_root))

    def test_renames_on_collision(self, isolated_work_root, tmp_path):
        src1 = tmp_path / "report.jpg"
        src1.write_bytes(b"a")
        save_image(src1, "DEID02", "2026-01-01", "outpatient", "lab")
        src2 = tmp_path / "report.jpg"
        src2.write_bytes(b"b")
        result = save_image(src2, "DEID02", "2026-01-01", "outpatient", "lab")
        assert "report_" in result  # report_HHMMSS.jpg


class TestIngestLabImage:
    def test_records_metadata(self, isolated_work_root, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "lab_analysis.pipeline.cli.get_deid", lambda x: "DEID03"
        )
        src = tmp_path / "lab.jpg"
        src.write_bytes(b"x")
        rec = ingest_lab_image(src, VALID_ID, "2026-03-24", "outpatient")
        assert rec["type"] == "lab_image"
        assert rec["patient_id_obf"] == "DEID03"
        assert rec["report_date"] == "2026-03-24"
        assert rec["report_type"] == "outpatient"
        assert _log_path().exists()
        data = json.loads(_log_path().read_text(encoding="utf-8"))
        assert len(data["ingested"]) == 1


class TestIngestMriReport:
    def test_saves_to_papers_subdir(self, isolated_work_root, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "lab_analysis.pipeline.cli.get_deid", lambda x: "DEID04"
        )
        src = tmp_path / "mri_report.txt"
        src.write_text("MRI 报告内容")
        rec = ingest_mri_report(src, VALID_ID, "2026-04-11")
        expected = (isolated_work_root / "raw" / "patient_DEID04" /
                    "papers" / "mri_report.txt")
        assert expected.exists()
        assert rec["type"] == "mri_report"
        assert rec["patient_id_obf"] == "DEID04"


class TestProcessBatch:
    def test_returns_success_fail_counts(self, isolated_work_root):
        def proc(item):
            if item == "bad":
                return None
            return {"type": "x", "value": item}

        # batch_mode=True: 不在 None 时 short-circuit，继续处理
        ok, fail = process_batch(["a", "bad", "b"], proc, batch_mode=True)
        assert ok == 2
        assert fail == 1

    def test_non_batch_mode_short_circuits_on_none(self, isolated_work_root):
        def proc(item):
            return None

        ok, fail = process_batch(["first", "second"], proc, batch_mode=False)
        assert (ok, fail) == (0, 1)

    def test_batch_mode_continues_after_failure(self, isolated_work_root):
        def proc(item):
            if item == "bad":
                raise ValueError("nope")
            return {"type": "x", "value": item}

        ok, fail = process_batch(["a", "bad", "b"], proc, batch_mode=True)
        assert ok == 2
        assert fail == 1

    def test_non_batch_mode_raises(self, isolated_work_root):
        def proc(item):
            raise ValueError("boom")

        with pytest.raises(ValueError):
            process_batch(["x"], proc, batch_mode=False)


class TestPrintBatchSummary:
    def test_prints_summary(self, isolated_work_root, caplog):
        _log_mod.append_log({"type": "x", "value": 1})
        with caplog.at_level("INFO", logger="ingest_data"):
            print_batch_summary(3, 1, "extra info")
        # logger 写到 caplog（不经过 capsys）
        assert "3" in caplog.text
        assert "1" in caplog.text


class TestExtractDicomFromZip:
    def test_raises_when_no_dcm_in_zip(self, isolated_work_root, tmp_path):
        z = tmp_path / "empty.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("readme.txt", "no dcm here")
        with pytest.raises(FileNotFoundError):
            extract_dicom_from_zip(z, tmp_path / "out")

    def test_extracts_dcm_files_to_temp_dir(self, isolated_work_root, tmp_path):
        z = tmp_path / "dicom.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("series01/a.dcm", b"fake1")
            zf.writestr("series01/b.dcm", b"fake2")
        result = extract_dicom_from_zip(z, tmp_path / "out")
        # 有子目录时返回 temp_dir 本身，文件在 series01/ 下
        assert (result / "series01" / "a.dcm").exists()
        assert (result / "series01" / "b.dcm").exists()


class TestRenameDicomSequences:
    def test_renames_seq_dirs(self, isolated_work_root, tmp_path):
        src = tmp_path / "src"
        (src / "S1").mkdir(parents=True)
        (src / "S1" / "a.dcm").write_bytes(b"1")
        (src / "S2").mkdir(parents=True)
        (src / "S2" / "b.dcm").write_bytes(b"2")
        target = tmp_path / "tgt"
        n = rename_dicom_sequences(src, target)
        assert n == 2
        assert (target / "seq_01").exists()
        assert (target / "seq_02").exists()

    def test_skips_existing_target_seqs(self, isolated_work_root, tmp_path):
        src = tmp_path / "src"
        (src / "S1").mkdir(parents=True)
        (src / "S1" / "a.dcm").write_bytes(b"1")
        target = tmp_path / "tgt"
        (target / "seq_01").mkdir(parents=True)
        n = rename_dicom_sequences(src, target)
        assert n == 0

    def test_ignores_dirs_without_dcm(self, isolated_work_root, tmp_path):
        src = tmp_path / "src"
        (src / "S1").mkdir(parents=True)
        (src / "S1" / "a.dcm").write_bytes(b"1")
        (src / "S2").mkdir(parents=True)
        target = tmp_path / "tgt"
        n = rename_dicom_sequences(src, target)
        assert n == 1


class TestIngestMriDicom:
    def test_dicom_dir_branch(self, isolated_work_root, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "lab_analysis.pipeline.cli.get_deid", lambda x: "DEID05"
        )
        src = tmp_path / "src"
        (src / "S1").mkdir(parents=True)
        (src / "S1" / "a.dcm").write_bytes(b"1")
        rec = ingest_mri_dicom(dicom_dir=src, patient_id=VALID_ID,
                               report_date="2026-04-11")
        assert rec["type"] == "mri_dicom"
        assert rec["sequence_count"] == 1
        assert "patient_DEID05" in rec["saved_dir"]

    def test_no_source_raises(self, isolated_work_root, monkeypatch):
        monkeypatch.setattr(
            "lab_analysis.pipeline.cli.get_deid", lambda x: "DEID06"
        )
        with pytest.raises(ValueError, match="zip-path"):
            ingest_mri_dicom(patient_id=VALID_ID)

    def test_zip_path_branch_cleans_temp(
        self, isolated_work_root, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            "lab_analysis.pipeline.cli.get_deid", lambda x: "DEID07"
        )
        z = tmp_path / "d.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("series01/a.dcm", b"1")
            zf.writestr("series01/b.dcm", b"2")
        rec = ingest_mri_dicom(zip_path=z, patient_id=VALID_ID)
        assert rec["type"] == "mri_dicom"
        assert rec["sequence_count"] == 1


class TestMainCLI:
    def test_missing_type_exits(self, isolated_work_root, monkeypatch):
        """No --type → argparse exits with code 2 (standard argparse behavior)."""
        from lab_analysis.ingest_data import main as ingest_main
        monkeypatch.setattr(sys, "argv", ["ingest_data", "--id-card", VALID_ID])
        with pytest.raises(SystemExit) as exc:
            ingest_main()
        assert exc.value.code in (1, 2)

    def test_missing_id_card_exits(self, isolated_work_root, monkeypatch):
        from lab_analysis.ingest_data import main as ingest_main
        monkeypatch.setattr(sys, "argv", [
            "ingest_data", "--type", "lab_image"
        ])
        with pytest.raises(SystemExit) as exc:
            ingest_main()
        assert exc.value.code == 1

    def test_invalid_id_exits(self, isolated_work_root, monkeypatch):
        from lab_analysis.ingest_data import main as ingest_main
        # Mock validate_id_card to reject the bad id and not prompt
        monkeypatch.setattr(
            "lab_analysis.ingest_data.validate_id_card", lambda x: None
        )
        monkeypatch.setattr(sys, "argv", [
            "ingest_data", "--type", "lab_image", "--path", "x.jpg",
            "--id-card", "BAD"
        ])
        with pytest.raises(SystemExit) as exc:
            ingest_main()
        assert exc.value.code == 1

    def test_lab_image_path_missing_exits(
        self, isolated_work_root, monkeypatch
    ):
        from lab_analysis.ingest_data import main as ingest_main
        monkeypatch.setattr(sys, "argv", [
            "ingest_data", "--type", "lab_image", "--id-card", VALID_ID
        ])
        with pytest.raises(SystemExit) as exc:
            ingest_main()
        assert exc.value.code == 1

    def test_mri_dicom_no_source_exits(self, isolated_work_root, monkeypatch):
        from lab_analysis.ingest_data import main as ingest_main
        monkeypatch.setattr(sys, "argv", [
            "ingest_data", "--type", "mri_dicom", "--id-card", VALID_ID
        ])
        with pytest.raises(SystemExit) as exc:
            ingest_main()
        assert exc.value.code == 1

    def test_mri_report_path_missing_exits(
        self, isolated_work_root, monkeypatch
    ):
        from lab_analysis.ingest_data import main as ingest_main
        monkeypatch.setattr(sys, "argv", [
            "ingest_data", "--type", "mri_report", "--id-card", VALID_ID
        ])
        with pytest.raises(SystemExit) as exc:
            ingest_main()
        assert exc.value.code == 1

    def test_lab_image_happy_path(
        self, isolated_work_root, tmp_path, monkeypatch
    ):
        from lab_analysis.ingest_data import main as ingest_main
        monkeypatch.setattr(
            "lab_analysis.pipeline.cli.get_deid", lambda x: "DEIDH1"
        )
        src = tmp_path / "lab.jpg"
        src.write_bytes(b"x")
        monkeypatch.setattr(sys, "argv", [
            "ingest_data", "--type", "lab_image",
            "--path", str(src), "--id-card", VALID_ID,
            "--report-date", "2026-03-24", "--report-type", "outpatient"
        ])
        ingest_main()
        target = (isolated_work_root / "raw" / "patient_DEIDH1" /
                  "lab" / "lab.jpg")
        assert target.exists()