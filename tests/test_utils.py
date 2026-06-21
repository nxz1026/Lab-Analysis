"""tests.test_utils — 通用工具函数测试"""


from lab_analysis.llm_client import parse_json_response, strip_code_fence
from lab_analysis.utils import (
    parse_metadata_table,
)


class TestParseMetadataTable:
    """解析 Markdown 表格格式的 metadata"""

    def test_basic(self):
        text = "| 字段 | 值 |\n|------|-----|\n| 身份证号 | 110101199003078888 |\n| 报告日期 | 2026-03-24 |"
        result = parse_metadata_table(text)
        assert result["身份证号"] == "110101199003078888"
        assert result["报告日期"] == "2026-03-24"

    def test_skip_header(self):
        result = parse_metadata_table("| 字段 | 值 |\n| --- | --- |\n| 姓名 | 张三 |")
        assert result["姓名"] == "张三"

    def test_empty(self):
        assert parse_metadata_table("") == {}


class TestStripCodeFence:
    """剥离 LLM 回复中的 ```json 代码块标记"""

    def test_json_fence(self):
        assert strip_code_fence("```json\n{\"a\": 1}\n```") == "{\"a\": 1}"

    def test_plain_fence(self):
        assert strip_code_fence("```\nhello\n```") == "hello"

    def test_no_fence(self):
        assert strip_code_fence("plain text") == "plain text"


class TestParseJsonResponse:
    """从 LLM 回复解析 JSON"""

    def test_clean_json(self):
        assert parse_json_response("{\"a\": 1}") == {"a": 1}

    def test_with_fence(self):
        assert parse_json_response("```json\n{\"a\": 1}\n```") == {"a": 1}
