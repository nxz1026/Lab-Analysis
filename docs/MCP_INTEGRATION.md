# MCP 集成指南

> 把 Lab-Analysis 的两个核心能力（DSPy 编译审计 + 6 指标量化评估）以 **MCP (Model Context Protocol) tool** 形式暴露给 LLM agent（Claude Desktop / Cursor / Cline 等）。

---

## 1. 是什么

[MCP](https://modelcontextprotocol.io/) 是 Anthropic 提出的"模型上下文协议"，让 LLM agent 能直接调用本地工具。

本项目 `mcp_server.py` 启动一个 **stdio MCP server**，注册 2 个 tool：

| Tool | 作用 | 何时调 |
|------|------|--------|
| `audit_dspy_models` | 检查 4 个 DSPy compiled JSON 是否 STALE（源代码 mtime > compiled mtime） | 改完 `lab_analysis/dspy_modules/*.py` 后，确认要不要重新 compile |
| `run_quant_eval(id_card, std_ts, dspy_ts)` | 对 std + dspy 两次跑做 6 指标量化（entity_f1 / section_coverage / failure_rate / entity_recall / confidence / feedback_delta） | 跑完 `dual_mode_pipeline --auto-pick --quant` 后看量化指标 |

---

## 2. 安装依赖

MCP 是 **optional** 依赖，不在 `[project.dependencies]` 里（避免污染主依赖）。

```bash
# 方式 1：用项目自带的 extra
pip install -e ".[mcp]"

# 方式 2：直接装 mcp 包
pip install "mcp>=1.0"
```

安装后验证：

```bash
python -c "from mcp.server.fastmcp import FastMCP; print('OK')"
```

---

## 3. 客户端配置

### 3.1 Claude Desktop

编辑 `%APPDATA%\Claude\claude_desktop_config.json`（Windows）或 `~/Library/Application Support/Claude/claude_desktop_config.json`（macOS）：

```json
{
  "mcpServers": {
    "lab-analysis": {
      "command": "python",
      "args": ["e:/2026Workplace/Code/Lab-Analysis/mcp_server.py"],
      "env": {
        "PYTHONPATH": "e:/2026Workplace/Code/Lab-Analysis"
      }
    }
  }
}
```

完整示例见 [`mcp_config.example.json`](../mcp_config.example.json)。

### 3.2 Cursor

`~/.cursor/mcp.json`（项目级放 `.cursor/mcp.json`）：

```json
{
  "mcpServers": {
    "lab-analysis": {
      "command": "python",
      "args": ["e:/2026Workplace/Code/Lab-Analysis/mcp_server.py"]
    }
  }
}
```

### 3.3 Cline (VSCode)

`.vscode/cline_mcp_settings.json` 同上格式。

---

## 4. 验证

### 4.1 命令行 smoke test

```bash
# 应该输出 FastMCP server 启动信息（不会自己退出，等 stdin）
python mcp_server.py
```

如果 2 秒后没崩 = OK。

### 4.2 跑 pytest 验证 2 个 tool 都能调通

```bash
python -m pytest tests/test_mcp_server.py -v
```

8 个 test 应全部 passed：覆盖 audit_dspy_models / run_quant_eval 基本流程、参数校验、metrics 完整性。

### 4.3 客户端里调

启动 Claude Desktop 后，agent 工具列表会多出 `lab-analysis::audit_dspy_models` 和 `lab-analysis::run_quant_eval`。

直接问：
- *"帮我看看 DSPy 4 个 module 是不是要重 compile"*
- *"对患者 846552421134373347 的 std (20260620_175252) + dspy (20260620_175730) 跑 6 指标量化"*

---

## 5. Tool 返回格式

### 5.1 `audit_dspy_models() -> str (JSON)`

```json
{
  "overall_up_to_date": true,
  "stale_modules": [],
  "details": [
    {
      "module": "lab_data_extractor",
      "compiled_at": "2026-06-21T12:34:56",
      "source_commit": "8df5cf8",
      "is_up_to_date": true,
      "reason": "compiled 比 source 新"
    }
  ],
  "latest_src_mtime": 1718900000.0,
  "checked_at": "2026-06-21T13:00:00"
}
```

返回字段含义：
- `overall_up_to_date` — `True` = 4 个 module 都不需要重 compile
- `stale_modules` — 需要重 compile 的 module 列表
- `details` — 每个 module 详细审计结果
- `latest_src_mtime` — 源代码最新 mtime（epoch 秒）
- `checked_at` — 检查时间

### 5.2 `run_quant_eval(id_card, std_ts, dspy_ts) -> str (JSON)`

```json
{
  "id_card": "846552421134373347",
  "std_ts": "20260620_175252",
  "dspy_ts": "20260620_175730",
  "text_lengths": { "std": 12345, "dspy": 11223 },
  "metrics": {
    "entity_f1":          { "f1": 0.88, "tp": 14, "fp": 2, "fn": 1, "available": true },
    "section_coverage":   { "coverage": 0.92, "present": 12, "total": 13, "available": true },
    "failure_rate":       { "rate": 0.0, "failed": 0, "total": 13, "available": true },
    "entity_recall":      { "recall": 0.93, "hit": 14, "miss": 1, "available": true },
    "confidence":         { "dspy_conf": 0.85, "std_score": 82, "delta": 0.03, "available": true },
    "feedback_delta":     { "delta": 0.05, "before": 0.75, "after": 0.80, "available": true }
  }
}
```

每个 metric 都有 `available` 字段 — `false` = 数据缺失（std_md / dspy_json / scoring_card / feedback.json 任何一个文件不存在），agent 应主动告知用户"数据不全"。

---

## 6. 常见问题

### Q1: `ModuleNotFoundError: No module named 'mcp'`

A: 没装 MCP SDK。`pip install -e ".[mcp]"`

### Q2: 客户端连上后 tool 调不通 / 立刻崩

A: 大概率 `PYTHONPATH` 没传。`mcp_server.py` 顶部有 `sys.path.insert(0, str(PROJECT_ROOT))`，理论上不需要，但 client 跑在隔离环境时还是建议显式传 env：

```json
"env": { "PYTHONPATH": "e:/2026Workplace/Code/Lab-Analysis" }
```

### Q3: 跑 `run_quant_eval` 报"数据文件不存在"

A: 先跑 `python examples/dual_mode_pipeline.py --id-card <ID> --auto-pick --quant` 生成 std + dspy 两次报告，再调 tool。

### Q4: 想加新 tool

A: 改 `mcp_server.py`，加一个 `@mcp.tool()` 装饰的函数，返回 `str`（推荐 JSON 字符串）。然后在 `tests/test_mcp_server.py` 加对应 test（参考现有 8 个 test 的写法）。

---

## 7. 文件清单

| 文件 | 行数 | 作用 |
|------|-----:|------|
| `mcp_server.py` | ~170 | MCP server 入口，2 个 tool |
| `mcp_config.example.json` | ~15 | 客户端配置示例 |
| `docs/MCP_INTEGRATION.md` | 本文件 | 集成指南 |
| `tests/test_mcp_server.py` | ~135 | 8 个 test 覆盖 2 tool |

---

## 8. 后续路线

- [ ] 加 `get_pipeline_status` tool（看最近一次 run 状态）
- [ ] 加 `list_patients` tool（`lab_analysis/multi_patient.py::list_patients` 包成 MCP）
- [ ] 加 `trigger_dspy_recompile` tool（远程触发 incremental compile）
- [ ] HTTP transport 模式（除了 stdio，方便远程调用）
