"""增量 compile (mtime 检测) 单元测试。

不调真实 DSPy / API, 只测 _is_up_to_date / _module_source_paths。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

import compile_all_dspy_modules_v2 as cam  # noqa: E402


@pytest.fixture
def fake_compile_layout(tmp_path: Path, monkeypatch) -> tuple[Path, Path, Path, Path]:
    """构造 src/ + compiled.json, monkeypatch _DSPY_SRC_DIR 到 tmp。

    Returns:
        (src_dir, fake_module_py, fake_retry_py, fake_compiled_json)
    """
    src_dir = tmp_path / "lab_analysis" / "dspy_modules"
    src_dir.mkdir(parents=True)
    fake_module = src_dir / "fake_module.py"
    fake_module.write_text("# v1\n")
    fake_retry = src_dir / "_retry.py"
    fake_retry.write_text("# v1\n")

    compiled_json = tmp_path / "fake_module_compiled.json"
    compiled_json.write_text("{}")

    monkeypatch.setattr(cam, "_DSPY_SRC_DIR", src_dir)
    return src_dir, fake_module, fake_retry, compiled_json


def test_module_source_paths_returns_existing(fake_compile_layout):
    src_dir, fake_module, fake_retry, _ = fake_compile_layout
    paths = cam._module_source_paths("fake_module")
    names = [p.name for p in paths]
    # fake_module.py 必含, _retry.py 必含
    assert "fake_module.py" in names
    assert "_retry.py" in names


def test_module_source_paths_filters_missing(fake_compile_layout):
    src_dir, _, _, _ = fake_compile_layout
    paths = cam._module_source_paths("nonexistent_module")
    # nonexistent_module.py 不存在 → 被过滤
    # _retry.py 存在 → 保留
    names = [p.name for p in paths]
    assert "nonexistent_module.py" not in names
    assert "_retry.py" in names


def test_is_up_to_date_json_missing(fake_compile_layout):
    _, _, _, compiled_json = fake_compile_layout
    compiled_json.unlink()
    assert cam._is_up_to_date(compiled_json, []) is False


def test_is_up_to_date_no_sources(fake_compile_layout):
    _, _, _, compiled_json = fake_compile_layout
    # 空 sources 列表 → 视为 up-to-date
    assert cam._is_up_to_date(compiled_json, []) is True


def test_is_up_to_date_json_newer(fake_compile_layout):
    _, fake_module, fake_retry, compiled_json = fake_compile_layout
    # json 比 source 新 1s
    time.sleep(0.05)
    fake_module.write_text("# v2\n")
    fake_retry.write_text("# v2\n")
    # 此时 source 更新, JSON 旧 → 应当重新编译
    assert cam._is_up_to_date(compiled_json, [fake_module, fake_retry]) is False


def test_is_up_to_date_source_older(fake_compile_layout):
    _, fake_module, fake_retry, compiled_json = fake_compile_layout
    # 把 source 的 mtime 倒回 1 小时前
    old_time = time.time() - 3600
    import os

    os.utime(fake_module, (old_time, old_time))
    os.utime(fake_retry, (old_time, old_time))
    assert cam._is_up_to_date(compiled_json, [fake_module, fake_retry]) is True


def test_is_up_to_date_one_source_newer(fake_compile_layout):
    """只要有一个 source 比 json 新, 就需要重编译。"""
    _, fake_module, fake_retry, compiled_json = fake_compile_layout
    # sleep 0.05s 跨过 Windows 文件系统的秒级 mtime 精度
    time.sleep(0.1)
    # fake_module 是最新写入, fake_retry 倒回 1h 前
    fake_module.write_text("# v2\n")
    old_time = time.time() - 3600
    import os

    os.utime(fake_retry, (old_time, old_time))
    assert cam._is_up_to_date(compiled_json, [fake_module, fake_retry]) is False


def test_is_up_to_date_missing_source_skipped(fake_compile_layout):
    """不存在的 source 文件 → 跳过 (视作没改动)。"""
    _, _, _, compiled_json = fake_compile_layout
    missing = fake_compile_layout[0] / "does_not_exist.py"
    # 只有 missing source + 旧 json → 仍然 up-to-date
    import os

    os.utime(compiled_json, (time.time(), time.time()))
    # 调一次让 JSON 的 mtime 更新 (上面已隐含)
    assert cam._is_up_to_date(compiled_json, [missing]) is True


def test_compile_skip_returns_none(monkeypatch):
    """compile_literature_interpreter 在 up-to-date 时 return None, 不调 DSPy。"""

    # stub 掉 optimizer.compile 确认未调
    def _boom(*a, **kw):
        raise AssertionError("optimizer.compile should not be called when skipping")

    import dspy.teleprompt

    monkeypatch.setattr(dspy.teleprompt, "BootstrapFewShot", _boom)

    # 临时把 source 改成比 compiled JSON 旧 (json_mtime - 1s)
    # 之前用 time.time() - 86400 不可靠: json mtime 可能与 "now - 24h" 几乎同时间
    # (甚至更晚), 导致 _is_up_to_date 误判为 False 走进 ensure_min_examples 越界。
    # 修法: 以 json mtime 为锚点, src 设到 json_mtime - 1, 必然 up-to-date。
    import os

    json_path = (
        Path(cam.__file__).resolve().parent.parent
        / "models"
        / "dspy"
        / "literature_interpreter_compiled.json"
    )
    if not json_path.exists():
        pytest.skip("compiled JSON 不存在, 无法测增量跳过路径")

    json_mtime = json_path.stat().st_mtime
    older_than_json = json_mtime - 1  # 仅早 1s, 但足够让 _is_up_to_date 返回 True
    # 修改全部依赖的 source (包括 prompt_inspector.py), 否则 _is_up_to_date 会因
    # 未触动的 source mtime > json mtime 而误判 False
    sources = cam._module_source_paths("literature_interpreter")
    for src in sources:
        os.utime(src, (older_than_json, older_than_json))

    # 显式断言 _is_up_to_date 走到 True, 早退到 return None (避免空 samples 越界)
    assert cam._is_up_to_date(json_path, sources) is True, (
        "测试前置条件失败: source 应早于 json mtime, 否则会跳过不到 return None"
    )

    result = cam.compile_literature_interpreter(samples=[], force=False)
    assert result is None
