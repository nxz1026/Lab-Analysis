"""tests.test_dashboard — Streamlit dashboard helper 单元测试。

dashboard.py 顶层大量 streamlit 调用, 无法直接 import。
策略:
- 用 mock 让 streamlit 全 API 返回 dummy, 这样 import 不挂
- 测试纯函数: _list_patients / _list_runs / _load_json / _load_md / _load_csv_df
"""

from __future__ import annotations

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# 1) mock streamlit 模块, 让 dashboard 可被 import
# ---------------------------------------------------------------------------
def _make_stub_streamlit() -> ModuleType:
    """构造一个最小可用的 streamlit stub, 让 dashboard import 不报错。"""
    st = ModuleType("streamlit")

    # 全部 API 用 MagicMock 替身
    st.set_page_config = MagicMock()
    st.sidebar = MagicMock()
    st.warning = MagicMock()
    st.stop = MagicMock()
    st.selectbox = MagicMock(return_value="dummy")
    st.markdown = MagicMock()
    st.caption = MagicMock()
    st.button = MagicMock()
    st.rerun = MagicMock()
    st.tabs = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock(), MagicMock()])

    # st.columns(n) / st.columns([...]) 都返回 n 个容器
    def _columns(arg):
        n = arg if isinstance(arg, int) else len(arg)
        return [MagicMock() for _ in range(n)]

    st.columns = MagicMock(side_effect=_columns)
    st.header = MagicMock()
    st.subheader = MagicMock()
    st.metric = MagicMock()
    st.dataframe = MagicMock()
    st.pyplot = MagicMock()
    st.image = MagicMock()
    st.error = MagicMock()
    st.info = MagicMock()
    st.write = MagicMock()
    st.cache_data = lambda f: f  # 装饰器直接返回原函数
    return st


@pytest.fixture(scope="module")
def dashboard():
    """提供已经 mock 过 streamlit 的 dashboard module。"""
    # 在 sys.modules 里注册 stub
    stub = _make_stub_streamlit()
    sys.modules["streamlit"] = stub
    # 删除之前可能 cache 的 dashboard module
    sys.modules.pop("lab_analysis.dashboard", None)

    # 现在 import dashboard — 顶层 st.xxx 全部走到 stub
    import lab_analysis.dashboard as dash

    return dash


# ---------------------------------------------------------------------------
# 2) _list_patients / _list_runs 纯函数测试
# ---------------------------------------------------------------------------
class TestListPatients:
    def test_returns_empty_when_data_dir_missing(self, dashboard, tmp_path, monkeypatch):
        monkeypatch.setattr(dashboard, "_DATA_DIR", tmp_path / "nope")
        assert dashboard._list_patients() == []

    def test_returns_sorted_dirs_excluding_hidden(self, dashboard, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "patient_a").mkdir()
        (data_dir / "patient_b").mkdir()
        (data_dir / ".hidden").mkdir()  # 以 . 开头, 应跳过
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        result = dashboard._list_patients()
        assert result == ["patient_a", "patient_b"]

    def test_excludes_files(self, dashboard, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "patient_a").mkdir()
        (data_dir / "stray_file.txt").write_text("x")
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        result = dashboard._list_patients()
        assert result == ["patient_a"]


class TestListRuns:
    def test_returns_empty_when_patient_dir_missing(self, dashboard, tmp_path, monkeypatch):
        monkeypatch.setattr(dashboard, "_DATA_DIR", tmp_path / "nope")
        assert dashboard._list_runs("any_patient") == []

    def test_returns_sorted_dirs_with_numeric_prefix(self, dashboard, tmp_path, monkeypatch):
        r"""P1-3: _list_runs 改用 _TS_RE = re.compile(r"^\d{8}_\d{6}$"), 严格匹配
        标准 pipeline 时间戳格式 (YYYYMMDD_HHMMSS). 不再像原 [:8].isdigit() 那样
        误接受 99999999_anything 这类伪时间戳.
        """
        data_dir = tmp_path / "data"
        patient = data_dir / "p1"
        patient.mkdir(parents=True)
        (patient / "20260620_175252").mkdir()
        (patient / "20260622_220333").mkdir()
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        result = dashboard._list_runs("p1")
        assert result == ["20260620_175252", "20260622_220333"]

    def test_excludes_pseudo_timestamp_dirs(self, dashboard, tmp_path, monkeypatch):
        """P1-3 补充: 伪时间戳 (如 99999999_anything, 前 8 位是数字但 _ 后非 6 位数字)
        被 _TS_RE 严格过滤掉. 这是把 [:8].isdigit() 升级为正则匹配的副作用.
        """
        data_dir = tmp_path / "data"
        patient = data_dir / "p1"
        patient.mkdir(parents=True)
        (patient / "20260620_175252").mkdir()
        (patient / "99999999_anything").mkdir()  # 伪时间戳, _ 后不是 6 位数字
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        result = dashboard._list_runs("p1")
        assert result == ["20260620_175252"]
        assert "99999999_anything" not in result

    def test_excludes_non_numeric_prefix_dirs(self, dashboard, tmp_path, monkeypatch):
        """前 8 位非数字的目录被排除。"""
        data_dir = tmp_path / "data"
        patient = data_dir / "p1"
        patient.mkdir(parents=True)
        (patient / "20260620_175252").mkdir()
        (patient / "old_snapshots").mkdir()  # 前 8 位不是数字
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        result = dashboard._list_runs("p1")
        assert result == ["20260620_175252"]

    def test_excludes_files(self, dashboard, tmp_path, monkeypatch):
        data_dir = tmp_path / "data"
        patient = data_dir / "p1"
        patient.mkdir(parents=True)
        (patient / "20260620_175252").mkdir()
        (patient / "stray.txt").write_text("x")
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        result = dashboard._list_runs("p1")
        assert result == ["20260620_175252"]


