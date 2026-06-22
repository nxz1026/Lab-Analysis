"""MCP server for Lab-Analysis — 暴露 2 个 tool 给 LLM agent 调用。

启动:
    # stdio 模式 (默认, 用于 Claude Desktop / Cursor / IDE)
    python mcp_server.py

Tool 列表:
    1. audit_dspy_models()        — 检查 4 个 DSPy compiled JSON 是否 STALE
    2. run_quant_eval(...)        — 跑 6 指标量化评估 (std vs dspy)

依赖:
    pip install mcp  (>= 1.0)

客户端配置 (Claude Desktop):
    {
      "mcpServers": {
        "lab-analysis": {
          "command": "python",
          "args": ["e:/2026Workplace/Code/Lab-Analysis/mcp_server.py"]
        }
      }
    }
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 让 import 走项目根
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

# 业务模块 (项目内)
from scripts import audit_dspy_models as audit_mod  # noqa: E402
from lab_analysis.quant_metrics import (  # noqa: E402
    metric_confidence,
    metric_entity_f1,
    metric_entity_recall_breakdown,
    metric_failure_rate,
    metric_feedback_delta,
    metric_section_coverage,
)

mcp = FastMCP("lab-analysis")


# ============== Tool 1: audit_dspy_models ==============


@mcp.tool()
def audit_dspy_models() -> str:
    """检查 4 个 DSPy compiled JSON 是否 STALE (与源代码不同步)。

    返回 JSON 字符串:
        {
          "overall_up_to_date": bool,
          "stale_modules": [str, ...],
          "details": [
            {"module": str, "compiled_at": str, "source_commit": str,
             "is_up_to_date": bool, "reason": str}
          ]
        }
    """
    try:
        results = audit_mod.main()  # 不传 argv
        return json.dumps(results, ensure_ascii=False, indent=2)
    except SystemExit as e:
        # --ci 模式下 audit 失败会 sys.exit(1), 这里捕获
        return json.dumps(
            {
                "overall_up_to_date": False,
                "stale_modules": ["(see CLI exit)"],
                "details": [],
                "error": f"audit exit code = {e.code}",
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"overall_up_to_date": False, "error": str(e)},
            ensure_ascii=False,
            indent=2,
        )


# ============== Tool 2: run_quant_eval ==============


@mcp.tool()
def run_quant_eval(
    id_card: str,
    std_ts: str,
    dspy_ts: str,
) -> str:
    """对 std + dspy 两次跑做 6 指标量化评估。

    Args:
        id_card: 脱敏患者 ID, 形如 "846552421134373347"
        std_ts:  std 模式时间戳, 形如 "20260620_175252"
        dspy_ts: dspy 模式时间戳, 形如 "20260620_175730"

    Returns:
        JSON 字符串, 含 6 个 metric + std/dspy 文本长度等元信息。
    """
    try:
        from lab_analysis.utils import WORK_ROOT  # noqa: PLC0415

        base = WORK_ROOT / "data" / id_card
        std_md = base / std_ts / "04_reports" / "final_integrated_report.md"
        dspy_json = base / dspy_ts / "04_reports" / "final_integrated_report.json"
        std_scoring_p = base / std_ts / "04_reports" / "scoring_card.json"
        feedback_p = base / "feedback.json"

        # 加载数据
        std_text = std_md.read_text(encoding="utf-8") if std_md.exists() else ""
        dspy_text = dspy_json.read_text(encoding="utf-8") if dspy_json.exists() else ""
        if dspy_json.exists():
            dspy_data = json.loads(dspy_text)
        else:
            dspy_data = {}
        std_scoring = (
            json.loads(std_scoring_p.read_text(encoding="utf-8"))
            if std_scoring_p.exists()
            else {}
        )
        feedback = (
            json.loads(feedback_p.read_text(encoding="utf-8"))
            if feedback_p.exists()
            else {}
        )
        dspy_sections = dspy_data.get("sections", {}) if dspy_data else {}

        # 调 6 个 metric
        return json.dumps(
            {
                "id_card": id_card,
                "std_ts": std_ts,
                "dspy_ts": dspy_ts,
                "text_lengths": {
                    "std": len(std_text),
                    "dspy": len(dspy_text),
                },
                "metrics": {
                    "entity_f1": metric_entity_f1(std_text, dspy_text),
                    "section_coverage": metric_section_coverage(dspy_sections),
                    "failure_rate": metric_failure_rate(dspy_data, dspy_sections),
                    "entity_recall": metric_entity_recall_breakdown(std_text, dspy_text),
                    "confidence": metric_confidence(dspy_data, std_scoring),
                    "feedback_delta": metric_feedback_delta(feedback),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"error": str(e), "type": type(e).__name__},
            ensure_ascii=False,
            indent=2,
        )


# ============== Entry ==============


if __name__ == "__main__":
    mcp.run()  # stdio transport 默认
