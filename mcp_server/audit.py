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
