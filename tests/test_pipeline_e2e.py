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
        from lab_analysis.utils import WORK_ROOT, build_paths

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


# ----------------------------------------------------------------------------
# SCNet OCR 端到端: 用 monkeypatch 注入 fake OCR 文本，
# 这样 e2e 可以在 CI 里跑，不依赖真实 SCNet 服务。
# ----------------------------------------------------------------------------


_FAKE_OCR_TEXT = """\
川渝HR
四川省人民医院温江医院
成都市温江区人民医院
血细胞分析+超敏C反应蛋白测定(门)
检验报告单
Report of Clinical Laboratory
姓名(Name): 聂聃
性别(Sex): 男
年龄 (Age): 38岁
样本编号(No.): 22
科别(Dept.):消化内科
诊疗卡号(CaseNo.)513229198801040014
诊断(Diag.):慢性胰腺炎
标本(Sample): 全血
送检医生 (Doc.): 李薇
序号
项目名称(Test)
结果(Result)
单位(Unit)
参考范围(Ref.)
1 *
白细胞计数(WBC)
6.70
10^9/L
3.5-9.5
2 *
红细胞计数(RBC)
4.52
10^12/L
4.30-5.80
3 *
血红蛋白测定(HGB)
138
g/L
130-175
4 *
血小板计数(PLT)
275
10^9/L
125-350
5 *
C反应蛋白测定(CRP)
8.2
mg/L
<10
报告时间: 2026-03-24 08:15
打印时间: 2026-05-01 08:14
第1页 共1页
"""


class TestSCNetOCRE2E:
    """端到端走 call_scnet_ocr + _parse_ocr_to_json，
    但用 monkeypatch 替换网络调用，使 CI 可跑。
    """

    def test_call_scnet_ocr_is_monkeypatchable(self, tmp_path, monkeypatch):
        """call_scnet_ocr 能被 monkeypatch 替换，避免走真实 API。"""
        from lab_analysis import extract_lab_data as mod

        fake_called = []

        def fake_scnet(image_path, api_key):
            fake_called.append((str(image_path), len(api_key)))
            return _FAKE_OCR_TEXT

        monkeypatch.setattr(mod, "call_scnet_ocr", fake_scnet)
        # 现在调它会走 fake
        out = mod.call_scnet_ocr(tmp_path / "x.jpg", "dummy-key")
        assert out == _FAKE_OCR_TEXT
        assert fake_called == [(str(tmp_path / "x.jpg"), 9)]

    def test_extract_lab_metrics_e2e_with_fake_ocr(self, tmp_path, monkeypatch):
        """extract_lab_metrics 全流程跑通，metrics 字典非空且关键指标正确。"""
        from lab_analysis import extract_lab_data as mod

        monkeypatch.setattr(mod, "call_scnet_ocr", lambda *a, **kw: _FAKE_OCR_TEXT)

        fake_img = tmp_path / "lab_fake.jpg"
        fake_img.write_bytes(b"\x00")  # 不读，只走函数路径

        result = mod.extract_lab_metrics(fake_img)

        assert isinstance(result, dict)
        # 元数据
        assert result.get("report_date") == "2026-03-24"
        assert "消化内科" in (result.get("department") or "")
        assert "慢性胰腺炎" in (result.get("diagnosis") or "")
        # 关键指标
        metrics = result.get("metrics", {})
        assert metrics.get("WBC") == 6.7
        assert metrics.get("RBC") == 4.52
        assert metrics.get("HGB") == 138.0
        assert metrics.get("PLT") == 275.0
        assert "CRP" in metrics
        # 至少有 5 个指标被解析
        assert len(metrics) >= 5

    def test_extract_lab_metrics_resize_does_not_break_monkeypatch(self, tmp_path, monkeypatch):
        """当 fake OCR 被注入，call_scnet_ocr 不应走真实图片预处理路径。"""
        from lab_analysis import extract_lab_data as mod

        monkeypatch.setattr(mod, "call_scnet_ocr", lambda *a, **kw: _FAKE_OCR_TEXT)

        # PIL.Image 不会真的被打开，因为 fake 完全绕过真实读取
        fake_img = tmp_path / "anything.bin"
        fake_img.write_bytes(b"not an image")

        result = mod.extract_lab_metrics(fake_img)
        assert "metrics" in result
        assert isinstance(result["metrics"], dict)

    def test_resize_threshold_units(self):
        """MAX_OCR_SIDE 常量暴露，且是合理上限（<= 2048）。"""
        from lab_analysis import extract_lab_data as mod

        # 阈值不应超过 2048（原始 2082px 图片就触发了 435）
        assert 800 <= getattr(mod, "MAX_OCR_SIDE", 0) <= 2048
