"""tests.test_batch_vision_extract — 批量视觉提取模块单测。"""

from __future__ import annotations

from lab_analysis.batch_vision_extract import get_project_root, get_venv_python


def test_get_project_root():
    root = get_project_root()
    assert root.exists()
    assert (root / "pyproject.toml").exists()


def test_get_venv_python():
    path = get_venv_python()
    assert path is not None
    assert path.exists()
