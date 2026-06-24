# Lab-Analysis

> 医学检验 + 文献循证 + 影像印证 多源整合分析 Pipeline（DSPy 双轨 + 量化评估 + CI Gate）

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-passing-success.svg)](.github/workflows/tests.yml)
[![Quant Gate](https://img.shields.io/badge/Quant_Gate-6/6_PASS-success.svg)](lab_analysis/quant_metrics.py)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Tests](https://img.shields.io/badge/Tests-606_✔️-success.svg)](tests/)
[![MCP](https://img.shields.io/badge/MCP-6_Tools-purple.svg)](mcp_server.py)
[![Coverage](https://img.shields.io/badge/Coverage-60%25-yellow.svg)](pyproject.toml)
[![Code Style](https://img.shields.io/badge/Code-Ruff-blueviolet.svg)](pyproject.toml)

> [English Version](README_EN.md)

---

## TL;DR

```bash
pip install -e ".[dspy]" && python -m lab_analysis
```

一次命令，自动产出：

| 产物 | 形式 | 说明 |
|------|------|------|
| 7 张统计图表 + 异常告警 | PNG + JSON | 趋势/相关/炎症/异常/移动均值/CV/Z-score |
| 文献循证解读 | Markdown | PubMed top-k + 5 维证据打分 + LLM 解读 |
| 影像一致性报告 | Markdown | MRI + 检验交叉印证（Qwen-VL） |
| 综合临床报告 | Markdown / JSON / FHIR | 9 章节 + 可选 FHIR R4 Bundle |
| **量化评估报告** | **PNG + HTML** | **6 指标 std vs dspy 自动打分 + 可视化** |
| **多 run 趋势图** | **PNG** | **同患者跨多次跑分的纵向趋势** |
| 评分卡 & 诊断假设 | JSON + MD | 5 维 0-100 + top-3 假设 |

LLM agent (Claude Desktop / Cursor) 可通过 **MCP server 6 个 tool** 直接调度整条流水线。

---

## 功能特性

| 维度 | 描述 |
|------|------|
| **多源整合** | 检验数据 CSV/JSON + PubMed 文献 + MRI/DICOM + 文本报告 |
| **量化评估** | 6 项指标 (实体 F1 / 覆盖度 / 失败率 / 召回率 / 置信度 / 反馈 Δ) + 跨模态一致性 |
| **可视化** | 7 张统计图表 + 单次 PNG/HTML + 跨次趋势图 (暗色/响应式/可打印) |
| **CI 门控** | 6 项指标均需通过阈值方可合入 PR；自动 PR 评论 |
| **LLM 双轨** | 4 个 DSPy 模块：标准模式 vs DSPy 优化，自动编译，prompt 快照 |
| **MCP 服务** | 6 个工具，通过 stdio 向 LLM agent 暴露流水线能力 |
| **决策支持** | 5 维评分卡 + 加权诊断假设 + 反馈闭环 |
| **PHI 保护** | AES-256-GCM 确定性去标识；日志/CLI/环境变量中无明文 ID |
| **跨平台** | Windows / Linux 自适应，兼容 PowerShell |
| **可扩展** | 模块化设计，通过标准接口添加新的分析维度 |

---

## 流水线流程

```bash
python -m lab_analysis [--use-dspy] [--skip-xxx]
```

| 步骤 | 阶段 | 模块 | 输入 → 输出 |
|------|------|------|-------------|
| ① | **数据摄入** | `ingest_data/` | `raw/Origin_data/` 图片/DICOM/MRI → `raw/patient_<deid>/` |
| ② | **前置检查** | `pipeline.steps` | 校验目录结构 |
| ③ | **数据加载** | `data_loader.py` | `metrics.md` → `lab_metrics.csv` + `.json` |
| ④ | **统计分析** | `analysis/` | CSV → 7 张图表 + `analysis_results_report.md` + `alerts.json` |
| ⑤ | **文献检索** | `literature_searcher/` | 检验指标 → PubMed 摘要 `.md`（自动生成查询词） |
| ⑤b | **证据分级** | `literature_filter.py` | 检索结果 → 5 维过滤 + S/A/B/C 等级 |
| ⑥ | **文献解读** | `literature_interpreter(_dspy).py` | 文献 + 检验数据 → 解读报告 |
| ⑦ | **影像分析** | `qwen_vl_report_check(_dspy).py` | MRI 报告 + 检验数据 → 一致性报告 |
| ⑧ | **综合报告** | `gen_final_report(_dspy).py` | 步骤 ④⑤⑥⑦ → 9 章节综合报告 |
| ⑧b | **评分卡** | `scoring_card/` | 多源数据 → 5 维评分 + top-3 假设 |
| ⑧c | **量化评估** ★ | `quant_metrics.py` + `quant_visualizer.py` | std vs dspy → 6 项指标 + PNG + HTML + 门控 |
| ⑨ | **归档** | `organize_local_files.py` | `data/<id>/<ts>/` → `local_upload/<YYYY-MM-DD>/` |
| ⑨b | **FHIR 导出** | `fhir_exporter.py` | 结果 → HL7 FHIR R4 Bundle |
| ⑩ | **清理** | `cleanup_runs.py` | 自动删除旧 run，保留最近 N 个 (`--keep-last 3`) |

> 步骤 ⑥⑦⑧ 使用 `--use-dspy` 切换到 DSPy 模式，保存优化后的 prompt。
> 步骤 ⑧c 在 std 和 dspy 两种模式均存在时自动触发。

### 流程图

```
[① 数据摄入] → [② 前置检查] → [③ 数据加载] → [④ 统计分析]
                                                       ↓
[⑩ 清理] ← [⑨ 归档] ← [⑨b FHIR] ← [⑧b 评分卡] ← [⑧c 量化评估] ← [⑧ 综合报告] ← [⑦ 影像分析] ← [⑥ 文献解读] ← [⑤b 证据分级] ← [⑤ 文献检索]
```

---

## 量化评估与可视化 ★

6 项定量指标，对比 DSPy 与标准模式，结合 CI 门控自动决策。

### 6 项指标 (`lab_analysis/quant_metrics.py`)

| # | 指标 | 含义 | 合格阈值 |
|---|------|------|----------|
| 1 | `entity_f1` | DSPy 实体 vs 标准实体 F1 | ≥ 0.70 |
| 2 | `section_coverage` | 9 章节覆盖度 | ≥ 0.80 |
| 3 | `failure_rate` | 解析失败率（逆向） | is_failure = False |
| 4 | `entity_recall` | 标准实体被 DSPy 召回率 | ≥ 0.70 |
| 5 | `confidence` | DSPy 置信度校准 | ≥ 0.60 |
| 6 | `feedback_delta` | 用户反馈前后置信度 Δ | n_corrections ≥ 0 |
| 7 | `cross_modality_consistency` 🆕 | 影像-检验跨模态一致性 | ≥ 0.70 |

### 单次输出

```
data/<deid>/<ts>/04_reports/
├── quant_eval_report.json              # 完整 6 指标结果 + 跨模态 #7
├── quant_eval_report.png               # 柱状图（OK/FAIL 标签）
├── quant_eval_report.html              # 单文件可视化（暗色/响应式/可折叠）
├── quant_eval_gate_result.json         # 门控决策（PASS/FAIL）
└── .latest.txt                         # 最新 dspy_ts 指针

data/_all/trend/
└── quant_eval_trend.png                # 跨次趋势图（多患者）
```

### CI 门控

GitHub Actions 在 PR 时：所有 6 项指标均需通过阈值，否则合入被阻止。结果自动以 PR 评论发布（标记防刷）。

---

## MCP 服务（LLM Agent 集成）

`python mcp_server.py` 通过 stdio 向 Claude Desktop / Cursor 暴露 **6 个工具**：

| # | 工具 | 用途 | 关键参数 |
|---|------|------|----------|
| 1 | `audit_dspy_models` | 检查 4 个已编译 DSPy JSON 是否过时 | — |
| 2 | `run_quant_eval` | 运行 6 指标量化评估 + 门控 + 可视化 | `deid`, `ts` |
| 3 | `list_patients` | 列出所有患者及其统计信息 + std/dspy 配对 | — |
| 4 | `get_pipeline_status` | 按患者+时间戳检查流水线运行状态 | `patient_id`, `timestamp` |
| 5 | `trigger_dspy_recompile` | 增量/全量 DSPy 重新编译（子进程） | `force`, `timeout_sec` |
| 6 | `render_quant_trend` | 从量化报告链生成多 run 趋势图 | `patient_id`, `out_dir` |

Claude Desktop `claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "lab-analysis": {
      "command": "python",
      "args": ["/path/to/Lab-Analysis/mcp_server.py"]
    }
  }
}
```

---

## 项目结构

```
Lab-Analysis/
├── lab_analysis/                     # 核心包（76 模块，11.3k 行）
│   ├── pipeline/                     #   流水线编排
│   │   ├── cli.py                    #     CLI 参数解析
│   │   ├── steps.py                  #     步骤执行器
│   │   ├── ingest.py                 #     自动数据摄入
│   │   └── run.py                    #     主编排器
│   ├── analysis/                     #   统计分析子包
│   │   ├── _base.py                  #     常量、参考范围、图表
│   │   ├── _compute.py               #     纯计算（回归、稳健 Z-score、MAD）
│   │   ├── charts.py                 #     7 张统计图表
│   │   └── run.py                    #     编排器 + markdown 报告
│   ├── quant_metrics.py              # ★ 6 维度质量指标 + 门控
│   ├── quant_visualizer.py           # ★ PNG/HTML/趋势渲染
│   ├── alert_generator.py            #   结构化告警摘要
│   ├── scoring_card/                 #   决策支持（5 维 + 假设）
│   ├── compare_report_modes.py       #   标准 vs DSPy 对比
│   ├── evidence_grader.py            #   5 维文献证据分级
│   ├── patient_id.py                 #   AES-256-GCM 去标识（PHI 安全）
│   ├── error_logger.py               #   结构化错误日志（PHI 脱敏）
│   ├── _phi_filter.py                #   全局 PHI 日志过滤器
│   ├── fhir_exporter.py              #   HL7 FHIR R4 Bundle 导出
│   ├── feedback.py                   #   用户反馈闭环
│   ├── ingest_data/                  #   数据摄入
│   ├── extract_lab_data/             #   检验报告 OCR（SCNet + 正则解析）
│   ├── literature_searcher/          #   PubMed 检索（批量获取，自动查询词）
│   ├── dspy_modules/                 #   DSPy 优化模块
│   │   ├── literature_interpreter.py
│   │   ├── mri_analyzer.py
│   │   ├── final_report_generator.py
│   │   ├── lab_data_extractor.py
│   │   ├── prompt_inspector.py
│   │   └── _retry.py                 #     LLM 重试（指数退避）
│   └── _log.py                       #   日志基础设施（轮转、线程安全、PHI 清洗）
├── mcp_server.py                     # ★ MCP 服务（6 工具，stdio）
├── tests/                            # pytest（606 用例，37 文件）
│   ├── test_pipeline_e2e.py
│   ├── test_mcp_server.py            # ★ MCP 工具单元测试
│   ├── test_quant_metrics.py         # ★ 6 指标单元测试
│   ├── test_quant_visualizer.py      # ★ PNG/HTML 渲染测试
│   ├── test_quant_eval_gate.py       # ★ 门控决策测试
│   ├── test_dspy_modules.py
│   └── ...                           # 31 个更多测试文件
├── scripts/                          # CI/开发工具（18 脚本）
├── examples/                         # DSPy 演示与工具（18 示例）
├── docs/                             # 扩展文档
├── models/dspy/                      # 已编译 DSPy 模型
├── data/                             # 流水线输出（按患者 × 时间戳）
├── raw/                              # 原始数据
├── .github/workflows/tests.yml       # CI：测试 + 量化门控 + PR 评论
├── pyproject.toml                    # 配置：mypy strict，ruff S/T10/PTH，覆盖率 60%
└── mcp_server.py                     # MCP 服务入口
```

---

## 安装

### 环境要求

- **Python**: 3.10+
- **操作系统**: Windows 10/11、macOS、Linux
- **磁盘**: ≥ 5 GB（DICOM 缓存）

### 安装步骤

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .

# 可选依赖组
pip install "lab-analysis[dspy]"       # DSPy 模式
pip install "lab-analysis[pdf]"        # PDF 报告
pip install "lab-analysis[dashboard]"  # Streamlit 仪表盘
pip install "lab-analysis[mcp]"        # MCP 服务
pip install "lab-analysis[dev]"        # 开发工具（ruff、pytest、mypy）
```

### 环境变量

```bash
cp .env.example .env
```

| 变量 | 必需 | 用途 | 提供商 |
|------|------|------|--------|
| `WORK_ROOT` | 是 | 工作根目录（默认当前目录） | — |
| `DEEPSEEK_API_KEY` | 是 | 文献解读/报告生成的 LLM | DeepSeek |
| `DASHSCOPE_API_KEY` | 是 | Qwen-VL 影像分析 | 阿里云 |
| `SCNET_OCR_API_KEY` | 否 | 检验报告 OCR | SCNet |
| `LAB_DEID_KEY` | 否 | 去标识主密钥（自动生成） | — |
| `LOG_LEVEL` | 否 | 覆盖嘈杂日志级别（默认 WARNING） | — |

---

## 使用

### 一键运行

```bash
python -m lab_analysis                          # 标准模式（交互式输入 ID）
python -m lab_analysis --use-dspy               # DSPy 优化模式
```

### 跳过步骤

```bash
python -m lab_analysis --skip-ingest --skip-pdf --skip-cleanup
```

### 关键选项

```bash
--auto-queries                  # 自动生成 PubMed 检索词
--compare-report-modes          # 标准 vs DSPy 对比
--keep-last 5                   # 保留最近 5 次运行
--no-interactive                # 非交互模式（ID 不匹配则失败）
--skip-lit-filter               # 跳过文献过滤
--lit-filter-scenario <scenario> # early_diagnosis | differential_diagnosis | prognosis
```

### 调试单个步骤

```bash
python -m lab_analysis.data_loader    --id-card <deid>
python -m lab_analysis.scoring_card   --id-card <deid>
python -m lab_analysis.fhir_exporter  --id-card <deid>
python -m lab_analysis.cleanup_runs   --keep-last 3 --dry-run
```

步骤 ⑥⑦⑧ 需要 `ANALYSIS_TS` 环境变量：

```powershell
$env:ANALYSIS_TS="20260611_111343"
python -m lab_analysis.literature_interpreter --id-card <deid>
```

### 量化评估与趋势

```python
# 对特定 run 执行量化评估
python -c "from mcp_server import run_quant_eval; print(run_quant_eval('846552421134373347','20260620_175730'))"

# 多 run 趋势图
python -c "from mcp_server import render_quant_trend; print(render_quant_trend('846552421134373347'))"

# Streamlit 仪表盘
pip install "lab-analysis[dashboard]"
streamlit run lab_analysis/dashboard.py
```

---

## 输出产物

```
data/{patient_id}/{timestamp}/
├── lab_metrics{.csv,.json}               # 检验数据
├── analysis_results.json                 # 统计分析结果
├── alerts.json                           # 结构化告警
├── fig_01~fig_07.png                     # 7 张统计图表
├── analysis_results_report.md            # 分析报告
├── literature_results{.json,.filtered.json}  # PubMed + 证据分级
├── literature_interpretation.md          # 文献解读
├── mri_report_check_results.md           # 影像一致性
├── final_integrated_report{.md,.json}    # 综合报告（9 章节）
├── scoring_card{.json,.md}               # 评分卡 + top-3 假设
├── mode_comparison_report.md             # 标准/DSPy 对比
├── quant_eval_report{.json,.png,.html}   # ★ 6 指标量化评估
├── quant_eval_gate_result.json           # ★ 门控决策
├── .latest.txt                           # 最新 dspy_ts 指针
├── fhir_bundle.json                      # HL7 FHIR R4 Bundle
├── feedback.json                         # 用户反馈
└── dspy_prompts/                         # DSPy prompt 快照

data/_all/trend/
└── quant_eval_trend.png                  # ★ 跨次趋势图
```

---

## DSPy 增强

4 个 LLM 核心模块支持标准 + DSPy 双轨：

| 模块 | 标准模式 | DSPy 模式 |
|------|----------|-----------|
| 文献解读 | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` |
| MRI 分析 | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` |
| 综合报告 | `gen_final_report.py` | `dspy_modules/final_report_generator.py` |
| 检验数据提取 | `extract_lab_data/` | `dspy_modules/lab_data_extractor.py` |

详见 [docs/DSPY_INTEGRATION.md](docs/DSPY_INTEGRATION.md) 和 [docs/DSPY_USAGE.md](docs/DSPY_USAGE.md)。

### 重试与容错

所有 DSPy 模块使用 `safe_predict()`，3 次指数退避，捕获所有 LLM API 异常（OpenAI、LiteLLM、连接错误）。失败模块回退到 `make_empty_prediction()`，输出零初始化结果。

---

## 证据分级（步骤 ⑤b）

详见 [docs/EVIDENCE_GRADING.md](docs/EVIDENCE_GRADING.md)：

- 5 个维度：主题匹配 / 证据等级 / 时效性 / 样本量 / 解析质量
- 3 种场景权重：`early_diagnosis` / `differential_diagnosis` / `prognosis`
- S / A / B / C 等级评定
- 纯规则引擎，无 LLM，可复现

CLI：`--lit-filter-scenario <scenario> --lit-filter-top-k <N>`

---

## CI / CD

GitHub Actions `.github/workflows/tests.yml`：

| 任务 | 触发条件 | 内容 |
|------|----------|------|
| `test` | push / PR | pytest 矩阵（3.10~3.13）+ ruff + mypy |
| `quant_eval_gate` | push / PR | 6 指标量化评估 + 门控 + **自动 PR 评论** |

PR 评论示例：

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
| 数据处理 | pandas, numpy, scipy |
| 机器学习 | scikit-learn（MAD 稳健 Z-score） |
| 可视化 | matplotlib, Streamlit |
| 影像处理 | Pillow, pydicom |
| PDF | weasyprint, markdown（可选） |
| OCR | SCNet OCR API + 正则解析 |
| 视觉 | 阿里云 Qwen-VL |
| LLM | DeepSeek API（OpenAI 兼容） |
| LLM 优化 | DSPy 3.2+ (BootstrapFewShot / MIPROv2) |
| 文献检索 | PubMed E-utilities（批量 100/请求） |
| MCP | FastMCP（stdio 传输） |
| 安全 | AES-256-GCM 去标识，PHI 安全日志 |
| 错误处理 | tenacity 重试 + PHI 脱敏错误日志 |
| 测试 | pytest（606 用例，37 文件） |
| 代码检查 | ruff（S/T10/PTH 规则），mypy strict |
| 覆盖率 | ≥ 60%（pytest-cov） |
| CI | GitHub Actions |

---

## 开发

```bash
pip install -e ".[dev]"
python -m pytest                       # 606 测试
python -m pytest -v --cov              # 含覆盖率
ruff check lab_analysis/               # 代码检查
mypy lab_analysis/                     # 类型检查（严格模式）
```

### 代码规范

- PEP 8 + 类型注解（`from __future__ import annotations`）
- 所有路径使用 `pathlib.Path`
- `WORK_ROOT` 统一来自 `utils.py`
- 双轨脚本命名：`<module>.py` + `<module>_dspy.py`
- 日志统一使用 `_log.get_logger(__name__)`
- 异常处理：非关键路径使用 `_exceptions.py` 中的 `SAFE_EXCEPTIONS`

### 添加新模块

1. 在 `lab_analysis/` 下创建模块
2. 实现 `main_with_args(args)` 标准接口
3. 在 `pipeline/run.py` 中通过 `run_step()` 注册
4. 如涉及 LLM，同时实现 DSPy 版本 + `prompt_inspector` 集成

### 添加量化指标

1. 在 `lab_analysis/quant_metrics.py` 中添加函数 + `available=True` 回退
2. 在 `DEFAULT_THRESHOLDS` 中添加阈值
3. 在 `quant_visualizer.py` 的 `_extract_metric_value` 中添加分支
4. 在 `tests/test_quant_metrics.py` 和 `tests/test_quant_visualizer.py` 中添加单元测试
5. 更新 README 表格

---

## 文档

- [DSPy 集成](docs/DSPY_INTEGRATION.md)
- [DSPy 使用指南](docs/DSPY_USAGE.md)
- [证据分级](docs/EVIDENCE_GRADING.md)
- [MCP 集成](docs/MCP_INTEGRATION.md)

---

## 贡献

1. Fork 本项目
2. `git checkout -b feature/xxx`
3. `git commit -m 'feat: xxx'`
4. `git push origin feature/xxx`
5. 提交 PR

---

## 许可

MIT — 详见 [LICENSE](LICENSE)

---

## 作者

**nxz1026** — [GitHub @nxz1026](https://github.com/nxz1026)

---

## 致谢

- DeepSeek / SCNet / 阿里云（Qwen-VL）
- Stanford NLP [DSPy](https://dspy.ai/)
- PubMed E-utilities
- [FastMCP](https://github.com/jlowin/fastmcp) MCP 框架

---

⭐ 如果这个项目对你有帮助，请给一个 Star！
