"""MCP server for Lab-Analysis — 启动入口 (薄 shim)。

实际逻辑在 mcp_server/ 包内按 tool 拆分:
    audit, quant_eval, patient, recompile, trend

启动 (stdio, 用于 Claude Desktop / Cursor / IDE):
    python mcp_server.py

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

from mcp_server import mcp

if __name__ == "__main__":
    mcp.run()  # stdio transport 默认
