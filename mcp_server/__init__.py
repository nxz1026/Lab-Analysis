"""mcp_server — MCP server for Lab-Analysis, 暴露 6 个 tool 给 LLM agent。

子模块拆分:
    audit       — audit_dspy_models
    quant_eval  — run_quant_eval
    patient     — list_patients + get_pipeline_status
    recompile   — trigger_dspy_recompile
    trend       — render_quant_trend

调用:
    from mcp_server import get_pipeline_status, run_quant_eval  # 兼容老 API
    from mcp_server import mcp  # FastMCP 实例,用于 mcp.run()

启动 (stdio):
    python mcp_server.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让 import 走项目根
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("lab-analysis")

# 注册 6 个 tool (副作用 import + @mcp.tool())
from . import audit, patient, quant_eval, recompile, trend  # noqa: E402, F401, I001

# 兼容旧 API: mcp_server.get_pipeline_status(...) / mcp_server.run_quant_eval(...)
# 重新导出 tool 函数,让 tests/test_mcp_server.py 的旧调用方式继续工作
from .audit import audit_dspy_models  # noqa: E402, F401
from .patient import get_pipeline_status, list_patients  # noqa: E402, F401
from .quant_eval import run_quant_eval  # noqa: E402, F401
from .recompile import trigger_dspy_recompile  # noqa: E402, F401
from .trend import render_quant_trend  # noqa: E402, F401

__all__ = [
    "mcp",
    "audit_dspy_models",
    "run_quant_eval",
    "list_patients",
    "get_pipeline_status",
    "trigger_dspy_recompile",
    "render_quant_trend",
]
