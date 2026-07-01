"""tests.test_organize_local_files — 文件归档模块单测。"""

from __future__ import annotations

from pathlib import Path

from lab_analysis.organize_local_files import build_paths, copy_file_to_folder, create_local_folder


class TestBuildPaths:
    def test_returns_dict(self):
        paths = build_paths("p001")
        assert isinstance(paths, dict)

    def test_has_data_key(self):
        paths = build_paths("p001")
        assert "data" in paths


class TestCreateLocalFolder:
    def test_creates_folder(self, tmp_path):
        target = tmp_path / "new_folder"
        assert create_local_folder(target) is True
        assert target.exists()

    def test_existing_folder_returns_true(self, tmp_path):
        target = tmp_path / "existing"
        target.mkdir()
        assert create_local_folder(target) is True


class TestCopyFileToFolder:
    def test_copies_file(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("hello")
        dst = tmp_path / "dest"
        dst.mkdir()
        assert copy_file_to_folder(src, dst) is True
        assert (dst / "source.txt").exists()
