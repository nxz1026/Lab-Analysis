"""tests.test_pipeline_ingest — Pipeline 数据摄入单测。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lab_analysis.pipeline.ingest import auto_ingest_from_origin_data


class TestAutoIngest:
    def test_no_origin_dir_returns_false(self, monkeypatch, tmp_path):
        monkeypatch.setattr("lab_analysis.pipeline.ingest.WORK_ROOT", tmp_path)
        result = auto_ingest_from_origin_data(id_card="test123")
        assert result is False

    def test_empty_origin_dir_returns_false(self, monkeypatch, tmp_path):
        origin_dir = tmp_path / "raw" / "Origin_data"
        origin_dir.mkdir(parents=True)
        monkeypatch.setattr("lab_analysis.pipeline.ingest.WORK_ROOT", tmp_path)
        result = auto_ingest_from_origin_data(id_card="test123")
        assert result is False

    def test_with_lab_image_calls_extract(self, monkeypatch, tmp_path):
        origin_dir = tmp_path / "raw" / "Origin_data"
        origin_dir.mkdir(parents=True)
        lab_file = origin_dir / "lab_2026-01-15_outpatient.jpg"
        lab_file.write_text("fake-image-data")
        monkeypatch.setattr("lab_analysis.pipeline.ingest.WORK_ROOT", tmp_path)

        def fake_main(args):
            return True

        monkeypatch.setattr("lab_analysis.extract_lab_data.main_with_args", fake_main)
        result = auto_ingest_from_origin_data(id_card="test123")
        assert result is True

    def test_error_during_processing_continues(self, monkeypatch, tmp_path):
        origin_dir = tmp_path / "raw" / "Origin_data"
        origin_dir.mkdir(parents=True)
        lab_file = origin_dir / "lab_broken.jpg"
        lab_file.write_text("data")
        monkeypatch.setattr("lab_analysis.pipeline.ingest.WORK_ROOT", tmp_path)

        def failing_main(**kwargs):
            msg = "模拟失败"
            raise ValueError(msg)

        monkeypatch.setattr("lab_analysis.extract_lab_data.main_with_args", failing_main)
        result = auto_ingest_from_origin_data(id_card="test123")
        assert result is False

    def test_date_extracted_from_filename(self, monkeypatch, tmp_path):
        origin_dir = tmp_path / "raw" / "Origin_data"
        origin_dir.mkdir(parents=True)
        lab_file = origin_dir / "lab_2026-06-15_inpatient.png"
        lab_file.write_text("data")
        monkeypatch.setattr("lab_analysis.pipeline.ingest.WORK_ROOT", tmp_path)
        captured = {}

        def capture_main(args):
            captured["args"] = args
            return True

        monkeypatch.setattr("lab_analysis.extract_lab_data.main_with_args", capture_main)
        auto_ingest_from_origin_data(id_card="test123")
        assert captured["args"].image == str(lab_file)
