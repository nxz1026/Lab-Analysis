"""tests.test_dspy_cache_metrics — 验证 DSPy 编译缓存埋点。

被 metrics 文件 (`logs/dspy_cache_metrics.json`) 的存在与否决定 pass/fail:
- 跑测试 → 实际命中 record_hit / record_miss
- 测完读取 → 计数必须正确
- reset 必须清零

CI 中:
    python scripts/dspy_cache_stats.py --json
    # 断言 totals.load_fail == 0 (即没有破坏性 load)
"""

from __future__ import annotations

import importlib
import json
import sys

import pytest

# 重新导入避免跨测试的 _cache 状态污染
_cache_metrics_mod = importlib.import_module("lab_analysis.dspy_modules._cache_metrics")


@pytest.fixture
def isolated_metrics(tmp_path, monkeypatch):
    """每次测试都把 metrics 文件重定向到 tmp_path, 避免污染仓库 logs/。"""
    metrics_file = tmp_path / "dspy_cache_metrics.json"
    monkeypatch.setattr(_cache_metrics_mod, "_METRICS_FILE", metrics_file)
    # 强制重新加载 — 之前的 _cache 可能保留旧指针
    monkeypatch.setattr(_cache_metrics_mod, "_cache", None)
    yield metrics_file
    # 清理 in-memory cache, 避免后续测试串味
    monkeypatch.setattr(_cache_metrics_mod, "_cache", None)


class TestRecordHitMiss:
    def test_record_hit_increments_total(self, isolated_metrics):
        _cache_metrics_mod.record_hit("lab_data_extractor")
        stats = _cache_metrics_mod.get_stats()
        assert stats["totals"]["hit"] == 1
        assert stats["modules"]["lab_data_extractor"]["hit"] == 1

    def test_record_miss_increments_total(self, isolated_metrics):
        _cache_metrics_mod.record_miss("lab_data_extractor")
        stats = _cache_metrics_mod.get_stats()
        assert stats["totals"]["miss"] == 1
        assert stats["modules"]["lab_data_extractor"]["miss"] == 1

    def test_record_load_fail_separate_from_miss(self, isolated_metrics):
        _cache_metrics_mod.record_load_fail("mri_analyzer")
        stats = _cache_metrics_mod.get_stats()
        assert stats["totals"]["load_fail"] == 1
        assert stats["modules"]["mri_analyzer"]["load_fail"] == 1

    def test_multiple_modules_independent(self, isolated_metrics):
        _cache_metrics_mod.record_hit("lab_data_extractor")
        _cache_metrics_mod.record_miss("mri_analyzer")
        stats = _cache_metrics_mod.get_stats()
        assert stats["modules"]["lab_data_extractor"]["hit"] == 1
        assert stats["modules"]["mri_analyzer"]["miss"] == 1
        assert stats["totals"]["hit"] == 1
        assert stats["totals"]["miss"] == 1

    def test_repeated_calls_accumulate(self, isolated_metrics):
        for _ in range(3):
            _cache_metrics_mod.record_hit("final_report_generator")
        for _ in range(2):
            _cache_metrics_mod.record_miss("final_report_generator")
        stats = _cache_metrics_mod.get_stats()
        assert stats["modules"]["final_report_generator"]["hit"] == 3
        assert stats["modules"]["final_report_generator"]["miss"] == 2


class TestPersistence:
    def test_metrics_persisted_to_disk(self, isolated_metrics):
        _cache_metrics_mod.record_hit("lab_data_extractor")
        _cache_metrics_mod.record_miss("mri_analyzer")
        assert isolated_metrics.is_file()
        data = json.loads(isolated_metrics.read_text(encoding="utf-8"))
        assert data["totals"]["hit"] == 1
        assert data["totals"]["miss"] == 1

    def test_metrics_loadable_by_new_process(self, isolated_metrics):
        """模拟跨进程: 卸载 in-memory cache, 重新读盘。"""
        _cache_metrics_mod.record_hit("final_report_generator")
        # 模拟新进程
        _cache_metrics_mod._cache = None
        stats = _cache_metrics_mod.get_stats()
        assert stats["totals"]["hit"] == 1
        assert stats["modules"]["final_report_generator"]["hit"] == 1


class TestReset:
    def test_reset_clears_in_memory_and_disk(self, isolated_metrics):
        _cache_metrics_mod.record_hit("lab_data_extractor")
        assert isolated_metrics.is_file()
        _cache_metrics_mod.reset()
        assert not isolated_metrics.is_file()
        stats = _cache_metrics_mod.get_stats()
        assert stats["totals"] == {"hit": 0, "miss": 0, "load_fail": 0}
        assert stats["modules"] == {}


class TestGetStatsSnapshot:
    def test_get_stats_returns_independent_copy(self, isolated_metrics):
        _cache_metrics_mod.record_hit("lab_data_extractor")
        snap = _cache_metrics_mod.get_stats()
        # 改 snapshot 不影响内部
        snap["totals"]["hit"] = 999
        fresh = _cache_metrics_mod.get_stats()
        assert fresh["totals"]["hit"] == 1

    def test_get_stats_with_no_records(self, isolated_metrics):
        stats = _cache_metrics_mod.get_stats()
        assert stats == {
            "modules": {},
            "totals": {"hit": 0, "miss": 0, "load_fail": 0},
        }


class TestCLI:
    """scripts/dspy_cache_stats.py CLI 烟测, 保证 CI 步骤能正确解析输出。"""

    def test_cli_json_output_is_valid_json(self, isolated_metrics, capsys):
        _cache_metrics_mod.record_hit("lab_data_extractor")
        _cache_metrics_mod.record_miss("mri_analyzer")
        # 直接 import + 跑 main, 不用 subprocess
        from scripts.dspy_cache_stats import main

        sys.argv = ["dspy_cache_stats.py", "--json"]
        rc = main()
        assert rc == 0
        captured = capsys.readouterr().out
        data = json.loads(captured)
        assert data["totals"]["hit"] == 1
        assert data["totals"]["miss"] == 1

    def test_cli_table_output_contains_header(self, isolated_metrics, capsys):
        _cache_metrics_mod.record_hit("final_report_generator")
        from scripts.dspy_cache_stats import main

        sys.argv = ["dspy_cache_stats.py"]
        rc = main()
        assert rc == 0
        out = capsys.readouterr().out
        assert "DSPy compile cache hit-rate" in out
        assert "final_report_generator" in out


# ---------------------------------------------------------------------------
# CI gate 模拟: CI 跑完后, totals.load_fail 必须 == 0 才视为健康
# (record_load_fail 仅在 .json 存在但 load() 抛错时被埋, 是破坏信号)
# ---------------------------------------------------------------------------
class TestCIGate:
    def test_no_load_failures_after_clean_run(self, isolated_metrics):
        """正常 hit/miss 路径不应触发 load_fail, 这就是 CI 检查的依据。"""
        _cache_metrics_mod.record_hit("lab_data_extractor")
        _cache_metrics_mod.record_miss("mri_analyzer")
        stats = _cache_metrics_mod.get_stats()
        assert stats["totals"]["load_fail"] == 0