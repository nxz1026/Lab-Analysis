"""multi_patient 框架测试 — 覆盖 list_patients / find_pairs / _is_dspy_run / stats

使用 tmp_path 模拟 data/ 结构, 不依赖真实 patient 数据
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lab_analysis.dspy_modules.multi_patient import (
    Sample,
    find_pairs,
    iter_all_samples,
    list_patients,
    list_timestamps,
    load_summary_artifact,
    stats,
)


@pytest.fixture
def fake_data_root(monkeypatch, tmp_path: Path) -> Path:
    """构造一个伪 data/ 目录, 含 2 个 patient, 每个 patient 2 个 timestamp。

    结构:
        tmp_path/
            data/
                100/
                    20260101_100000/
                        04_reports/
                            final_integrated_report.md  (std)
                    20260101_110000/
                        04_reports/
                            final_integrated_report.md
                            final_integrated_report.json
                            dspy_prompts/   (dspy)
                200/
                    20260201_090000/
                        04_reports/
                            final_integrated_report.md  (std)
    """
    data = tmp_path / "data"
    data.mkdir()

    # patient 100
    p1 = data / "100"
    for ts, is_dspy in [("20260101_100000", False), ("20260101_110000", True)]:
        tsdir = p1 / ts
        rep = tsdir / "04_reports"
        rep.mkdir(parents=True)
        (rep / "final_integrated_report.md").write_text(f"# std report {ts}", encoding="utf-8")
        if is_dspy:
            (rep / "final_integrated_report.json").write_text("{}", encoding="utf-8")
            (rep / "dspy_prompts").mkdir()

    # patient 200
    p2 = data / "200" / "20260201_090000" / "04_reports"
    p2.mkdir(parents=True)
    (p2 / "final_integrated_report.md").write_text("# std 200", encoding="utf-8")

    # patch get_data_root -> 指向 tmp_path/data
    from lab_analysis.dspy_modules import multi_patient

    monkeypatch.setattr(multi_patient, "get_data_root", lambda: data)
    return data


def test_list_patients_sorted(fake_data_root: Path):
    assert list_patients() == ["100", "200"]


def test_list_patients_empty_when_no_data_dir(monkeypatch, tmp_path: Path):
    from lab_analysis.dspy_modules import multi_patient

    monkeypatch.setattr(multi_patient, "get_data_root", lambda: tmp_path / "nonexistent")
    assert list_patients() == []


def test_list_timestamps_sorted(fake_data_root: Path):
    assert list_timestamps("100") == ["20260101_100000", "20260101_110000"]
    assert list_timestamps("200") == ["20260201_090000"]
    assert list_timestamps("nonexistent") == []


def test_iter_all_samples_yields_dataclass(fake_data_root: Path):
    samples = list(iter_all_samples())
    assert len(samples) == 3
    for s in samples:
        assert isinstance(s, Sample)
        assert isinstance(s.data_dir, Path)
        assert s.data_dir.is_dir()


def test_iter_all_samples_filtered_by_patient(fake_data_root: Path):
    samples = list(iter_all_samples(patient_ids=["100"]))
    assert len(samples) == 2
    assert {s.patient_id for s in samples} == {"100"}


def test_is_dspy_detection(fake_data_root: Path):
    samples = list(iter_all_samples())
    by_ts = {s.timestamp: s for s in samples}

    # 100/20260101_100000: md exists, no dspy_prompts -> std
    assert by_ts["20260101_100000"].is_dspy is False
    assert by_ts["20260101_100000"].has_final_md is True

    # 100/20260101_110000: dspy_prompts exists -> dspy
    assert by_ts["20260101_110000"].is_dspy is True

    # 200/20260201_090000: std
    assert by_ts["20260201_090000"].is_dspy is False


def test_find_pairs_100_has_one_pair(fake_data_root: Path):
    pairs = find_pairs("100")
    assert pairs == [("20260101_100000", "20260101_110000")]


def test_find_pairs_200_no_pair(fake_data_root: Path):
    # patient 200 只有 std, 没有 dspy
    assert find_pairs("200") == []


def test_find_pairs_unknown_patient_returns_empty(fake_data_root: Path):
    assert find_pairs("999") == []


def test_load_summary_artifact(fake_data_root: Path):
    samples = list(iter_all_samples())
    by_ts = {s.timestamp: s for s in samples}

    # 20260101_100000: std 模式, 02_analyzed/analysis_results.json 不存在
    assert load_summary_artifact(by_ts["20260101_100000"]) is None

    # 20260201_090000: 同上
    assert load_summary_artifact(by_ts["20260201_090000"]) is None


def test_load_summary_artifact_with_json(fake_data_root: Path, tmp_path: Path):
    # 构造 02_analyzed/analysis_results.json
    data = fake_data_root
    sample_dir = data / "100" / "20260101_100000"
    ana = sample_dir / "02_analyzed"
    ana.mkdir(exist_ok=True)
    payload = {"metrics": {"WBC": 5.4}, "n_reports": 1}
    (ana / "analysis_results.json").write_text(json.dumps(payload), encoding="utf-8")

    samples = list(iter_all_samples())
    s = next(s for s in samples if s.timestamp == "20260101_100000")
    loaded = load_summary_artifact(s)
    assert loaded == payload


def test_load_summary_artifact_invalid_json(fake_data_root: Path, tmp_path: Path):
    data = fake_data_root
    ana = data / "100" / "20260101_100000" / "02_analyzed"
    ana.mkdir(exist_ok=True)
    (ana / "analysis_results.json").write_text("{not valid json", encoding="utf-8")

    samples = list(iter_all_samples())
    s = next(s for s in samples if s.timestamp == "20260101_100000")
    assert load_summary_artifact(s) is None


def test_stats(fake_data_root: Path):
    s = stats()
    assert s["n_patients"] == 2
    assert s["n_total_samples"] == 3
    assert s["n_dspy_samples"] == 1
    assert s["n_std_samples"] == 2
    assert s["per_patient"]["100"] == {"total": 2, "dspy": 1, "std": 1}
    assert s["per_patient"]["200"] == {"total": 1, "dspy": 0, "std": 1}


def test_stats_empty(monkeypatch, tmp_path: Path):
    from lab_analysis.dspy_modules import multi_patient

    monkeypatch.setattr(multi_patient, "get_data_root", lambda: tmp_path / "nonexistent")
    s = stats()
    assert s["n_patients"] == 0
    assert s["n_total_samples"] == 0
    assert s["n_dspy_samples"] == 0
    assert s["n_std_samples"] == 0
    assert s["per_patient"] == {}


def test_find_pairs_two_dspys_no_pair_for_first(monkeypatch, tmp_path: Path):
    """连续两个 dspy run, 第一个 dspy 找不到前面的 std -> 不配对"""
    data = tmp_path / "data" / "300"
    for ts in ["20260101_100000", "20260101_110000"]:
        rep = data / ts / "04_reports"
        rep.mkdir(parents=True)
        (rep / "dspy_prompts").mkdir()

    from lab_analysis.dspy_modules import multi_patient

    monkeypatch.setattr(multi_patient, "get_data_root", lambda: tmp_path / "data")
    pairs = find_pairs("300")
    # 第一个 dspy 前面无 std -> 跳过
    # 第二个 dspy 前面最近的 std 仍是 110000 之前的 dspy 110000, 不算 std -> 也跳过
    assert pairs == []
