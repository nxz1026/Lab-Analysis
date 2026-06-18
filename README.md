# Lab-Analysis

> 医学检验数据 + 文献循证 + 影像印证多源整合分析 Pipeline（集成 DSPy 提示词优化）

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/nxz1026/Lab-Analysis/actions/workflows/tests.yml/badge.svg)](https://github.com/nxz1026/Lab-Analysis/actions/workflows/tests.yml)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Pipeline](https://img.shields.io/badge/Pipeline-9_Steps-success.svg)](#-pipeline-完整流程)

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
| **一键自动化** | 9 步 Pipeline 一键运行，中间产物可追溯 |
| **可解释** | 7 张统计图表 + 完整日志 + 错误回溯 |
| **LLM 增强** | 集成 DSPy，自动优化提示词，支持标准 vs 优化双模式对比 |
| **跨平台** | Windows / Linux 自动适配，控制台编码自动修复 |
| **可扩展** | 模块化设计，新增分析维度只需实现标准接口 |

---

## Pipeline 完整流程

```bash
python -m lab_analysis
```

运行时强制交互输入身份证号，依次自动执行 9 个步骤。支持 `--skip-xxx` 跳过关键步骤。

| 步骤 | 环节 | 模块 | 输入 → 输出 |
|------|------|------|-------------|
| ① | **数据摄入** | `ingest_data.py` | `raw/Origin_data/` 中检验图片 / DICOM / MRI 报告 → `raw/patient_<deid>/` |
| ② | **前置检查** | `pipeline.steps` | `raw/patient_<deid>/` 目录结构校验 → 通过/失败 |
| ③ | **数据加载** | `data_loader.py` | `.../metrics.md` → `lab_metrics.csv` + `.json` |
| ④ | **统计分析** | `analysis/run` | `lab_metrics.csv` → 7 张图表 + `analysis_results_report.md` |
| ⑤ | **文献检索** | `literature_searcher.py` | 检验项目 + 关键指标 → PubMed 摘要 `.md` |
| ⑥ | **循证解读** | `literature_interpreter(_dspy).py` | 文献摘要 + 检验数据 → 解读报告 + DSPy prompt |
| ⑦ | **影像分析** | `qwen_vl_report_check(_dspy).py` | MRI 报告 + 检验数据 → 一致性报告 + DSPy prompt |
| ⑧ | **综合报告** | `gen_final_report(_dspy).py` | ④⑤⑥⑦ 产物 → 9 章节综合报告 + DSPy prompt |
| ⑨ | **本地归档** | `organize_local_files.py` | `data/<id>/<ts>/` → `local_upload/<YYYY-MM-DD>/` |

> 步骤 ⑥⑦⑧ 在 `--use-dspy` 时自动切换为 DSPy 优化模式，并保存优化后的 prompt 供对比。

### 流程图

```
[① 数据摄入] → [② 前置检查] → [③ 数据加载] → [④ 统计分析]
                                                    ↓
[⑨ 本地归档] ← [⑧ 综合报告] ← [⑦ 影像分析] ← [⑥ 循证解读] ← [⑤ 文献检索]
```

---

## 项目结构

```
Lab-Analysis/
├── lab_analysis/                         # 核心代码包
│   ├── __init__.py                       # 包入口（自动平台适配）
│   ├── __main__.py                       # python -m 入口
│   ├── pipeline.py                       # [过时]旧入口，委托给 pipeline/ 子包
│   ├── pipeline/                         # Pipeline 编排
│   │   ├── cli.py                        #   命令行解析
│   │   ├── steps.py                      #   子步骤（检查/子进程/日志）
│   │   ├── ingest.py                     #   自动数据摄入
│   │   └── run.py                        #   main 编排器
│   ├── analysis/                         # 统计分析子包
│   │   ├── _base.py                      #   常量 / 参考范围 / 绘图工具
│   │   ├── _compute.py                   #   纯计算函数（回归/分类/异常检测）
│   │   ├── charts.py                     #   7 张统计图表
│   │   └── run.py                        #   编排器 + Markdown 报告生成
│   ├── ingest_data.py                    # ① 数据摄入实现
│   ├── data_loader.py                    # ③ 数据加载
│   ├── data_analyzer.py                  # [过时]委托给 analysis/ 子包
│   ├── literature_searcher.py            # ⑤ PubMed 文献检索
│   ├── literature_interpreter.py         # ⑥ 文献解读（标准）
│   ├── literature_interpreter_dspy.py    # ⑥ 文献解读（DSPy 双模式）
│   ├── qwen_vl_report_check.py           # ⑦ 影像检查（标准）
│   ├── qwen_vl_report_check_dspy.py      # ⑦ 影像检查（DSPy 双模式）
│   ├── gen_final_report.py               # ⑧ 报告生成（标准）
│   ├── gen_final_report_dspy.py          # ⑧ 报告生成（DSPy 双模式）
│   ├── extract_lab_data.py               # 检验报告 OCR 提取
│   ├── vision_extractor.py               # 单图 Vision AI 提取
│   ├── batch_vision_extract.py           # 批量视觉提取
│   ├── llm_client.py                     # 统一 LLM API 客户端（DeepSeek / 智谱 / DashScope）
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
├── tests/                                # pytest 测试套件
│   ├── conftest.py                       #   测试配置（环境变量 / 夹具）
│   ├── test_utils.py                     #   工具函数测试
│   ├── test_patient_id.py                #   身份证脱敏/校验测试
│   └── test_extract_lab_data.py          #   检验数据提取测试
├── examples/                             # 示例与工具
│   ├── dspy_quickstart.py
│   ├── dspy_prompt_comparison.py         #   Prompt 对比报告生成
│   ├── compile_dspy_module.py            #   DSPy 模块编译
│   ├── test_dspy_e2e.py                  #   DSPy 端到端测试
│   ├── test_dspy_prompt_e2e.py           #   Prompt 保存/对比验证
│   └── ...
├── docs/                                 # 补充文档
│   ├── DSPY_INTEGRATION.md               #   DSPy 集成技术方案
│   └── DSPY_USAGE.md                     #   DSPy 使用指南
├── models/dspy/                          # 编译后 DSPy 模型
├── raw/                                  # 原始数据
│   └── Origin_data/                      #   待处理文件（lab_*.jpg / mri_*.jpg / export_*.zip）
├── data/                                 # 分析结果（按患者+时间戳组织）
├── local_upload/                         # 本地归档（按日期）
├── .github/workflows/                    # CI 配置
│   ├── tests.yml                         #   矩阵测试（py3.10~3.12）
│   └── ci.yml                            #   快速导入检查
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
pip install "dspy-ai>=3.2" python-dotenv   # DSPy 模式可选
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
| `ZHIPU_API_KEY` | 否 | 检验报告 OCR（GLM-4V） | 智谱 AI |
| `FEISHU_FOLDER_TOKEN` | 否 | 飞书云盘上传（实验性） | 飞书开放平台 |

---

## 运行指南

### 一键运行完整 Pipeline

```bash
# 标准模式 — 交互输入身份证号
python -m lab_analysis

# DSPy 优化模式
python -m lab_analysis --use-dspy
```

### 跳过指定步骤

```bash
python -m lab_analysis --skip-ingest   # 跳过数据摄入
python -m lab_analysis --skip-llm      # 跳过文献解读
python -m lab_analysis --skip-imaging  # 跳过影像分析
```

### 单独调试某一步骤

```bash
python -m lab_analysis.data_loader --id-card <脱敏ID>
python -m lab_analysis.data_analyzer --id-card <脱敏ID>
python -m lab_analysis.literature_interpreter_dspy --id-card <脱敏ID> --use-dspy
```

单独运行步骤 ⑥⑦⑧ 时需要设置 `ANALYSIS_TS` 环境变量指向已有时间戳目录：

```powershell
$env:ANALYSIS_TS="20260611_111343"
python -m lab_analysis.literature_interpreter_dspy --id-card <脱敏ID> --use-dspy
```

---

## 输出产物

```
data/{patient_id}/{timestamp}/
├── lab_metrics.csv                       # 检验数据（CSV，分析输入）
├── lab_metrics.json                      # 检验数据（JSON，含脱敏）
├── fig_01_trend_regression.png           # 趋势回归
├── fig_02_correlation_heatmap.png        # 相关性热图
├── fig_03_inflammation_status.png        # 炎症分期
├── fig_04_abnormal_indicators.png        # 异常指标标注
├── fig_05_moving_average.png             # 移动平均
├── fig_06_cv_stability.png              # CV 稳定性热力
├── fig_07_zscore_distribution.png        # Z-score 分布
├── analysis_results_report.md            # 统计分析报告
├── literature_results.md                 # PubMed 检索结果
├── literature_interpretation.md          # 文献解读
├── mri_report_check_results.md           # 影像一致性报告
├── final_integrated_report.md            # 最终综合报告
├── reports/dspy_prompt_comparison.{md,json}  # Prompt 对比报告
└── dspy_prompts/                         # DSPy prompt 快照
    ├── *_standard_prompt.txt
    ├── *_dspy_actual_prompt.txt
    └── *_dspy_prompts.{json,md}
```

---

## LS 增强特性

本项目集成 **DSPy**（Declarative Self-improving Python）框架，在 4 个 LLM 核心模块上实现"标准模式 + DSPy 优化模式"双轨运行。

### 4 个 DSPy 模块

| 模块 | 职责 | 标准版 | DSPy 版 |
|------|------|--------|---------|
| `literature_interpreter` | 文献循证解读 | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` |
| `mri_analyzer` | 影像报告分析 | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` |
| `final_report_generator` | 综合报告生成 | `gen_final_report.py` | `dspy_modules/final_report_generator.py` |
| `lab_data_extractor` | 检验数据提取 | `extract_lab_data.py` | `dspy_modules/lab_data_extractor.py` |

### Prompt 自动提取与对比

每次推理后，DSPy 模块自动调用 `prompt_inspector` 保存标准 prompt 与 DSPy 实际 prompt（含 ChainOfThought 格式 + few-shot 示例），两文件并排保存便于 diff。

生成对比报告：

```bash
python examples/dspy_prompt_comparison.py --data-dir data/<deid>/<ts>
```

---

## 技术栈

| 领域 | 选型 |
|------|------|
| 数据处理 | pandas, numpy, scipy |
| 机器学习 | scikit-learn |
| 可视化 | matplotlib |
| 图像处理 | Pillow, pydicom |
| OCR / Vision | 智谱 GLM-4V, 阿里云 Qwen-VL |
| 文本生成 | DeepSeek API, OpenAI 兼容协议 |
| LLM 优化 | DSPy 3.2+（BootstrapFewShot / MIPROv2） |
| 文献检索 | PubMed E-utilities API |
| 错误处理 | tenacity（重试）+ 自研 error_logger |
| 测试 | pytest, pytest-cov |
| CI | GitHub Actions（Python 3.10~3.12 矩阵）|

---

## 开发指南

### 测试

```bash
pip install -e ".[dev]"
python -m pytest                # 运行全部测试
python -m pytest -v --cov       # 带覆盖率
ruff check lab_analysis/        # 代码风格检查
```

### 代码规范

- PEP 8 + 类型注解
- 路径统一使用 `pathlib.Path`
- 优先 `WORK_ROOT` + 相对路径
- 双模式脚本命名 `<module>_dspy.py`
- 平台适配：使用 `utils.is_windows()` 判断操作系统，`utils.fix_console_encoding()` 自动修复控制台编码

### 添加新模块

1. 在 `lab_analysis/` 创建模块
2. 实现 `main_with_args(args)` 标准接口
3. 在 `pipeline/run.py` 中用 `run_step()` 注册
4. 若涉及 LLM，同步实现 DSPy 版本与 `prompt_inspector` 集成

### 依赖管理

```bash
pip install -e .                              # 安装
pip install pip-tools                         # 可选：生成锁定文件
pip-compile pyproject.toml -o requirements.lock
```

所有依赖在 `pyproject.toml` 中声明，请勿手动创建 `requirements.txt`。

---

## 进阶文档

- [DSPy 集成技术方案](docs/DSPY_INTEGRATION.md)
- [DSPy 使用指南](docs/DSPY_USAGE.md)
- [examples/dspy_quickstart.py](examples/dspy_quickstart.py)

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

- DeepSeek、智谱 AI、阿里云百炼（Qwen-VL）提供的 LLM 能力
- Stanford NLP 的 [DSPy](https://dspy.ai/) 框架
- PubMed E-utilities 开放接口

---

⭐ 如果这个项目对您有帮助，请给个 Star！
