"""tests.test_data_loader_e2e — 端到端覆盖 lab_analysis.data_loader

data_loader 是 0% 覆盖率核心模块,负责:
- 解析 markdown lab report (键值对格式 + YAML 格式)
- 写出宽表 CSV + JSON 落盘

关键纯函数:
    parse_metrics_simple(text) -> dict[str, float|str]
    parse_metrics_yaml(text)   -> dict[str, float|str]
    extract_value(result_str)  -> float | None
    to_csv(reports, output_path)
    to_json(reports, output_path)
"""

import csv
import json
import textwrap

import pytest

from lab_analysis.data_loader import (
    extract_value,
    parse_metrics_simple,
    parse_metrics_yaml,
    to_csv,
    to_json,
)

# ============== extract_value 单元覆盖 ==============


class TestExtractValue:
    @pytest.mark.parametrize(
        ("cell", "expected"),
        [
            ("3.5", 3.5),
            ("10.0", 10.0),
            ("0.45", 0.45),
            ("42", 42),
            ("3.5g/L", 3.5),
        ],
    )
    def test_numeric_extraction(self, cell, expected):
        assert extract_value(cell) == pytest.approx(expected)

    @pytest.mark.parametrize("cell", ["", "--", "N/A", "—"])
    def test_missing_markers_return_none(self, cell):
        assert extract_value(cell) is None


# ============== parse_metrics_simple (键值对格式) ==============


SIMPLE_KV = textwrap.dedent(
    """\
    # 患者检验报告
    WBC: 6.5
    RBC: 4.5
    hs-CRP: 3.2
    NEUT%: 65.0
    备注: 正常
    """
)


class TestParseMetricsSimple:
    def test_basic_extraction(self):
        result = parse_metrics_simple(SIMPLE_KV)
        assert result["WBC"] == pytest.approx(6.5)
        assert result["RBC"] == pytest.approx(4.5)
        assert result["hs-CRP"] == pytest.approx(3.2)
        assert result["NEUT%"] == pytest.approx(65.0)

    def test_non_numeric_kept_as_string(self):
        result = parse_metrics_simple(SIMPLE_KV)
        assert result["备注"] == "正常"

    def test_skips_comments_and_empty(self):
        text = "# comment\n\n\nWBC: 7.0\n"
        result = parse_metrics_simple(text)
        assert result == {"WBC": pytest.approx(7.0)}

    def test_empty_returns_empty(self):
        assert parse_metrics_simple("") == {}
        assert parse_metrics_simple("# only title\nno kv") == {}


# ============== parse_metrics_yaml (YAML 格式) ==============


YAML_INPUT = textwrap.dedent(
    """\
    report:
      patient: test001
      date: 2026-06-20
    metrics:
      WBC: 6.5
      hs-CRP: 3.2
      NEUT%: 65.0
      备注: 正常
    """
)


class TestParseMetricsYaml:
    def test_basic_extraction(self):
        """parse_metrics_yaml 只支持 \\w+ key(WBC / RBC 等纯字母数字)"""
        result = parse_metrics_yaml(YAML_INPUT)
        assert result["WBC"] == pytest.approx(6.5)
        assert result == {"WBC": pytest.approx(6.5), "备注": "正常"}

    def test_non_numeric_kept_as_string(self):
        result = parse_metrics_yaml(YAML_INPUT)
        assert result["备注"] == "正常"

    def test_hyphen_key_skipped(self):
        """hs-CRP 这种带连字符的 key 不被识别(parse_metrics_yaml 限制),应跳过"""
        result = parse_metrics_yaml(YAML_INPUT)
        assert "hs-CRP" not in result

    def test_percent_key_skipped(self):
        """NEUT% 带百分号也不被识别"""
        result = parse_metrics_yaml(YAML_INPUT)
        assert "NEUT%" not in result

    def test_no_metrics_block_returns_empty(self):
        text = textwrap.dedent(
            """\
            report:
              patient: test001
            """
        )
        assert parse_metrics_yaml(text) == {}

    def test_partial_metrics(self):
        text = textwrap.dedent(
            """\
            metrics:
              WBC: 4.0
            """
        )
        assert parse_metrics_yaml(text) == {"WBC": pytest.approx(4.0)}


# ============== to_csv / to_json (写文件 e2e) ==============


@pytest.fixture
def sample_reports():
    return [
        {
            "report_id": "R001",
            "report_date": "2026-06-20",
            "diagnosis": "慢性胰腺炎",
            "department": "消化内科",
            "physician": "张三",
            "visit_type": "门诊",
            "is_inpatient": False,
            "WBC": 6.5,
            "WBC_status": "正常",
            "hs-CRP": 3.2,
            "hs-CRP_status": "↑",
            "RBC": 4.5,
            "RBC_status": "正常",
        },
        {
            "report_id": "R002",
            "report_date": "2026-06-15",
            "diagnosis": "随访",
            "department": "消化内科",
            "physician": "李四",
            "visit_type": "门诊",
            "is_inpatient": False,
            "WBC": 7.0,
            "WBC_status": "正常",
            "hs-CRP": 2.5,
            "hs-CRP_status": "正常",
            "RBC": 4.6,
            "RBC_status": "正常",
        },
    ]


class TestToCsv:
    def test_basic(self, tmp_path, sample_reports):
        out = tmp_path / "out.csv"
        to_csv(sample_reports, out)
        assert out.exists()
        # 读 csv 验证
        with open(out, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["report_id"] == "R001"
        assert float(rows[0]["WBC"]) == 6.5
        assert rows[0]["hs-CRP_status"] == "↑"

    def test_empty_reports_no_write(self, tmp_path):
        out = tmp_path / "out.csv"
        to_csv([], out)
        assert not out.exists()


class TestToJson:
    def test_basic(self, tmp_path, sample_reports):
        out = tmp_path / "out.json"
        to_json(sample_reports, out)
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["report_count"] == 2
        assert (
            "2026-06-15" in data["date_range"]["start"]
            or data["date_range"]["start"] == "2026-06-15"
        )
        assert (
            "2026-06-20" in data["date_range"]["end"] or data["date_range"]["end"] == "2026-06-20"
        )

    def test_date_sorting(self, tmp_path, sample_reports):
        """to_json 应按 report_date 升序排序"""
        out = tmp_path / "out.json"
        to_json(sample_reports, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        dates = [r["report_date"] for r in data["reports"]]
        assert dates == sorted(dates)
