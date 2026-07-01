"""tests.test_analysis_base — 分析子包基类单测。"""

from __future__ import annotations

from pathlib import Path

import pytest

from lab_analysis.analysis._base import (
    INFLAMMATION_COLORS,
    NUMERIC_METRICS,
    REF_RANGES,
    build_paths,
    save_fig,
    setup_chinese,
)


class TestConstants:
    def test_numeric_metrics_is_list(self):
        assert isinstance(NUMERIC_METRICS, list)
        assert len(NUMERIC_METRICS) > 0

    def test_ref_ranges_has_all_metrics(self):
        for m in ["WBC", "RBC", "PLT", "CRP", "hs-CRP"]:
            assert m in REF_RANGES

    def test_ref_ranges_are_tuples(self):
        for k, v in REF_RANGES.items():
            assert isinstance(v, tuple)
            assert len(v) == 2

    def test_inflammation_colors(self):
        assert "急性期" in INFLAMMATION_COLORS
        assert "缓解期" in INFLAMMATION_COLORS


class TestBuildPaths:
    def test_returns_dict(self):
        paths = build_paths("patient123")
        assert isinstance(paths, dict)

    def test_contains_expected_keys(self):
        paths = build_paths("p001")
        for key in ["data_dir", "analyzed_dir", "figures_dir", "reports_dir", "metrics_csv"]:
            assert key in paths

    def test_values_are_paths(self):
        paths = build_paths("p001")
        for v in paths.values():
            assert isinstance(v, Path)

    def test_analyzed_dir_suffix(self):
        paths = build_paths("p001")
        assert paths["analyzed_dir"].name == "02_analyzed"

    def test_figures_dir_suffix(self):
        paths = build_paths("p001")
        assert paths["figures_dir"].name == "figures"


class TestSetupChinese:
    def test_is_idempotent(self):
        setup_chinese()
        setup_chinese()
        setup_chinese()


class TestSaveFig:
    def test_saves_to_path(self, tmp_path):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])
        out = tmp_path / "figs" / "test.png"
        save_fig(fig, out)
        assert out.exists()
        assert out.stat().st_size > 0
