"""inject_compile_metadata 注入工具测试

覆盖: get_git_head / get_latest_src_mtime / inject_metadata
不依赖真实 git / models/dspy/, 用 tmp_path + monkeypatch
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest


# inject_compile_metadata 是 scripts/ 子包,需把 scripts/ 加到 path
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import inject_compile_metadata as icm  # noqa: E402


@pytest.fixture
def fake_compiled_json(tmp_path: Path) -> Path:
    """最小可用的 DSPy compiled JSON"""
    p = tmp_path / "fake_compiled.json"
    p.write_text(
        json.dumps(
            {
                "metadata": {
                    "dependency_versions": {"python": "3.14", "dspy": "3.2.1"},
                },
                "predictor": {"key": "value"},
            }
        ),
        encoding="utf-8",
    )
    return p


def test_inject_metadata_writes_new_fields(fake_compiled_json: Path, monkeypatch):
    monkeypatch.setattr(icm, "get_git_head", lambda: "abc1234")
    # 注入 src mtime 比 json mtime 早 -> 不是 STALE
    monkeypatch.setattr(icm, "get_latest_src_mtime", lambda: fake_compiled_json.stat().st_mtime - 10)

    r = icm.inject_metadata(fake_compiled_json)
    assert "error" not in r
    assert r["source_commit"] == "abc1234"
    assert r["is_stale"] is False

    data = json.loads(fake_compiled_json.read_text(encoding="utf-8"))
    assert "compiled_at" in data["metadata"]
    assert "source_commit" in data["metadata"]
    assert data["metadata"]["source_commit"] == "abc1234"
    assert data["metadata"]["injector_version"] == "1.0.0"
    # 原 dependency_versions 保留
    assert data["metadata"]["dependency_versions"] == {"python": "3.14", "dspy": "3.2.1"}


def test_inject_metadata_preserves_existing_metadata(fake_compiled_json: Path, monkeypatch):
    monkeypatch.setattr(icm, "get_git_head", lambda: "deadbeef")
    monkeypatch.setattr(icm, "get_latest_src_mtime", lambda: 0.0)

    icm.inject_metadata(fake_compiled_json)

    data = json.loads(fake_compiled_json.read_text(encoding="utf-8"))
    meta = data["metadata"]
    # 注入字段都在
    for k in ("compiled_at", "source_commit", "latest_src_mtime", "injected_at", "injector_version"):
        assert k in meta
    # 原有字段保留
    assert "dependency_versions" in meta


def test_inject_metadata_detects_stale(fake_compiled_json: Path, monkeypatch):
    monkeypatch.setattr(icm, "get_git_head", lambda: "x")
    # src mtime 比 json mtime 晚 -> STALE
    monkeypatch.setattr(icm, "get_latest_src_mtime", lambda: fake_compiled_json.stat().st_mtime + 100)

    r = icm.inject_metadata(fake_compiled_json)
    assert r["is_stale"] is True


def test_inject_metadata_dry_run_does_not_write(fake_compiled_json: Path, monkeypatch):
    monkeypatch.setattr(icm, "get_git_head", lambda: "x")
    monkeypatch.setattr(icm, "get_latest_src_mtime", lambda: 0.0)
    before = fake_compiled_json.read_text(encoding="utf-8")

    r = icm.inject_metadata(fake_compiled_json, dry_run=True)
    assert r["dry_run"] is True

    after = fake_compiled_json.read_text(encoding="utf-8")
    assert before == after


def test_inject_metadata_creates_backup(fake_compiled_json: Path, monkeypatch):
    monkeypatch.setattr(icm, "get_git_head", lambda: "x")
    monkeypatch.setattr(icm, "get_latest_src_mtime", lambda: 0.0)

    icm.inject_metadata(fake_compiled_json)

    bak = fake_compiled_json.with_suffix(fake_compiled_json.suffix + ".bak")
    assert bak.exists()
    # 备份是注入前的内容 (无 compiled_at)
    bak_data = json.loads(bak.read_text(encoding="utf-8"))
    assert "compiled_at" not in bak_data["metadata"]


def test_inject_metadata_no_backup_on_second_run(fake_compiled_json: Path, monkeypatch):
    monkeypatch.setattr(icm, "get_git_head", lambda: "x")
    monkeypatch.setattr(icm, "get_latest_src_mtime", lambda: 0.0)

    icm.inject_metadata(fake_compiled_json)
    # 第二次注入: .bak 已存在 -> 不覆盖
    bak = fake_compiled_json.with_suffix(fake_compiled_json.suffix + ".bak")
    first_bak_mtime = bak.stat().st_mtime

    # 重新写入 bak 时间戳检测
    import time

    time.sleep(0.05)

    icm.inject_metadata(fake_compiled_json)
    assert bak.stat().st_mtime == first_bak_mtime  # 未覆盖


def test_inject_metadata_missing_file(tmp_path: Path):
    r = icm.inject_metadata(tmp_path / "nonexistent.json")
    assert r["error"] == "file not found"


def test_get_git_head_returns_unknown_on_failure(monkeypatch, tmp_path: Path):
    # 把 ROOT 指向空目录, git rev-parse 必失败
    monkeypatch.setattr(icm, "ROOT", tmp_path)
    assert icm.get_git_head() == "unknown"


def test_get_latest_src_mtime_returns_max(tmp_path: Path, monkeypatch):
    # 构造两个 .py, 第二个 mtime 较新
    src = tmp_path / "dspy_modules"
    src.mkdir()
    f1 = src / "a.py"
    f2 = src / "b.py"
    f1.write_text("a", encoding="utf-8")
    import time

    time.sleep(0.05)
    f2.write_text("b", encoding="utf-8")

    monkeypatch.setattr(icm, "SRC_DIR", src)
    expected = max(f1.stat().st_mtime, f2.stat().st_mtime)
    assert icm.get_latest_src_mtime() == expected


def test_get_latest_src_mtime_empty_dir(tmp_path: Path, monkeypatch):
    src = tmp_path / "empty"
    src.mkdir()
    monkeypatch.setattr(icm, "SRC_DIR", src)
    assert icm.get_latest_src_mtime() == 0.0


def test_inject_metadata_compiled_at_is_iso(fake_compiled_json: Path, monkeypatch):
    monkeypatch.setattr(icm, "get_git_head", lambda: "x")
    monkeypatch.setattr(icm, "get_latest_src_mtime", lambda: 0.0)

    icm.inject_metadata(fake_compiled_json)
    data = json.loads(fake_compiled_json.read_text(encoding="utf-8"))
    # 验证是合法 ISO
    datetime.fromisoformat(data["metadata"]["compiled_at"])


def test_inject_metadata_injected_at_after_compiled_at(fake_compiled_json: Path, monkeypatch):
    monkeypatch.setattr(icm, "get_git_head", lambda: "x")
    monkeypatch.setattr(icm, "get_latest_src_mtime", lambda: 0.0)

    icm.inject_metadata(fake_compiled_json)
    data = json.loads(fake_compiled_json.read_text(encoding="utf-8"))
    meta = data["metadata"]
    # 编译时间 <= 注入时间
    assert meta["compiled_at"] <= meta["injected_at"]
