"""tests/test_pipeline_e2e.py — Pipeline 端到端集成测试

覆盖：
- PipelineContext 创建与路径构建
- deid 一致性（get_deid 全局使用）
- build_paths() 路径解析
- 指标清洗逻辑

注意：WORK_ROOT、LAB_DEID_KEY 等模块级常量在 conftest.py 中设置，
本测试文件不依赖 monkeypatch 修改 WORK_ROOT。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _read_source(rel_path: str) -> str:
    """读取源码文件（指定 utf-8 编码）。"""
    return (Path(__file__).resolve().parent.parent / rel_path).read_text(encoding="utf-8")


class TestPipelineContext:
    """PipelineContext 单元测试。"""

    def test_paths_structure(self):
        """验证 PipelineContext 路径结构正确。"""
        from lab_analysis.pipeline.context import PipelineContext
        from lab_analysis.utils import WORK_ROOT

        ctx = PipelineContext(deid="test123", timestamp="20260620_150000")

        assert ctx.deid == "test123"
        assert ctx.timestamp == "20260620_150000"
        assert ctx.patient_dir == WORK_ROOT / "raw" / "patient_test123"
        assert ctx.data_dir == WORK_ROOT / "data" / "test123" / "20260620_150000"
        assert ctx.analyzed_dir == ctx.data_dir / "02_analyzed"
        assert ctx.literature_dir == ctx.data_dir / "03_literature"
        assert ctx.reports_dir == ctx.data_dir / "04_reports"
        assert ctx.raw_papers == WORK_ROOT / "raw" / "patient_test123" / "papers"
        assert ctx.raw_lab == WORK_ROOT / "raw" / "patient_test123" / "lab"
        assert ctx.raw_imaging == WORK_ROOT / "raw" / "patient_test123" / "imaging"

    def test_env_dict(self):
        """验证 env_dict 格式正确。"""
        from lab_analysis.pipeline.context import PipelineContext

        ctx = PipelineContext(deid="abc", timestamp="20260101_000000")
        env = ctx.env_dict()
        assert env["ANALYSIS_TS"] == "abc/20260101_000000"
        assert "WORK_ROOT" in env

    def test_frozen(self):
        """PipelineContext 应不可变。"""
        from lab_analysis.pipeline.context import PipelineContext

        ctx = PipelineContext(deid="test", timestamp="20260101_000000")
        with pytest.raises(AttributeError):
            ctx.deid = "changed"

    def test_path_relationships(self):
        """验证 derived paths 与 data_dir 的关系。"""
        from lab_analysis.pipeline.context import PipelineContext

        ctx = PipelineContext(deid="x", timestamp="20260101_000000")
        assert ctx.analyzed_dir.parent == ctx.data_dir
        assert ctx.literature_dir.parent == ctx.data_dir
        assert ctx.reports_dir.parent == ctx.data_dir
        assert ctx.figures_dir.parent == ctx.analyzed_dir


class TestBuildPaths:
    """build_paths() 路径解析测试。"""

    def test_with_explicit_timestamp(self, tmp_path, monkeypatch):
        """显式传入 timestamp 时应使用传入值。"""
        monkeypatch.setenv("WORK_ROOT", str(tmp_path))
        from lab_analysis.utils import build_paths, WORK_ROOT

        paths = build_paths("test123", timestamp="20260620_150000")
        assert paths["timestamp"] == "20260620_150000"
        assert paths["data_dir"] == WORK_ROOT / "data" / "test123" / "20260620_150000"

    def test_backward_compat_env_var(self, tmp_path, monkeypatch):
        """未传 timestamp 时应从 ANALYSIS_TS 环境变量读取。"""
        monkeypatch.setenv("WORK_ROOT", str(tmp_path))
        monkeypatch.setenv("ANALYSIS_TS", "test123/20260620_150000")
        from lab_analysis.utils import build_paths

        paths = build_paths("test123")
        assert paths["timestamp"] == "20260620_150000"


class TestDeidConsistency:
    """deid 一致性测试。"""

    def test_no_encode_in_ingest(self):
        """ingest_data.py 不应直接调用 encode(patient_id)。"""
        source = _read_source("lab_analysis/ingest_data.py")
        for i, line in enumerate(source.splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or ("import" in s and "encode" in s):
                continue
            assert "encode(patient_id)" not in s, f"Line {i}: 仍使用 encode(patient_id)"

    def test_no_encode_in_extract(self):
        """extract_lab_data.py 不应直接调用 encode(patient_id)。"""
        source = _read_source("lab_analysis/extract_lab_data.py")
        for i, line in enumerate(source.splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or ("import" in s and "encode" in s):
                continue
            assert "encode(patient_id)" not in s, f"Line {i}: 仍使用 encode(patient_id)"

    def test_no_encode_in_steps(self):
        """pipeline/steps.py 不应直接调用 encode()。"""
        source = _read_source("lab_analysis/pipeline/steps.py")
        for i, line in enumerate(source.splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or ("import" in s and "encode" in s):
                continue
            assert "encode(" not in s or "encode_image" in s, f"Line {i}: 仍使用 encode()"


class TestMetricsSanitization:
    """_sanitize_metrics 清洗逻辑测试。"""

    def test_less_than_prefix(self):
        from lab_analysis.extract_lab_data import _sanitize_metrics
        assert _sanitize_metrics({"CRP": "<10", "WBC": 7.5}) == {"CRP": 10.0, "WBC": 7.5}

    def test_greater_than_prefix(self):
        from lab_analysis.extract_lab_data import _sanitize_metrics
        assert _sanitize_metrics({"hs-CRP": ">3.0", "PLT": 250}) == {"hs-CRP": 3.0, "PLT": 250.0}

    def test_dash_removed(self):
        from lab_analysis.extract_lab_data import _sanitize_metrics
        cleaned = _sanitize_metrics({"EO#": "—", "BASO%": "-", "WBC": 5.0})
        assert "EO#" not in cleaned
        assert "BASO%" not in cleaned
        assert cleaned["WBC"] == 5.0

    def test_empty_string_removed(self):
        from lab_analysis.extract_lab_data import _sanitize_metrics
        cleaned = _sanitize_metrics({"EO#": "", "WBC": 5.0})
        assert "EO#" not in cleaned

    def test_normal_values_preserved(self):
        from lab_analysis.extract_lab_data import _sanitize_metrics
        assert _sanitize_metrics({"WBC": 7.5, "RBC": 4.52}) == {"WBC": 7.5, "RBC": 4.52}

    def test_mixed_formats(self):
        from lab_analysis.extract_lab_data import _sanitize_metrics
        cleaned = _sanitize_metrics({"CRP": "<10", "hs-CRP": ">3.0", "WBC": 7.5, "EO#": "\u2014"})
        assert cleaned == {"CRP": 10.0, "hs-CRP": 3.0, "WBC": 7.5}
