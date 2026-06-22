# Lab-Analysis

> 医学检验 + 文献循证 + 影像印证多源整合分析 Pipeline（DSPy 优化 + 量化评估）

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-passing-success.svg)](.github/workflows/tests.yml)
[![Quant Gate](https://img.shields.io/badge/Quant_Gate-6/6_PASS-success.svg)](lab_analysis/quant_metrics.py)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Tests](https://img.shields.io/badge/Tests-438_✔️-success.svg)](tests/)
[![MCP](https://img.shields.io/badge/MCP-6_Tools-purple.svg)](mcp_server.py)

---

## TL;DR

`pip install -e . && python -m lab_analysis` 一次摄入, 自动产出：

| 产物 | 形式 | 说明 |
|------|------|------|
| 7 张统计图表 + 异常告警 | PNG + JSON | 趋势/相关/炎症/异常/移动均值/CV/Z-score |
| 文献循证解读 | Markdown | PubMed top-k + 5 维证据打分 + LLM 解读 |
| 影像一致性报告 | Markdown | MRI + 检验交叉印证（Qwen-VL） |
| 综合临床报告 | Markdown / PDF | 9 章节，可选 FHIR R4 Bundle |
| **量化评估报告** | **PNG + HTML** | **6 指标 std vs dspy 自动打分 + 可视化** |
| **多 run 趋势图** | **PNG** | **同患者跨多次跑分的纵向趋势** |
| 评分卡 & 诊断假设 | JSON + MD | 5 维 0-100 + top-3 假设 |

LLM agent (Claude Desktop / Cursor) 可通过 **MCP server 6 个 tool** 直接调度整条流水线。

---

## 适用场景

- **临床研究** — 长期检验趋势、炎症分期演变、影像-检验跨模态印证
- **个案会诊** — 检验 + 文献 + 影像三源交叉印证 + 量化证据
- **教学复盘** — 文献循证与临床数据的可解释关联 + 评分卡置信度
- **LLM 应用研究** — DSPy prompt 优化 + 6 指标量化对比 + 双模式报告

---

## 核心特性

| 维度 | 说明 |
|------|------|
| **多源整合** | 检验数据（CSV/JSON）+ PubMed 文献 + MRI/DICOM 影像 + 文字报告 |
| **量化评估** | 6 维指标（实体 F1 / 章节覆盖 / 失败率 / 实体召回 / 置信度 / 反馈 Δ）+ 跨模态印证 #7 |
| **可视化** | 7 张统计图 + 单报告 PNG/HTML + 跨 run 趋势 PNG（暗色 / 响应式 / Print） |
| **CI Gate** | 6 指标 ≤ 阈值才放行，PR 自动贴结果（marker 防 spam） |
| **LLM 增强** | DSPy 4 模块 Standard/DSPy 双轨 + 自动编译 + prompt 快照 |
| **MCP Server** | 6 tool 暴露 pipeline 给 LLM agent（stdio） |
| **决策支持** | 5 维评分卡 + 加权诊断假设 + 反馈回路（动态调权） |
| **跨平台** | Windows / Linux 自动适配，PowerShell 兼容 |
| **可扩展** | 模块化设计，新增分析维度只需实现标准接口 |

---

## Pipeline 完整流程

```bash
python -m lab_analysis
```

运行时强制交互输入身份证号，依次自动执行 11 个步骤。支持 `--skip-xxx` 跳过关键步骤。

| 步骤 | 环节 | 模块 | 输入 → 输出 |
|------|------|------|-------------|
| ① | **数据摄入** | `ingest_data.py` | `raw/Origin_data/` 中检验图片 / DICOM / MRI 报告 → `raw/patient_<deid>/` |
| ② | **前置检查** | `pipeline.steps` | `raw/patient_<deid>/` 目录结构校验 → 通过/失败 |
| ③ | **数据加载** | `data_loader.py` | `.../metrics.md` → `lab_metrics.csv` + `.json` |
| ④ | **统计分析** | `analysis/run` | `lab_metrics.csv` → 7 张图表 + `analysis_results_report.md` + `alerts.json` |
| ⑤ | **文献检索** | `literature_searcher.py` | 检验项目 + 关键指标 → PubMed 摘要 `.md`（`--auto-queries` 自动生成搜索词） |
| ⑤b | **文献证据打分** | `literature_filter.py` | `literature_results.json` → `.filtered.json`（5 维 + S/A/B/C tier） |
| ⑥ | **循证解读** | `literature_interpreter(_dspy).py` | 文献摘要 + 检验数据 → 解读报告 + DSPy prompt |
| ⑦ | **影像分析** | `qwen_vl_report_check(_dspy).py` | MRI 报告 + 检验数据 → 一致性报告 + DSPy prompt |
| ⑧ | **综合报告** | `gen_final_report(_dspy).py` | ④⑤⑥⑦ 产物 → 9 章节综合报告（`--compare-mode` 双模式对比） |
| ⑧b | **评分卡 & 决策** | `scoring_card.py` | 多源数据 → 5 维评分 + top-3 诊断假设 |
| ⑧c | **量化评估** ✨ | `quant_metrics.py` + `quant_visualizer.py` | std vs dspy 全章节 → 6 指标 + 跨模态印证 + PNG + HTML + gate |
| ⑨ | **本地归档** | `organize_local_files.py` | `data/<id>/<ts>/` → `local_upload/<YYYY-MM-DD>/` |
| ⑨b | **FHIR 输出** | `fhir_exporter.py` | 多源数据 → HL7 FHIR R4 Bundle（Patient/Observation/RiskAssessment） |
| ⑩ | **旧产物清理** | `cleanup_runs.py` | 自动删除旧批次，保留最近 N 次（`--keep-last 3`） |

> 步骤 ⑥⑦⑧ 在 `--use-dspy` 时切换为 DSPy 优化模式，并保存优化后 prompt 供对比。
> 步骤 ⑧c 在 std 与 dspy 都跑过后自动触发，量化打分 + gate。

### 流程图

```
[① 数据摄入] → [② 前置检查] → [③ 数据加载] → [④ 统计分析]
                                                    ↓
[⑩ 产物清理] ← [⑨ 本地归档] ← [⑨b FHIR] ← [⑧b 评分卡] ← [⑧c 量化评估] ← [⑧ 综合报告] ← [⑦ 影像分析] ← [⑥ 循证解读] ← [⑤b 文献打分] ← [⑤ 文献检索]
```

---

## 量化评估与可视化 ✨

DSPy 优化是否真的比 Standard 模式好？6 个量化指标 + 可视化报告 + CI gate 自动判定。

### 6 维指标（`lab_analysis/quant_metrics.py`）

| # | 指标 | 含义 | OK 阈值 |
|---|------|------|---------|
| 1 | `entity_f1` | DSPy 实体 vs 标准实体 F1 | ≥ 0.70 |
| 2 | `section_coverage` | 9 章节覆盖度 | ≥ 0.80 |
| 3 | `failure_rate` | 解析失败率（反向） | is_failure = False |
| 4 | `entity_recall` | 标准实体被 DSPy 召回率 | ≥ 0.70 |
| 5 | `confidence` | DSPy 置信度校准 | ≥ 0.60 |
| 6 | `feedback_delta` | 用户反馈前后的 Δ confidence | n_corrections ≥ 0（始终显示） |
| 7 | `cross_modality_consistency` 🆕 | 影像-检验跨模态印证 | ≥ 0.70 |

### 输出产物（每 run）

```
data/<deid>/<ts>/04_reports/
├── quant_eval_report.json              # 6 指标完整结果 + cross_modality #7
├── quant_eval_report.png               # 6 维柱状图（X 轴全显示 + OK/FAIL 标签）
├── quant_eval_report.html              # 单文件可视化（暗色 / 响应式 / Print 按钮 / 可折叠）
├── quant_eval_gate_result.json         # gate 决策（PASS/FAIL）+ 每项 OK/FAIL/SKIP
└── .latest.txt                         # 文本占位，指向最新 dspy_ts（Win 不支持 symlink）

data/_all/trend/
└── quant_eval_trend.png                # 跨 run 纵向趋势（多 patient 混排或单 patient）
```

### CI Gate

GitHub Actions 在 PR 上自动跑 `quant_eval_gate` job：6 指标全 ≤ 阈值才 ✅，否则 ❌ 阻断 merge。结果自动贴到 PR 评论（marker 防 spam）。

### 量化评估 CLI / MCP

```bash
# CLI 单独跑
python -c "from mcp_server import run_quant_eval; print(run_quant_eval('846552421134373347','20260620_175730'))"

# MCP tool 暴露给 LLM agent
mcp_server.render_quant_trend(patient_id='846552421134373347', x_key='std_ts')
```

---

## MCP Server（LLM Agent 集成）

`mcp_server.py` 暴露 **6 个 tool** 给 Claude Desktop / Cursor 等 LLM agent 通过 stdio 调用：

| # | Tool | 用途 | 关键参数 |
|---|------|------|---------|
| 1 | `audit_dspy_models` | 检查 4 个 DSPy compiled JSON 是否 STALE | — |
| 2 | `run_quant_eval` | 跑 6 指标量化评估 + 自动 gate + 可视化 | `deid`, `ts` |
| 3 | `list_patients` | 列出 data/ 下所有 patient + 样本统计 + std/dspy 配对 | — |
| 4 | `get_pipeline_status` | 看指定 patient (可选 timestamp) 的 pipeline 运行状态 | `patient_id`, `timestamp` |
| 5 | `trigger_dspy_recompile` | 触发增量/全量 DSPy 4 module recompile (subprocess) | `force`, `timeout_sec` |
| 6 | `render_quant_trend` | 串多 quant_eval_report.json 渲染多 run trend PNG | `patient_id`, `out_dir`, `x_key` |

启动：

```bash
python mcp_server.py          # stdio transport 默认
```

Claude Desktop `claude_desktop_config.json` 示例：

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

---

## 项目结构

```
Lab-Analysis/
├── lab_analysis/                         # 核心代码包
│   ├── pipeline/                         #   Pipeline 编排
│   │   ├── cli.py                        #     命令行解析
│   │   ├── steps.py                      #     子步骤（检查/子进程/日志）
│   │   ├── ingest.py                     #     自动数据摄入
│   │   └── run.py                        #     main 编排器
│   ├── analysis/                         #   统计分析子包
│   │   ├── _base.py                      #     常量 / 参考范围 / 绘图工具
│   │   ├── _compute.py                   #     纯计算函数（回归/分类/异常检测）
│   │   ├── charts.py                     #     7 张统计图表
│   │   └── run.py                        #     编排器 + Markdown 报告生成
│   ├── quant_metrics.py                  # ✨ 6 维量化指标 + 跨模态印证 + gate 决策
│   ├── quant_visualizer.py               # ✨ PNG / HTML / 趋势 PNG 渲染
│   ├── alert_generator.py                #   结构化异常告警摘要（CRITICAL/WARNING/INFO）
│   ├── scoring_card.py                   #   评分卡 & 临床决策支持（5 维 + 诊断假设）
│   ├── compare_report_modes.py           #   Standard vs DSPy 双模式报告对比
│   ├── gen_final_report_pdf.py           #   Markdown → PDF（可选依赖）
│   ├── dashboard.py                      #   Streamlit 趋势看板（可选）
│   ├── cleanup_runs.py                   #   Pipeline 产物清理
│   ├── report_schema.py                  #   综合报告 9 章节模板
│   ├── ingest_data.py                    # ①
│   ├── data_loader.py                    # ③
│   ├── literature_searcher.py            # ⑤ PubMed 检索（--auto-queries）
│   ├── evidence_grader.py                # ⑤b 5 维证据打分
│   ├── literature_filter.py              # ⑤b CLI 封装
│   ├── literature_interpreter.py         # ⑥ 标准
│   ├── literature_interpreter_dspy.py    # ⑥ DSPy
│   ├── qwen_vl_report_check.py           # ⑦ 标准
│   ├── qwen_vl_report_check_dspy.py      # ⑦ DSPy
│   ├── gen_final_report.py               # ⑧ 标准
│   ├── gen_final_report_dspy.py          # ⑧ DSPy
│   ├── extract_lab_data.py               #   检验 OCR
│   ├── batch_vision_extract.py           #   批量视觉提取
│   ├── llm_client.py                     #   LLM API 客户端（DeepSeek / DashScope）
│   ├── patient_id.py                     #   AES-GCM 脱敏与校验
│   ├── error_logger.py                   #   错误日志
│   ├── utils.py                          #   通用工具（平台适配 / 路径）
│   ├── organize_local_files.py           # ⑨
│   ├── feedback.py                       #   反馈回路（动态调评分卡置信度）
│   ├── fhir_exporter.py                  # ⑨b FHIR R4 Bundle
│   ├── upload_to_feishu_backup.py        #   飞书备份（实验性）
│   └── dspy_modules/                     #   DSPy 优化模块
│       ├── literature_interpreter.py
│       ├── mri_analyzer.py
│       ├── final_report_generator.py
│       ├── lab_data_extractor.py
│       └── prompt_inspector.py
├── mcp_server.py                         # ✨ MCP server (6 tools, stdio)
├── tests/                                # pytest（438 用例）
│   ├── conftest.py
│   ├── test_pipeline_e2e.py
│   ├── test_pipeline_cli.py
│   ├── test_mcp_server.py                # ✨ MCP 6 tools 单测
│   ├── test_quant_metrics.py             # ✨ 6 指标单测
│   ├── test_quant_visualizer.py          # ✨ PNG / HTML 渲染单测
│   ├── test_quant_eval_gate.py           # ✨ gate 决策单测
│   ├── test_dspy_modules.py
│   ├── test_compare_modes.py
│   ├── test_alert_generator.py
│   ├── test_scoring_card.py
│   ├── test_cleanup_runs.py
│   ├── test_extract_lab_data.py
│   ├── test_evidence_grader.py
│   ├── test_feedback.py
│   ├── test_fhir_exporter.py
│   ├── test_lab_prediction.py
│   ├── test_patient_id.py
│   ├── test_report_schema_models.py
│   ├── test_utils.py
│   └── test_multi_patient.py             # ✨ 多 patient 隔离
├── scripts/                              # 调试/对比脚本
├── examples/                             # 示例与工具
├── docs/                                 # 补充文档
│   ├── DSPY_INTEGRATION.md
│   ├── DSPY_USAGE.md
│   └── EVIDENCE_GRADING.md
├── models/dspy/                          # 编译后 DSPy 模型
├── data/                                 # 分析结果（按患者+时间戳）
├── local_upload/                         # 本地归档（按日期）
├── .github/workflows/
│   └── tests.yml                         #   CI（test + quant_eval_gate + PR comment）
├── pyproject.toml
└── run_analysis.py                       # 便捷启动
```

---

## 安装与配置

### 环境要求

- **Python**: 3.10+
- **OS**: Windows 10/11、macOS、Linux
- **磁盘**: ≥ 5 GB（含 DICOM 解压缓存）

### 安装

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .

# 可选依赖组
pip install "lab-analysis[dspy]"       # DSPy 模式（dspy-ai, pydicom）
pip install "lab-analysis[pdf]"        # PDF 报告（weasyprint, markdown）
pip install "lab-analysis[dashboard]"  # Streamlit 看板
pip install "lab-analysis[mcp]"        # MCP server（mcp）
pip install "lab-analysis[dev]"        # 开发工具（ruff, pytest）
```

### 环境变量

```bash
cp .env.example .env
```

| 变量 | 必填 | 用途 | 提供方 |
|------|------|------|--------|
| `WORK_ROOT` | 是 | 工作根目录（默认当前目录） | — |
| `DEEPSEEK_API_KEY` | 是 | 文献解读 / 报告生成 | DeepSeek |
| `DASHSCOPE_API_KEY` | 是 | 影像分析（Qwen-VL） | 阿里云百炼 |
| `SCNET_OCR_API_KEY` | 否 | 检验报告图片 OCR | SCNet |
| `FEISHU_FOLDER_TOKEN` | 否 | 飞书云盘上传（实验性） | 飞书 |

---

## 运行指南

### 一键运行

```bash
python -m lab_analysis                          # 标准模式（交互输入 ID）
python -m lab_analysis --use-dspy               # DSPy 优化模式
```

### 跳过指定步骤

```bash
python -m lab_analysis --skip-ingest --skip-pdf --skip-cleanup
```

### 新功能示例

```bash
# 自动 PubMed 搜索词（基于异常指标）
python -m lab_analysis --auto-queries

# Standard / DSPy 双模式对比
python -m lab_analysis --compare-report-modes

# 产物清理（保留最近 5 次）
python -m lab_analysis --keep-last 5

# 量化评估（指定患者 + ts）
python -c "from mcp_server import run_quant_eval; print(run_quant_eval('846552421134373347','20260620_175730'))"

# 多 run 趋势图
python -c "from mcp_server import render_quant_trend; print(render_quant_trend('846552421134373347'))"

# Streamlit 看板
pip install "lab-analysis[dashboard]"
streamlit run lab_analysis/dashboard.py
```

### 单独调试某步

```bash
python -m lab_analysis.data_loader    --id-card <脱敏ID>
python -m lab_analysis.scoring_card   --id-card <脱敏ID>
python -m lab_analysis.cleanup_runs   --keep-last 3 --dry-run
python -m lab_analysis.fhir_exporter  --id-card <脱敏ID>
```

单独运行步骤 ⑥⑦⑧ 时需要 `ANALYSIS_TS`：

```powershell
$env:ANALYSIS_TS="20260611_111343"
python -m lab_analysis.literature_interpreter --id-card <脱敏ID>
```

---

## 输出产物

```
data/{patient_id}/{timestamp}/
├── lab_metrics.csv                       # 检验数据（CSV）
├── lab_metrics.json                      # 检验数据（JSON，含脱敏）
├── analysis_results.json                 # 统计分析（含 predictions）
├── alerts.json                           # 结构化异常告警
├── fig_01~fig_07.png                     # 7 张统计图表
├── analysis_results_report.md            # 统计分析报告
├── literature_results.json               # PubMed 检索结果
├── literature_results.filtered.json      # 5 维证据打分（S/A/B/C tier）
├── literature_interpretation.md          # 文献解读
├── mri_report_check_results.md           # 影像一致性报告
├── final_integrated_report.md            # 最终综合报告（9 章节）
├── final_integrated_report.pdf           # PDF（可选）
├── scoring_card.json                     # 评分卡 + top-3 假设
├── scoring_card.md                       # 评分卡可读版
├── mode_comparison_report.md             # Standard/DSPy 对比
├── mode_comparison.json
├── quant_eval_report.json                # ✨ 6 指标量化评估
├── quant_eval_report.png                 # ✨ 6 维柱状图
├── quant_eval_report.html                # ✨ 单文件可视化
├── quant_eval_gate_result.json           # ✨ gate 决策
├── .latest.txt                           # ✨ 文本占位（最新 dspy_ts）
├── fhir_bundle.json                      # HL7 FHIR R4 Bundle
├── feedback.json                         # 用户反馈数据
├── reports/dspy_prompt_comparison.{md,json}
└── dspy_prompts/                         # DSPy prompt 快照

data/_all/trend/
└── quant_eval_trend.png                  # ✨ 跨 run 趋势图
```

---

## 新增功能详述

### 结构化异常告警摘要（步骤④）

`alerts.json` 自动生成：

| 级别 | 触发条件 |
|------|---------|
| CRITICAL | hs-CRP 急性期 / 严重 Z-score 异常 / 同指标 ≥3 次超参考范围 |
| WARNING | 超参考范围 / CV>0.2 高变异 / 显著上升趋势 |
| INFO | 轻度 Z-score 异常 / 下降趋势 |

### 评分卡 & 临床决策（步骤⑧b）

纯规则引擎，不调 LLM，5 维 0-100 + 加权诊断假设：

| 维度 | 数据源 | 含义 |
|------|--------|------|
| `inflammation` | hs-CRP 分期 + 趋势 | 炎症活跃度 |
| `lab_abnormality` | 异常指标 + Z-score | 异常显著度 |
| `literature_support` | 证据打分 | 文献证据充分度 |
| `imaging_consistency` | MRI 一致性报告 | 影像-检验一致度 |
| `variability_stability` | CV 稳定性 | 指标稳定性 |

### PubMed 搜索词自动生成

```bash
python -m lab_analysis --auto-queries
```

根据 `analysis_results.json` 异常指标自动生成策略。例如 `hs-CRP↑` → `"chronic pancreatitis" AND ("hs-CRP" OR "high-sensitivity CRP")`。

### Standard / DSPy 双模式对比

```bash
python -m lab_analysis.gen_final_report --id-card <deid> --compare-mode
```

按 9 章节逐段对比：字符数 / 内容重叠率 / 关键实体提及差异 → `mode_comparison_report.md`。

### 反馈回路

```bash
python -m lab_analysis.feedback --id-card <deid> --show
python -m lab_analysis.feedback --id-card <deid> --correct \
  --original "慢性胰腺炎（活动期）" --corrected "急性胰腺炎" \
  --confidence 0.90 --comment "临床确诊"
python -m lab_analysis.feedback --id-card <deid> --clear
```

写入 `feedback.json`，下次 pipeline 自动调整评分卡置信度，并写入 `feedback_delta` 指标。

### 指标预测（步骤④）

基于时间序列线性回归 + 95% CI 预测下次就诊指标：

```
hs-CRP: 下次预测=14.300  95%CI=[11.200, 17.400]  上升 ⚠️ 预测值超过阈值 3.0
```

### FHIR 输出（步骤⑨b）

多源结果映射 HL7 FHIR R4 Bundle：Patient / Observation（含 LOINC）/ RiskAssessment / DiagnosticReport。可对接任意 FHIR R4 兼容系统。

### Streamlit 看板

```bash
pip install "lab-analysis[dashboard]"
streamlit run lab_analysis/dashboard.py
```

4 Tab：概览（炎症 timeline + 告警）/ 7 张图表 / 检验表 / 最终报告。

### 产物清理

```bash
python -m lab_analysis.cleanup_runs --keep-last 3            # 保留最近 3 次
python -m lab_analysis.cleanup_runs --keep-last 5 --dry-run  # 预览
python -m lab_analysis.cleanup_runs --keep-last 2 --id-card <deid>
```

---

## 证据打分（步骤⑤b）

详见 [docs/EVIDENCE_GRADING.md](docs/EVIDENCE_GRADING.md)：

- 5 维打分：主题匹配 / 证据等级 / 时效性 / 样本量 / 解析质量
- 3 种场景权重：`early_diagnosis` / `differential_diagnosis` / `prognosis`
- S / A / B / C 四档 tier
- 纯规则，不调 LLM，可重复可测试

CLI：

```
--skip-lit-filter
--lit-filter-scenario {early_diagnosis|differential_diagnosis|differential_diagnosis}
--lit-filter-top-k INT          # 默认 8
```

---

## DSPy 增强

4 个 LLM 核心模块实现 Standard + DSPy 双轨：

| 模块 | 标准版 | DSPy 版 |
|------|--------|---------|
| 文献循证解读 | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` |
| 影像报告分析 | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` |
| 综合报告生成 | `gen_final_report.py` | `dspy_modules/final_report_generator.py` |
| 检验数据提取 | `extract_lab_data.py` | `dspy_modules/lab_data_extractor.py` |

详见 [docs/DSPY_INTEGRATION.md](docs/DSPY_INTEGRATION.md) 和 [docs/DSPY_USAGE.md](docs/DSPY_USAGE.md)。

---

## CI / CD

GitHub Actions `.github/workflows/tests.yml`：

| Job | 触发 | 内容 |
|-----|------|------|
| `test` | push / PR | pytest 矩阵（3.10~3.13）+ ruff |
| `quant_eval_gate` | push / PR | 6 指标量化评估 + gate 决策 + **自动 PR 评论**（marker 防 spam） |

PR 评论样式：

> ### Quant Eval Gate
> **deid=846552421134373347 ts=20260620_175730**
> | metric | value | status |
> |--------|-------|--------|
> | entity_f1 | 0.94 | OK |
> | ... | ... | ... |
> **Overall: PASS ✅**

---

## 技术栈

| 领域 | 选型 |
|------|------|
| 数据 | pandas, numpy, scipy |
| ML | scikit-learn |
| 可视化 | matplotlib, Streamlit |
| 图像 | Pillow, pydicom |
| PDF | weasyprint, markdown（可选） |
| OCR / Vision | SCNet OCR, 阿里云 Qwen-VL |
| 文本生成 | DeepSeek API（OpenAI 兼容） |
| LLM 优化 | DSPy 3.2+（BootstrapFewShot / MIPROv2） |
| 文献 | PubMed E-utilities |
| MCP | mcp（FastMCP, stdio） |
| 错误处理 | tenacity + 自研 error_logger |
| 测试 | pytest（438 用例） |
| CI | GitHub Actions |

---

## 开发指南

```bash
pip install -e ".[dev]"
python -m pytest                  # 全量 438 用例
python -m pytest -v --cov         # 带覆盖率
ruff check lab_analysis/          # 代码风格
```

### 代码规范

- PEP 8 + 类型注解
- 路径统一 `pathlib.Path`
- 优先 `WORK_ROOT` + 相对路径
- 双模式脚本命名 `<module>_dspy.py`
- 平台适配：`utils.is_windows()`

### 添加新模块

1. 在 `lab_analysis/` 创建模块
2. 实现 `main_with_args(args)` 标准接口
3. 在 `pipeline/run.py` 中 `run_step()` 注册
4. 涉及 LLM：同步实现 DSPy 版 + `prompt_inspector` 集成

### 添加量化指标

1. 在 `lab_analysis/quant_metrics.py` 加函数 + 默认 `available=True` 兜底
2. `DEFAULT_THRESHOLDS` 加阈值
3. `quant_visualizer.py` `_extract_metric_value` 加分支
4. `tests/test_quant_metrics.py` + `tests/test_quant_visualizer.py` 加单测
5. `README.md` 表格更新

---

## 进阶文档

- [DSPy 集成技术方案](docs/DSPY_INTEGRATION.md)
- [DSPy 使用指南](docs/DSPY_USAGE.md)
- [证据打分说明](docs/EVIDENCE_GRADING.md)

---

## 贡献

欢迎 Issue 与 PR：

1. Fork
2. `git checkout -b feature/xxx`
3. `git commit -m 'feat: xxx'`
4. `git push origin feature/xxx`
5. 发 PR

---

## 许可证

MIT — 详见 [LICENSE](LICENSE)

---

## 作者

**nxz1026** — [GitHub @nxz1026](https://github.com/nxz1026)

---

## 致谢

- DeepSeek / SCNet / 阿里云百炼（Qwen-VL）
- Stanford NLP 的 [DSPy](https://dspy.ai/)
- PubMed E-utilities
- [FastMCP](https://github.com/jlowin/fastmcp) MCP 框架

---

⭐ 如果这个项目对您有帮助，请给个 Star！