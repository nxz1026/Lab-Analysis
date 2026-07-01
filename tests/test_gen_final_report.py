"""tests.test_gen_final_report — 最终报告生成模块单测 (smoke)。"""

from __future__ import annotations

from pathlib import Path

from lab_analysis.gen_final_report import (
    assess_three_source_consistency,
    build_prompt,
    load_api_key,
)


def test_assess_three_source_consistency(tmp_path):
    # 空目录: 预期直接返回一个字符串结果（不会抛异常）
    result = assess_three_source_consistency(tmp_path)
    assert isinstance(result, str)


def test_load_api_key_default():
    key = load_api_key("NONEXISTENT_VAR_FOR_TEST", required=False)
    assert key is None


class TestBuildPrompt:
    def test_returns_string(self, tmp_path):
        result = build_prompt(tmp_path, "p001")
        assert isinstance(result, str)

    def test_returns_chinese_text(self, tmp_path):
        result = build_prompt(tmp_path, "p001")
        assert isinstance(result, str)
        assert len(result) > 100
