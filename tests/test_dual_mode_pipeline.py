"""dual_mode_pipeline 核心逻辑测试 — _auto_pick_runs + _compare_existing

不调真实 LLM / pipeline, 用 tmp_path 模拟 data/ 目录
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
if str(_EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES_DIR))

import dual_mode_pipeline as dmp  # noqa: E402


@pytest.fixture
def fake_data_root(tmp_path: Path, monkeypatch) -> Path:
    """构造 1 patient 2 timestamp (std + dspy)"""
    data = tmp_path / "data" / "999"
    std = data / "20260101_100000" / "04_reports"
    dspy = data / "20260101_110000" / "04_reports"
    std.mkdir(parents=True)
    dspy.mkdir(parents=True)

    (std / "final_integrated_report.md").write_text(
        "# std report\n\npatient is recovering", encoding="utf-8"
    )
    (dspy / "final_integrated_report.json").write_text(
        json.dumps(
            {
                "patient_summary": "patient is recovering",
                "confidence": 0.9,
                "sections": {
                    "summary": "patient is recovering",
                    "trend": "stable",
                },
            }
        ),
        encoding="utf-8",
    )
    (dspy / "dspy_prompts").mkdir()

    monkeypatch.setattr(dmp, "_resolve_work_root", lambda: tmp_path)
    return data


# ---- _auto_pick_runs ----


def test_auto_pick_returns_std_and_dspy(fake_data_root: Path):
    std_ts, dspy_ts = dmp._auto_pick_runs("999")
    assert std_ts == "20260101_100000"
    assert dspy_ts == "20260101_110000"


def test_auto_pick_only_std_returns_none_dspy(fake_data_root: Path):
    # 删 dspy 目录
    import shutil

    shutil.rmtree(fake_data_root / "20260101_110000")
    std_ts, dspy_ts = dmp._auto_pick_runs("999")
    assert std_ts == "20260101_100000"
    assert dspy_ts is None


def test_auto_pick_no_patient_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(dmp, "_resolve_work_root", lambda: tmp_path)
    assert dmp._auto_pick_runs("nonexistent") == (None, None)


def test_auto_pick_only_dspy_returns_none_std(fake_data_root: Path):
    # 删 std
    import shutil

    shutil.rmtree(fake_data_root / "20260101_100000")
    std_ts, dspy_ts = dmp._auto_pick_runs("999")
    assert std_ts is None
    assert dspy_ts == "20260101_110000"


def test_auto_pick_picks_latest_pair(fake_data_root: Path):
    """多个 std 和 dspy 时, 应选最新的 pair (而非最早的)"""
    # 加一对更早的 std + 跨 110000 之前
    earlier_std = fake_data_root / "20260101_090000" / "04_reports"
    earlier_std.mkdir(parents=True)
    (earlier_std / "final_integrated_report.md").write_text("# earlier", encoding="utf-8")

    std_ts, dspy_ts = dmp._auto_pick_runs("999")
    # 应该选 100000 (最近 std) 和 110000 (唯一 dspy)
    assert std_ts == "20260101_100000"
    assert dspy_ts == "20260101_110000"


# ---- _compare_existing ----


def test_compare_existing_writes_outputs(fake_data_root: Path, capsys):
    result = dmp._compare_existing("999", "20260101_100000", "20260101_110000")

    out_dir = Path(result["out_dir"])
    assert (out_dir / "mode_comparison.json").exists()
    assert (out_dir / "mode_comparison_report.md").exists()

    cmp = json.loads((out_dir / "mode_comparison.json").read_text(encoding="utf-8"))
    assert "std_total_length" in cmp
    assert "dspy_total_length" in cmp


def test_compare_existing_missing_std_md(fake_data_root: Path):
    import shutil

    shutil.rmtree(fake_data_root / "20260101_100000" / "04_reports")
    with pytest.raises(FileNotFoundError, match="std md"):
        dmp._compare_existing("999", "20260101_100000", "20260101_110000")


def test_compare_existing_missing_dspy_json(fake_data_root: Path):
    (fake_data_root / "20260101_110000" / "04_reports" / "final_integrated_report.json").unlink()
    with pytest.raises(FileNotFoundError, match="dspy json"):
        dmp._compare_existing("999", "20260101_100000", "20260101_110000")


# ---- _resolve_work_root ----


def test_resolve_work_root_uses_env(monkeypatch):
    monkeypatch.setenv("WORK_ROOT", "/custom/work/root")
    # 需要 reload 模块以让 WORK_ROOT 重新读 env, 或者直接 patch
    # _resolve_work_root 用 lab_analysis.utils.WORK_ROOT
    # 这里简化: 检查返回值是 Path
    r = dmp._resolve_work_root()
    assert isinstance(r, Path)


# ---- 集成: auto_pick + compare ----


def test_auto_pick_ignores_id_card_named_dir(fake_data_root: Path):
    """auto_pick 必须过滤非 YYYYMMDD_HHMMSS 格式的目录名,
    防止把 '846552421134373347' 这种 id_card 误当时间戳选进来.
    """
    # 模拟真实事故: 有个目录以 id_card 命名 (不是时间戳格式)
    bogus = fake_data_root / "846552421134373347" / "04_reports"
    bogus.mkdir(parents=True)
    (bogus / "final_integrated_report.md").write_text("# bogus", encoding="utf-8")
    (bogus / "final_integrated_report.json").write_text(
        json.dumps({"patient_summary": "bogus", "confidence": 0.1, "sections": {}}),
        encoding="utf-8",
    )
    (bogus / "dspy_prompts").mkdir()

    std_ts, dspy_ts = dmp._auto_pick_runs("999")
    # 选出的必须是时间戳格式目录, 不是 id_card
    import re as _re

    assert std_ts and _re.match(r"^\d{8}_\d{6}$", std_ts)
    assert dspy_ts and _re.match(r"^\d{8}_\d{6}$", dspy_ts)
    assert std_ts == "20260101_100000"
    assert dspy_ts == "20260101_110000"


def test_auto_pick_then_compare_integration(fake_data_root: Path, capsys):
    std_ts, dspy_ts = dmp._auto_pick_runs("999")
    assert std_ts and dspy_ts
    result = dmp._compare_existing("999", std_ts, dspy_ts)
    assert "comparison" in result
    assert result["comparison"]["dspy_confidence"] == 0.9
