# MCP 集成指南

> 把 Lab-Analysis 的 6 个核心能力以 **MCP (Model Context Protocol) tool** 形式暴露给 LLM agent（Claude Desktop / Cursor / Cline 等），让 agent 直接调度整条 pipeline。

---

## 1. 是什么

[MCP](https://modelcontextprotocol.io/) 是 Anthropic 提出的"模型上下文协议"，让 LLM agent 能直接调用本地工具。

本项目 `mcp_server.py` 启动一个 **stdio MCP server**，注册 **6 个 tool**：

| # | Tool | 作用 | 何时调 |
|---|------|------|--------|
| 1 | `audit_dspy_models` | 检查 4 个 DSPy compiled JSON 是否 STALE（源代码 mtime > compiled mtime） | 改完 `lab_analysis/dspy_modules/*.py` 后，确认要不要重新 compile |
| 2 | `run_quant_eval(id_card, std_ts, dspy_ts)` | 对 std + dspy 两次跑做 **7 指标**量化评估（entity_f1 / section_coverage / failure_rate / entity_recall / confidence / feedback_delta / **cross_modality_consistency #7**）+ 自动 gate + 可视化 PNG/HTML | 跑完 dual_mode pipeline 后看量化指标 |
| 3 | `list_patients()` | 列出 `data/` 下所有 patient + 样本统计 + std/dspy 配对 | agent 想知道"有哪些患者可以跑"时 |
| 4 | `get_pipeline_status(patient_id, timestamp)` | 看指定 patient (可选 timestamp) 的 pipeline 运行状态（哪几步完成 / 失败 / 跳过） | agent 想知道"这个患者跑完了没"时 |
| 5 | `trigger_dspy_recompile(force, timeout_sec)` | 触发增量/全量 DSPy 4 module recompile (subprocess) | agent 想让模型用最新数据重训时 |
| 6 | `render_quant_trend(patient_id, out_dir, x_key)` | 串多 `quant_eval_report.json` 渲染多 run trend PNG（PNG 写到 `data/{patient or _all}/trend/`） | agent 想看"这个患者 6 指标跨多次跑的趋势"时 |

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

### 4.2 跑 pytest 验证 6 个 tool 都能调通

```bash
python -m pytest tests/test_mcp_server.py -v
```

**18+ test 应全部 passed**：覆盖 6 tool 的基本流程、参数校验、metrics 完整性、traceback 错误处理。

### 4.3 客户端里调

启动 Claude Desktop 后，agent 工具列表会多出 `lab-analysis::*` 共 6 个 tool。

直接问：
- *"帮我看看 DSPy 4 个 module 是不是要重 compile"*
- *"列出 data/ 下所有患者"*
- *"对患者 846552421134373347 的 std (20260620_175252) + dspy (20260620_175730) 跑 7 指标量化"*
- *"给我画一张该患者跨多次跑的指标趋势图"*

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

### 5.2 `run_quant_eval(id_card, std_ts, dspy_ts, run_gate, render_visual, out_dir) -> str (JSON)`

```json
{
  "id_card": "846552421134373347",
  "std_ts": "20260620_175252",
  "dspy_ts": "20260620_175730",
  "text_lengths": { "std": 12345, "dspy": 11223 },
  "metrics": {
    "entity_f1":                  { "f1": 0.88, "available": true },
    "section_coverage":           { "coverage_rate": 0.92, "available": true },
    "failure_rate":               { "is_failure": false, "available": true },
    "entity_recall":              { "recall_rate": 0.93, "available": true },
    "confidence":                 { "dspy_confidence": 0.85, "available": true },
    "feedback_delta":             { "n_corrections": 0, "available": true },
    "cross_modality_consistency": { "accuracy": 1.0, "available": true }
  },
  "gate": {
    "passed": true,
    "n_passed": 7,
    "n_failed": 0,
    "n_skipped": 0,
    "details": [...]
  },
  "artifacts": {
    "json_path": ".../quant_eval_report.json",
    "png_path":  ".../quant_eval_report.png",
    "html_path": ".../quant_eval_report.html",
    "sidecar_path": ".../quant_eval_gate_result.json",
    "latest_marker": ".../.latest.txt"
  }
}
```

每个 metric 都有 `available` 字段 — `false` = 数据缺失（std_md / dspy_json / scoring_card / feedback.json 任何一个文件不存在），agent 应主动告知用户"数据不全"。

异常时返回：

```json
{
  "error": "FileNotFoundError: ...",
  "type": "FileNotFoundError",
  "traceback": "Traceback (most recent call last):\n  ..."
}
```

### 5.3 `list_patients() -> str (JSON)`

```json
[
  {
    "patient_id": "846552421134373347",
    "n_runs": 2,
    "runs": [
      { "ts": "20260620_175252", "has_std": true, "has_dspy": false },
      { "ts": "20260620_175730", "has_std": false, "has_dspy": true }
    ]
  }
]
```

### 5.4 `get_pipeline_status(patient_id, timestamp) -> str (JSON)`

```json
{
  "patient_id": "846552421134373347",
  "timestamp": "20260620_175730",
  "steps": [
    { "name": "ingest", "status": "done", "duration_sec": 1.2 },
    { "name": "analysis", "status": "done", "duration_sec": 5.4 },
    { "name": "llm_interpretation", "status": "done", "duration_sec": 12.1 },
    { "name": "quant_eval", "status": "done", "duration_sec": 0.8 }
  ],
  "overall_status": "done"
}
```

### 5.5 `trigger_dspy_recompile(force, timeout_sec) -> str (JSON)`

```json
{
  "ok": true,
  "modules_recompiled": ["lab_data_extractor", "mri_analyzer"],
  "modules_skipped": ["literature_interpreter", "final_report_generator"],
  "duration_sec": 47.3
}
```

### 5.6 `render_quant_trend(patient_id, out_dir, x_key) -> str (JSON)`

```json
{
  "n_reports": 2,
  "x_key": "std_ts",
  "png_path": "E:/2026Workplace/Code/Lab-Analysis/data/_all/trend/quant_eval_trend.png",
  "report_ids": [
    "846552421134373347/20260620_175252",
    "846552421134373347/20260620_175730"
  ]
}
```

参数：
- `patient_id=""` — 不传则全 patient 混排，传则只取该 patient
- `out_dir=""` — PNG 输出目录（默认 = `data/{patient_id or '_all'}/trend/`）
- `x_key="std_ts"` — X 轴 label 来源（`std_ts` / `dspy_ts` / `deid`）

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

A: 先跑 `python -m lab_analysis --use-dspy` 生成 std + dspy 两次报告，再调 tool。

### Q4: 调 tool 返回的 JSON 里 `error` 字段非空

A: v2 起所有 tool 异常都包含 `traceback` 字段（Python 完整堆栈），agent 可直接把 traceback 贴给用户便于排查。

### Q5: 想加新 tool

A: 改 `mcp_server.py`，加一个 `@mcp.tool()` 装饰的函数，返回 `str`（推荐 JSON 字符串）。然后在 `tests/test_mcp_server.py` 加对应 test（参考现有 18 个 test 的写法）。

---

## 7. 文件清单

| 文件 | 行数 | 作用 |
|------|-----:|------|
| `mcp_server.py` | ~640 | MCP server 入口，6 个 tool |
| `mcp_config.example.json` | ~15 | 客户端配置示例 |
| `docs/MCP_INTEGRATION.md` | 本文件 | 集成指南 |
| `tests/test_mcp_server.py` | ~250 | 18 个 test 覆盖 6 tool |

---

## 8. 与 LLM agent 的典型对话流

```
用户: 帮我看看患者 846552421134373347 的 DSPy 报告有没有问题
agent:
  1. list_patients() → 找到 1 个 patient
  2. get_pipeline_status(846552421134373347) → 最近 run 已 done
  3. run_quant_eval('846552421134373347', '<最近 std_ts>', '<最近 dspy_ts>') → 7 指标 + gate
  4. 把 gate_result 转成人话: "entity_f1=0.88 PASS, cross_modality=1.0 PASS, 7/7 通过"

用户: 给我画一下趋势图
agent:
  1. render_quant_trend(patient_id='846552421134373347')
  2. 返回 PNG 路径, agent 在 chat 里展示 (multimodal 模型) 或写本地路径给用户
```

---

## 9. 路线图

- [x] 6 tool 全部上线（2026-06-22）
- [x] 异常加 traceback 字段（v2, 2026-06-22）
- [x] 7 指标 + 跨模态印证 #7 接全链路（v2, 2026-06-22）
- [ ] HTTP transport 模式（除了 stdio，方便远程调用 / 多用户）
- [ ] render_quant_trend 加 lru_cache (避免每次都重扫全 data/)
- [ ] input_schema 用 Pydantic 注解（替代纯 docstring 描述）