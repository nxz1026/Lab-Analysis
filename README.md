# Lab-Analysis

> 医学检验数据 + 文献循证 + 影像印证多源整合分析 Pipeline（集成 DSPy 提示词优化）

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/nxz1026/Lab-Analysis/actions/workflows/tests.yml/badge.svg)](https://github.com/nxz1026/Lab-Analysis/actions/workflows/tests.yml)
[![Quant Gate](https://github.com/nxz1026/Lab-Analysis/actions/workflows/quant_eval_gate.yml/badge.svg)](https://github.com/nxz1026/Lab-Analysis/actions/workflows/quant_eval_gate.yml)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Tests](https://img.shields.io/badge/Tests-427_✔️-success.svg)](tests/)
[![Pipeline](https://img.shields.io/badge/Pipeline-11_Steps-success.svg)](#pipeline-完整流程)
[![MCP](https://img.shields.io/badge/MCP-5_Tools-purple.svg)](mcp_server.py)

---

## 概览

**Lab-Analysis** 是面向**慢性胰腺炎等慢性病**的多源数据整合分析工具，完整覆盖 _检验数据 → 趋势分析 → 文献循证 → 影像印证 → 综合报告_ 的临床路径。一次摄入，自动产出结构化临床分析报告。

### 适用场景

- **临床研究**：长期检验数据趋势分析、炎症分期演变
- **个案会诊**：检验 + 文献 + 影像三源数据交叉印证
- **教学复盘**：文献循证与临床数据的可解释关联
- **LLM 应用研究**：医学 LLM 的 Prompt 工程与对比评测

### 核心特性

| 维度 | 说明 |
|------|------|
| **多源整合** | 检验数据（CSV/JSON）+ PubMed 文献 + MRI/DICOM 影像 + 文字报告，三源一致性评估 |
| **一键自动化** | 10+ 步 Pipeline 一键运行，中间产物可追溯 |
| **可解释** | 7 张统计图表 + 结构化告警摘要 + 完整日志 |
| **LLM 增强** | 集成 DSPy，支持 Standard / DSPy 双模式自动对比 |
| **决策支持** | 5 维评分卡 + 加权诊断假设（纯规则引擎，不调 LLM） |
| **跨平台** | Windows / Linux 自动适配，控制台编码自动修复 |
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
| ⑤ | **文献检索** | `literature_searcher.py` | 检验项目 + 关键指标 → PubMed 摘要 `.md`（支持 `--auto-queries` 自动生成搜索词） |
| ⑤b | **文献证据打分**（可选） | `literature_filter.py` | `literature_results.json` → `.filtered.json`（按证据等级排序 top-k） |
| ⑥ | **循证解读** | `literature_interpreter(_dspy).py` | 文献摘要 + 检验数据 → 解读报告 + DSPy prompt |
| ⑦ | **影像分析** | `qwen_vl_report_check(_dspy).py` | MRI 报告 + 检验数据 → 一致性报告 + DSPy prompt |
| ⑧ | **综合报告** | `gen_final_report(_dspy).py` | ④⑤⑥⑦ 产物 → 9 章节综合报告（支持 `--compare-mode` 双模式对比） |
| ⑧b | **评分卡 & 决策支持**（可选新增） | `scoring_card.py` | 多源数据 → 5 维评分 + top-3 诊断假设 |
| ⑨ | **本地归档** | `organize_local_files.py` | `data/<id>/<ts>/` → `local_upload/<YYYY-MM-DD>/` |
| ⑨b | **FHIR 输出**（可选新增） | `fhir_exporter.py` | 多源数据 → HL7 FHIR R4 Bundle（Patient/Observation/RiskAssessment） |
| ⑩ | **旧产物清理**（可选新增） | `cleanup_runs.py` | 自动删除旧批次，保留最近 N 次（`--keep-last 3`） |

> 步骤 ⑥⑦⑧ 在 `--use-dspy` 时自动切换为 DSPy 优化模式，并保存优化后的 prompt 供对比。

### 流程图

```
[① 数据摄入] → [② 前置检查] → [③ 数据加载] → [④ 统计分析]
                                                    ↓
[⑩ 产物清理] ← [⑨ 本地归档] ← [⑧b 评分卡] ← [⑧ 综合报告] ← [⑦ 影像分析] ← [⑥ 循证解读] ← [⑤ 文献检索]
```

---

## 项目结构

```
Lab-Analysis/
├── lab_analysis/                         # 核心代码包
│   ├── __init__.py                       #   包入口（自动平台适配）
│   ├── __main__.py                       #   python -m 入口
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
│   ├── alert_generator.py                #   结构化异常告警摘要（CRITICAL/WARNING/INFO）
│   ├── scoring_card.py                   #   评分卡 & 临床决策支持（5 维评分 + 诊断假设）
│   ├── compare_report_modes.py           #   Standard vs DSPy 双模式报告对比
│   ├── gen_final_report_pdf.py           #   Markdown → PDF 转换（可选依赖）
│   ├── dashboard.py                      #   Streamlit 趋势看板（可选依赖）
│   ├── cleanup_runs.py                   #   Pipeline 产物清理工具
│   ├── report_schema.py                  #   综合报告 9 章节定义与 MD 模板（共享）
│   ├── ingest_data.py                    # ① 数据摄入实现
│   ├── data_loader.py                    # ③ 数据加载
│   ├── literature_searcher.py            # ⑤ PubMed 文献检索（支持 --auto-queries）
│   ├── evidence_grader.py                # ⑤b 论文证据等级打分（5 维 + 3 scenario）
│   ├── literature_filter.py              # ⑤b CLI 封装（pipeline 步骤入口）
│   ├── literature_interpreter.py         # ⑥ 文献解读（标准）
│   ├── literature_interpreter_dspy.py    # ⑥ 文献解读（DSPy 双模式）
│   ├── qwen_vl_report_check.py           # ⑦ 影像检查（标准）
│   ├── qwen_vl_report_check_dspy.py      # ⑦ 影像检查（DSPy 双模式）
│   ├── gen_final_report.py               # ⑧ 报告生成（标准，支持 --compare-mode）
│   ├── gen_final_report_dspy.py          # ⑧ 报告生成（DSPy 双模式）
│   ├── extract_lab_data.py               # 检验报告 OCR 提取
│   ├── vision_extractor.py               # 单图 Vision AI 提取
│   ├── batch_vision_extract.py           # 批量视觉提取
│   ├── llm_client.py                     # 统一 LLM API 客户端（DeepSeek / DashScope）
│   ├── patient_id.py                     # AES-GCM 身份证脱敏与校验
│   ├── error_logger.py                   # 错误日志
│   ├── utils.py                          # 通用工具（平台适配 / 路径 / JSON 解析）
│   ├── organize_local_files.py           # ⑨ 本地归档
│   ├── upload_to_feishu_backup.py        # 飞书备份（实验性）
│   └── dspy_modules/                     # DSPy 优化模块
│       ├── __init__.py
│       ├── literature_interpreter.py     #   DSPy 文献解读
│       ├── mri_analyzer.py               #   DSPy 影像分析
│       ├── final_report_generator.py     #   DSPy 报告生成
│       ├── lab_data_extractor.py         #   DSPy 检验数据提取
│       └── prompt_inspector.py           #   DSPy prompt 提取工具
├── tests/                                # pytest 测试套件（427 用例）
│   ├── conftest.py                       #   测试配置（环境变量 / 夹具）
│   ├── test_utils.py                     #   工具函数测试
│   ├── test_patient_id.py                #   身份证脱敏/校验测试
│   ├── test_evidence_grader.py           #   证据打分测试
│   ├── test_extract_lab_data.py          #   检验数据提取测试
│   ├── test_alert_generator.py           #   告警摘要测试（新增）
│   ├── test_compare_modes.py             #   双模式对比测试（新增）
│   ├── test_dspy_modules.py              #   DSPy 模块测试（新增）
│   ├── test_cleanup_runs.py              #   产物清理测试（新增）
│   └── test_scoring_card.py              #   评分卡测试（新增）
├── scripts/                              # 调试/对比脚本
│   ├── grading_demo.py
│   └── st_vs_grader_compare.py
├── examples/                             # 示例与工具
├── docs/                                 # 补充文档
│   ├── DSPY_INTEGRATION.md               #   DSPy 集成技术方案
│   ├── DSPY_USAGE.md                     #   DSPy 使用指南
│   └── EVIDENCE_GRADING.md               #   证据打分说明
├── models/dspy/                          # 编译后 DSPy 模型
├── raw/                                  # 原始数据
│   └── Origin_data/                      #   待处理文件
├── data/                                 # 分析结果（按患者+时间戳组织）
├── local_upload/                         # 本地归档（按日期）
├── .github/workflows/                    # CI 配置
├── .editorconfig                         # 编辑器配置
├── .env.example                          # 环境变量示例
├── pyproject.toml                        # 项目配置与依赖
└── run_analysis.py                       # 便捷启动脚本
```

---

## 安装与配置

### 环境要求

- **Python**: 3.10+
- **操作系统**: Windows 10/11、macOS、Linux
- **磁盘**: ≥ 5 GB（含 DICOM 解压缓存）

### 安装

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .

# 可选依赖组
pip install "lab-analysis[dspy]"    # DSPy 模式（dspy-ai, pydicom）
pip install "lab-analysis[pdf]"     # PDF 报告输出（weasyprint, markdown）
pip install "lab-analysis[dashboard]" # Streamlit 趋势看板
pip install "lab-analysis[dev]"     # 开发工具（ruff, pytest）
```

### 配置环境变量

```bash
cp .env.example .env
```

| 变量 | 必填 | 用途 | 提供方 |
|------|------|------|--------|
| `WORK_ROOT` | 是 | 项目工作根目录（默认当前目录） | — |
| `DEEPSEEK_API_KEY` | 是 | 文献解读 / 报告生成 | DeepSeek |
| `DASHSCOPE_API_KEY` | 是 | 影像分析（Qwen-VL） | 阿里云百炼 |
| `SCNET_OCR_API_KEY` | 否 | 检验报告图片 OCR 文字提取 | SCNet |
| `FEISHU_FOLDER_TOKEN` | 否 | 飞书云盘上传（实验性） | 飞书开放平台 |

---

## 运行指南

### 一键运行 Pipeline

```bash
# 标准模式 — 交互输入身份证号
python -m lab_analysis

# DSPy 优化模式
python -m lab_analysis --use-dspy
```

### 跳过指定步骤

```bash
python -m lab_analysis --skip-ingest           # 跳过数据摄入
python -m lab_analysis --skip-llm              # 跳过文献解读
python -m lab_analysis --skip-imaging          # 跳过影像分析
python -m lab_analysis --skip-lit-filter       # 跳过文献证据打分
python -m lab_analysis --skip-scoring          # 跳过评分卡
python -m lab_analysis --skip-pdf              # 跳过 PDF 生成
python -m lab_analysis --skip-cleanup          # 跳过旧产物清理
```

### 新增功能

**文献搜索词自动生成**（基于异常指标）：
```bash
python -m lab_analysis --auto-queries
```

**Standard / DSPy 双模式对比**：
```bash
python -m lab_analysis --compare-report-modes
```

**产物清理**（保留最近 5 次）：
```bash
python -m lab_analysis --keep-last 5
```

**Streamlit 趋势看板**（独立运行）：
```bash
pip install "lab-analysis[dashboard]"
streamlit run lab_analysis/dashboard.py
```

### 单独调试某一步骤

```bash
python -m lab_analysis.data_loader --id-card <脱敏ID>
python -m lab_analysis.scoring_card --id-card <脱敏ID>
python -m lab_analysis.cleanup_runs --keep-last 3 --dry-run
```

单独运行步骤 ⑥⑦⑧ 时需要设置 `ANALYSIS_TS` 环境变量指向已有时间戳目录：

```powershell
$env:ANALYSIS_TS="20260611_111343"
python -m lab_analysis.literature_interpreter --id-card <脱敏ID>
```

---

## 输出产物

```
data/{patient_id}/{timestamp}/
├── lab_metrics.csv                       # 检验数据（CSV，分析输入）
├── lab_metrics.json                      # 检验数据（JSON，含脱敏）
├── analysis_results.json                 # 统计分析完整结果（含 predictions 预测字段）
├── alerts.json                           # 结构化异常告警摘要（新增）
├── fig_01~fig_07.png                     # 7 张统计图表
├── analysis_results_report.md            # 统计分析报告
├── literature_results.json               # PubMed 检索结果
├── literature_results.filtered.json      # 文献证据打分结果
├── literature_interpretation.md          # 文献解读
├── mri_report_check_results.md           # 影像一致性报告
├── final_integrated_report.md            # 最终综合报告
├── final_integrated_report.pdf           # PDF 报告（可选，新增）
├── scoring_card.json                     # 评分卡 & 诊断假设（新增）
├── scoring_card.md                       # 评分卡可读版（新增）
├── mode_comparison_report.md             # Standard/DSPy 对比（新增）
├── mode_comparison.json                  # 对比数据（新增）
├── fhir_bundle.json                      # HL7 FHIR R4 Bundle（新增）
├── reports/dspy_prompt_comparison.{md,json}  # Prompt 对比报告
└── dspy_prompts/                         # DSPy prompt 快照
```

---

## 新增功能详述

### 结构化异常告警摘要

Pipeline 步骤④ 自动生成，分析 results 后立即输出 `alerts.json`：

| 级别 | 触发条件 |
|------|---------|
| 🚨 CRITICAL | hs-CRP 急性期 / 严重 Z-score 异常 / 同一指标 ≥3 次超参考范围 |
| ⚠️ WARNING | 超参考范围 / 高变异（CV>0.2）/ 显著上升趋势 |
| ℹ️ INFO | 轻度 Z-score 异常 / 下降趋势 |

### 评分卡 & 临床决策支持（步骤⑧b）

纯规则引擎，不调 LLM，可重复可测试。5 维评分（0-100） + 加权诊断假设：

| 维度 | 数据源 | 含义 |
|------|--------|------|
| `inflammation` | hs-CRP 分期 + 趋势 | 评分高 → 炎症活跃 |
| `lab_abnormality` | 异常指标 + Z-score | 评分高 → 异常显著 |
| `literature_support` | 证据打分结果 | 评分高 → 文献证据充分 |
| `imaging_consistency` | MRI 一致性报告 | 评分高 → 影像与检验一致 |
| `variability_stability` | CV 稳定性 | 评分高 → 指标稳定 |

### PubMed 搜索词自动生成

```bash
python -m lab_analysis --auto-queries
# 或单独使用:
python -m lab_analysis.literature_searcher --id-card <deid> --auto-queries
```

根据 `analysis_results.json` 中的异常指标自动生成搜索策略。例如：
- hs-CRP↑ → `"chronic pancreatitis" AND ("hs-CRP" OR "high-sensitivity CRP")`
- 急性期 → `"acute pancreatitis" biomarker PCT CRP severity`

### Standard / DSPy 双模式对比

```bash
python -m lab_analysis.gen_final_report --id-card <deid> --compare-mode
```

同时运行 Standard API 和 DSPy 模块生成报告，按 9 章节逐段对比：字符数、内容重叠率、关键实体提及差异，输出对比报告到 `04_reports/mode_comparison_report.md`。

### PDF 报告输出

```bash
pip install "lab-analysis[pdf]"
python -m lab_analysis.gen_final_report_pdf \
    --md data/<deid>/<ts>/04_reports/final_integrated_report.md \
    --img-dir data/<deid>/<ts>/02_analyzed/figures \
    --out data/<deid>/<ts>/04_reports/final_integrated_report.pdf
```

Pipeline 中默认开启（安装依赖后），`--skip-pdf` 跳过。CJK 中文排版。

### Streamlit 趋势看板

```bash
pip install "lab-analysis[dashboard]"
streamlit run lab_analysis/dashboard.py
```

4 个 Tab：概览（炎症 timeline + 告警） / 7 张图表 / 检验数据表 / 最终报告。侧边栏选择患者和运行批次。

### 产物清理

```bash
# 保留最近 3 次，删除其余
python -m lab_analysis.cleanup_runs --keep-last 3

# 预览不动手
python -m lab_analysis.cleanup_runs --keep-last 5 --dry-run

# 只清理某个患者
python -m lab_analysis.cleanup_runs --keep-last 2 --id-card <deid>
```

Pipeline 步骤⑩ 默认启用（保留最近 3 次），`--skip-cleanup` 跳过。

---

### 检验指标预测

Pipeline 步骤④ 自动执行，基于已有时间序列用线性回归 + 95% 置信区间预测下次就诊指标值。

```
   hs-CRP: 下次预测=14.300  95%CI=[11.200, 17.400]  上升 ⚠️ 预测值超过阈值 3.0
```

预测结果写入 `analysis_results.json` 的 `predictions` 字段，同时打印到控制台。

### FHIR 输出（步骤⑨b）

将多源分析结果映射为 HL7 FHIR R4 Bundle：

| FHIR 资源 | 源数据 |
|-----------|--------|
| `Patient` | 脱敏患者 ID |
| `Observation` | 各检验指标（含 LOINC 编码）+ 参考范围 + 异常标记 |
| `Observation` | 炎症分期 |
| `Observation` | 告警摘要（CRITICAL/WARNING 级别） |
| `RiskAssessment` | 评分卡 top-3 诊断假设 |
| `DiagnosticReport` | 综合报告结论 + Markdown 全文 |

```bash
# Pipeline 中默认启用
python -m lab_analysis --skip-fhir   # 跳过

# 单独运行
python -m lab_analysis.fhir_exporter --id-card <deid>
```

输出到 `04_reports/fhir_bundle.json`，可直接对接 FHIR R4 兼容的医疗信息系统。

### 交互式反馈回路

记录用户对评分卡诊断假设的纠正，自动调整后续评分置信度。

```bash
# 查看当前反馈
python -m lab_analysis.feedback --id-card <deid> --show

# 记录纠正
python -m lab_analysis.feedback --id-card <deid> --correct \
  --original "慢性胰腺炎（活动期）" --corrected "急性胰腺炎" \
  --confidence 0.90 --comment "临床确诊"

# 清除反馈
python -m lab_analysis.feedback --id-card <deid> --clear
```

反馈数据保存在 `data/<deid>/feedback.json`，下次 pipeline 运行时自动加载并调整评分卡置信度。

---

## 证据打分（步骤⑤b）

参见 [docs/EVIDENCE_GRADING.md](docs/EVIDENCE_GRADING.md)。

简要：
- 5 个独立维度打分（主题匹配 / 证据等级 / 时效性 / 样本量 / 解析质量）
- 3 种场景权重：`early_diagnosis` / `differential_diagnosis` / `prognosis`
- S/A/B/C 四档 tier
- 纯规则打分，不调 LLM，可重复可测试

CLI 参数：
```
--skip-lit-filter              跳过步骤⑤b
--lit-filter-scenario {early_diagnosis|differential_diagnosis|prognosis}
                              默认 differential_diagnosis
--lit-filter-top-k INT         保留前 k 篇，默认 8
```

---

## DSPy 增强特性

本项目集成 **DSPy** 框架，在 4 个 LLM 核心模块上实现 Standard + DSPy 双轨运行。

| 模块 | 职责 | 标准版 | DSPy 版 |
|------|------|--------|---------|
| `literature_interpreter` | 文献循证解读 | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` |
| `mri_analyzer` | 影像报告分析 | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` |
| `final_report_generator` | 综合报告生成 | `gen_final_report.py` | `dspy_modules/final_report_generator.py` |
| `lab_data_extractor` | 检验数据提取 | `extract_lab_data.py` | `dspy_modules/lab_data_extractor.py` |

---

## 技术栈

| 领域 | 选型 |
|------|------|
| 数据处理 | pandas, numpy, scipy |
| 机器学习 | scikit-learn |
| 可视化 | matplotlib, Streamlit（看板） |
| 图像处理 | Pillow, pydicom |
| PDF | weasyprint, markdown（可选） |
| OCR / Vision | SCNet OCR, 阿里云 Qwen-VL |
| 文本生成 | DeepSeek API, OpenAI 兼容协议 |
| LLM 优化 | DSPy 3.2+（BootstrapFewShot / MIPROv2） |
| 文献检索 | PubMed E-utilities API |
| 错误处理 | tenacity（重试）+ 自研 error_logger |
| 测试 | pytest, pytest-cov（427 用例） |
| CI | GitHub Actions（Python 3.10~3.13 矩阵 + quant_eval_gate PR 必跑）|

---

## 开发指南

### 测试

```bash
pip install -e ".[dev]"
python -m pytest                # 运行全部测试（166 个）
python -m pytest -v --cov       # 带覆盖率
ruff check lab_analysis/        # 代码风格检查
```

### 代码规范

- PEP 8 + 类型注解
- 路径统一使用 `pathlib.Path`
- 优先 `WORK_ROOT` + 相对路径
- 双模式脚本命名 `<module>_dspy.py`
- 平台适配：使用 `utils.is_windows()` 判断操作系统

### 添加新模块

1. 在 `lab_analysis/` 创建模块
2. 实现 `main_with_args(args)` 标准接口
3. 在 `pipeline/run.py` 中用 `run_step()` 注册
4. 若涉及 LLM，同步实现 DSPy 版本与 `prompt_inspector` 集成

---

## 进阶文档

- [DSPy 集成技术方案](docs/DSPY_INTEGRATION.md)
- [DSPy 使用指南](docs/DSPY_USAGE.md)
- [证据打分说明](docs/EVIDENCE_GRADING.md)

---

## 贡献

欢迎 Issue 与 PR！

1. Fork 仓库
2. 创建特性分支（`git checkout -b feature/xxx`）
3. 提交更改（`git commit -m 'feat: add xxx'`）
4. 推送（`git push origin feature/xxx`）
5. 发起 Pull Request

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

## 作者

**nxz1026** — [GitHub @nxz1026](https://github.com/nxz1026)

---

## 致谢

- DeepSeek、SCNet、阿里云百炼（Qwen-VL）提供的 LLM 与 OCR 能力
- Stanford NLP 的 [DSPy](https://dspy.ai/) 框架
- PubMed E-utilities 开放接口

---

⭐ 如果这个项目对您有帮助，请给个 Star！