# ---------------------------------------------------------------------------
# 3) _load_json / _load_md / _load_csv_df 数据加载
# ---------------------------------------------------------------------------
class TestLoadJson:
    def test_loads_valid_json(self, dashboard, tmp_path):
        p = tmp_path / "data.json"
        p.write_text(json.dumps({"a": 1, "b": [1, 2]}), encoding="utf-8")
        result = dashboard._load_json(p)
        assert result == {"a": 1, "b": [1, 2]}

    def test_returns_empty_when_missing(self, dashboard, tmp_path):
        assert dashboard._load_json(tmp_path / "nope.json") == {}

    def test_returns_empty_on_corrupt_json(self, dashboard, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json {", encoding="utf-8")
        # P2-1: _load_json 改为 catch JSONDecodeError/OSError 并返回 {},
        # 防止 dashboard 视图因单个坏文件整体崩溃
        result = dashboard._load_json(p)
        assert result == {}


class TestLoadMd:
    def test_loads_text(self, dashboard, tmp_path):
        p = tmp_path / "report.md"
        p.write_text("# Title\n\n正文", encoding="utf-8")
        assert dashboard._load_md(p) == "# Title\n\n正文"

    def test_returns_empty_when_missing(self, dashboard, tmp_path):
        assert dashboard._load_md(tmp_path / "nope.md") == ""


class TestLoadCsvDf:
    def test_loads_csv(self, dashboard, tmp_path):
        pytest.importorskip("pandas")
        p = tmp_path / "metrics.csv"
        p.write_text("date,value\n2026-01-01,1.5\n2026-01-02,2.5\n", encoding="utf-8")
        df = dashboard._load_csv_df(p)
        assert df is not None
        assert len(df) == 2
        assert list(df.columns) == ["date", "value"]

    def test_returns_none_when_missing(self, dashboard, tmp_path):
        assert dashboard._load_csv_df(tmp_path / "nope.csv") is None


# ---------------------------------------------------------------------------
# 4) 集成: 选择 patient + run 后能正确解析目录结构
# ---------------------------------------------------------------------------
class TestIntegrationSelections:
    """模拟 dashboard 实际使用: 选 patient → 选 run → 列 figures。"""

    def test_selects_first_run_by_default(self, dashboard, tmp_path, monkeypatch):
        """dashboard.py 顶层用 st.sidebar.selectbox(..., index=0) 拿第一个 run。"""
        data_dir = tmp_path / "data"
        patient_dir = data_dir / "p1"
        run_dir = patient_dir / "20260622_220333"
        (run_dir / "02_analyzed" / "figures").mkdir(parents=True)
        (run_dir / "04_reports").mkdir()
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        # _list_runs 返回 sorted, 第一个就是 20260622
        runs = dashboard._list_runs("p1")
        assert runs[0] == "20260622_220333"
        # 验证 figures 目录在 standard path
        figures = run_dir / "02_analyzed" / "figures"
        assert figures.is_dir()

    def test_data_loaders_resolve_correct_paths(self, dashboard, tmp_path):
        """当 patient/run 选定时, 各个 load 函数应能读对应路径。"""
        run_dir = tmp_path / "run"
        analyzed_dir = run_dir / "02_analyzed"
        analyzed_dir.mkdir(parents=True)
        reports_dir = run_dir / "04_reports"
        reports_dir.mkdir()
        # 写入 4 个标准产物
        (analyzed_dir / "analysis_results.json").write_text(
            json.dumps({"n_reports": 5}), encoding="utf-8"
        )
        (analyzed_dir / "alerts.json").write_text(
            json.dumps([{"level": "WARNING", "message": "x"}]), encoding="utf-8"
        )
        (analyzed_dir / "lab_metrics.csv").write_text("d,v\n1,2\n", encoding="utf-8")
        (reports_dir / "final_integrated_report.md").write_text("# Final", encoding="utf-8")

        assert dashboard._load_json(analyzed_dir / "analysis_results.json") == {"n_reports": 5}
        assert len(dashboard._load_json(analyzed_dir / "alerts.json")) == 1
        assert dashboard._load_md(reports_dir / "final_integrated_report.md") == "# Final"


# ---------------------------------------------------------------------------
# 5) 异常路径: corrupt analysis_results 不阻断 list 操作
# ---------------------------------------------------------------------------
class TestResilience:
    def test_missing_run_subdir_returns_empty(self, dashboard, tmp_path):
        """run_dir 不存在 / 空 时 _load_xxx 安全降级 (返回 None / {} / '')"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert dashboard._load_json(empty_dir / "analysis_results.json") == {}
        assert dashboard._load_md(empty_dir / "final_integrated_report.md") == ""
        assert dashboard._load_csv_df(empty_dir / "lab_metrics.csv") is None

    def test_no_patients_triggers_warning(self, dashboard, tmp_path, monkeypatch):
        """无 patient 时 _list_patients() 返回 [], 触发 dashboard 顶层 st.warning + st.stop"""
        data_dir = tmp_path / "empty_data"
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        assert dashboard._list_patients() == []

    def test_patient_with_no_runs(self, dashboard, tmp_path, monkeypatch):
        """patient 目录存在但无 run → 空 runs, 应触发 st.warning"""
        data_dir = tmp_path / "data"
        (data_dir / "lonely_patient").mkdir(parents=True)
        monkeypatch.setattr(dashboard, "_DATA_DIR", data_dir)
        assert dashboard._list_runs("lonely_patient") == []