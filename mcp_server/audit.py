"""mcp_server.audit — audit_dspy_models tool"""

from __future__ import annotations

import json

from scripts import audit_dspy_models as audit_mod

from . import mcp


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
        # 走 print-free 的 collect(), 不调 main(): main() 会往 stdout 打 ~30 行,
        # 污染 MCP stdio JSON-RPC 帧 (见 mcp_server.py 的 stdio transport)。
        audit = audit_mod.collect()
        return json.dumps(
            {
                "overall_up_to_date": not audit["overall_needs_recompile"],
                "stale_modules": [d["module"] for d in audit["details"] if not d["is_up_to_date"]],
                "details": audit["details"],
                "latest_src_mtime": audit["latest_src_mtime"],
                "checked_at": audit["checked_at"],
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
