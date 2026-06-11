# Lab-Analysis

> 医学检验数据 + 文献循证 + 影像印证多源整合分析 Pipeline(集成 DSPy 提示词优化)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Pipeline](https://img.shields.io/badge/Pipeline-9_Steps-success.svg)](#-pipeline-完整流程)

---

## 📋 项目概述

**Lab-Analysis** 是一个面向**慢性胰腺炎等慢性病临床数据分析**的多源整合工具,围绕 *检验数据 → 趋势分析 → 文献循证 → 影像印证 → 综合报告* 的完整临床路径,实现"一次摄入,自动产出结构化临床分析报告"。

### 适用场景

- 🏥 **临床研究**: 慢性胰腺炎、肿瘤标志物等长期检验数据趋势分析
- 🧪 **个案会诊**: 多源数据(检验 + 文献 + 影像)交叉印证
- 📚 **教学/复盘**: 文献循证与临床数据的可解释关联
- 🤖 **LLM 应用研究**: 医学 LLM 的 Prompt 工程与对比评测

### 核心价值

| 维度 | 价值 |
|------|------|
| **多源整合** | 检验数据(CSV/JSON)+ PubMed 文献 + MRI/DICOM 影像 + 文字报告,三源一致性评估 |
| **自动化** | 9 步 Pipeline 一键运行,中间产物可追溯 |
| **可解释** | 7 张统计图表 + 完整日志 + 错误回溯 |
| **LLM 增强** | 集成 DSPy,自动优化提示词,支持标准 vs 优化双模式对比 |
| **可扩展** | 模块化设计,新增分析维度只需实现标准接口 |

---

## ✨ 核心功能

### 1. 数据摄入(检验 + 影像 + 文献预处理)
- 检验报告图片 OCR 识别(智谱 GLM-4V)
- DICOM 影像解压、序列重命名
- MRI 文字报告解析
- 患者 ID 自动脱敏

### 2. 统计分析(7 张图表)
- 趋势回归、相关性热图
- 炎症评估、异常检测
- 移动平均、变异系数、综合仪表板

### 3. 文献检索与循证解读
- PubMed 自动检索(支持 MeSH + 自由词组合)
- DeepSeek AI 循证解读
- 🧠 **DSPy 优化**: 病理生理层级结构化分析,内置置信度评分

### 4. 影像报告检查
- Qwen-VL 模型验证 MRI 报告
- 影像所见与检验数据一致性比对
- 🧠 **DSPy 优化**: 结构化提取影像征象

### 5. 综合报告生成
- 三源一致性评估(检验 / 文献 / 影像)
- 9 章节结构化临床诊断报告
- 🧠 **DSPy 优化**: 自动组织章节、补充鉴别诊断

### 6. 本地归档与上传备份
- 按日期组织的本地归档
- 飞书云盘自动上传(实验性,见 `lark-cli` 集成)

---

## 🧠 DSPy 增强特性

本项目集成 **DSPy** (Declarative Self-improving Python) 框架,在 4 个 LLM 驱动的核心模块上实现"标准模式 + DSPy 优化模式"双轨运行,既保证稳定生产,又支持 LLM 提示词的自动化迭代。

### 4 个 DSPy 模块

| 模块 | 职责 | 标准版 | DSPy 版 | 保存路径 |
|------|------|--------|---------|----------|
| `literature_interpreter` | 文献循证解读 | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` | `data/<id>/<ts>/03_literature/dspy_prompts/` |
| `mri_analyzer` | 影像报告分析 | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` | `data/<id>/<ts>/dspy_prompts/` |
| `final_report_generator` | 综合报告生成 | `gen_final_report.py` | `dspy_modules/final_report_generator.py` | `data/<id>/<ts>/04_reports/dspy_prompts/` |
| `lab_data_extractor` | 检验数据提取 | `extract_lab_data.py` | `dspy_modules/lab_data_extractor.py` | `data/<id>/<ts>/dspy_prompts/` |

### 双模式运行

每个双模式脚本(如 `literature_interpreter_dspy.py`)均支持:
- **标准模式**: 手工编写的 prompt 模板 + 一次性调用 LLM
- **DSPy 模式**: 加载已编译模块(若存在)/ 动态生成 prompt + 自动调用

命令行参数:
```bash
# 标准模式
python -m lab_analysis.literature_interpreter_dspy --patient-id <id>

# DSPy 优化模式
python -m lab_analysis.literature_interpreter_dspy --patient-id <id> --use-dspy
```

### Prompt 提取与对比工具

#### `lab_analysis/dspy_modules/prompt_inspector.py`

DSPy 模块的 prompt 提取器,提供 3 个核心函数:

```python
from lab_analysis.dspy_modules.prompt_inspector import (
    extract_module_prompts,      # 提取模块所有 predictor 的 prompt 信息
    save_prompts_to_json,         # 保存为 JSON
    save_prompts_to_markdown,     # 保存为可读 Markdown
)

prompts_data = extract_module_prompts(my_dspy_module, "literature_interpreter")
save_prompts_to_json("literature_interpreter", prompts_data, output_dir)
save_prompts_to_markdown("literature_interpreter", prompts_data, output_dir)
```

提取内容: Signature instructions、输入/输出字段描述、Few-shot demos、DSPy 内部完整 prompt 重建。

#### `examples/dspy_prompt_comparison.py`

标准 vs DSPy 模式 prompt 对比工具,生成 Markdown + JSON 双格式报告:

```bash
python examples/dspy_prompt_comparison.py --data-dir data/<patient_id>/<timestamp>
```

输出: `data/<id>/<ts>/reports/dspy_prompt_comparison.{md,json}`,包含:
- 双模式 prompt 长度、章节、Few-shot 数对比
- 关键改进点分析(length_ratio、length_increase 等)
- 完整 prompt 文本快照

#### `examples/test_dspy_prompt_e2e.py`

端到端验证脚本,可直接运行验证整套保存与对比机制:

```bash
python examples/test_dspy_prompt_e2e.py
```

---

## 📂 项目结构

```
Lab-Analysis/
├── lab_analysis/                     # 核心代码包
│   ├── pipeline.py                   # Pipeline 统一入口
│   ├── ingest_data.py                # ① 数据摄入(检验图片/DICOM/MRI报告)
│   ├── data_loader.py                # ③ 数据加载与预处理
│   ├── data_analyzer.py              # ④ 统计分析(7 张图表)
│   ├── literature_searcher.py        # ⑤ PubMed 文献检索
│   ├── literature_interpreter.py     # ⑥ 文献解读(标准)
│   ├── literature_interpreter_dspy.py    # ⑥ 文献解读(双模式)
│   ├── qwen_vl_report_check.py       # ⑦ 影像报告检查(标准)
│   ├── qwen_vl_report_check_dspy.py  # ⑦ 影像报告检查(双模式)
│   ├── gen_final_report.py           # ⑧ 综合报告生成(标准)
│   ├── gen_final_report_dspy.py      # ⑧ 综合报告生成(双模式)
│   ├── extract_lab_data.py           # 检验数据提取(OCR)
│   ├── vision_extractor.py           # Vision AI 单图提取
│   ├── batch_vision_extract.py       # 批量视觉提取
│   ├── organize_local_files.py       # ⑨ 本地文件组织
│   ├── upload_to_feishu_backup.py    # 飞书上传备份实现
│   ├── patient_id.py                 # 患者 ID 脱敏
│   ├── error_logger.py               # 错误日志记录
│   ├── utils.py                      # 通用工具
│   └── dspy_modules/                 # 🧠 DSPy 优化模块
│       ├── __init__.py               # 包导出
│       ├── literature_interpreter.py # DSPy 文献解读
│       ├── mri_analyzer.py           # DSPy 影像分析
│       ├── final_report_generator.py # DSPy 报告生成
│       ├── lab_data_extractor.py     # DSPy 检验数据提取
│       └── prompt_inspector.py       # DSPy prompt 提取工具
├── examples/                         # 示例与工具脚本
│   ├── dspy_quickstart.py            # DSPy 快速开始
│   ├── dspy_prompt_comparison.py     # prompt 对比工具
│   ├── prepare_dspy_training_data.py # 训练数据准备
│   ├── collect_dspy_training_data.py # 训练数据收集
│   ├── compile_dspy_module.py        # DSPy 模块编译
│   ├── monitor_dspy_performance.py   # DSPy 性能监控
│   ├── test_dspy_basic.py            # DSPy 基础测试
│   ├── test_dspy_e2e.py              # DSPy 端到端测试
│   ├── test_dspy_llm.py              # DSPy LLM 连接测试
│   ├── test_dspy_prompt_e2e.py       # DSPy prompt 端到端测试
│   ├── test_prompt_extraction.py     # prompt 提取单元测试
│   ├── test_dashscope_compatibility.py # DashScope 兼容性测试
│   └── quick_ingest.py               # 快速数据摄入
├── docs/                             # 补充文档
│   ├── DSPY_INTEGRATION.md           # DSPy 集成技术方案
│   └── DSPY_USAGE.md                 # DSPy 使用指南
├── models/                           # 编译后模型存储
│   └── dspy/
│       └── literature_interpreter_compiled.json
├── raw/                              # 原始数据
│   └── Origin_data/                  # 待处理原始文件(lab_*.jpg / mri_*.jpg / export_*.zip)
├── data/                             # 分析结果(按患者ID与时间戳组织)
│   └── {patient_id}/
│       └── {timestamp}/
│           ├── lab_metrics.csv/json
│           ├── fig_01~07.png
│           ├── literature_results.md
│           ├── literature_interpretation.md
│           ├── mri_report_check_results.md
│           ├── analysis_results_report.md
│           ├── final_integrated_report.md
│           ├── reports/
│           │   └── dspy_prompt_comparison.{md,json}
│           └── dspy_prompts/
│               ├── *_standard_prompt.txt
│               └── *_dspy_prompts.{json,md}
├── local_upload/                     # 本地归档(按日期)
│   └── {YYYY-MM-DD}/
│       ├── 原始数据/
│       ├── 文献参考/
│       ├── 中间结果/
│       ├── 统计结果/
│       └── final_integrated_report.md
├── .env                              # 环境变量(不提交)
├── .env.example                      # 环境变量示例
├── pyproject.toml                    # 项目配置与依赖
└── run_analysis.py                   # 运行脚本入口
```

---

## 🔁 Pipeline 完整流程

`python -m lab_analysis --patient-id <id>` 会自动依次执行以下 9 个步骤,任何步骤失败均有日志记录,关键步骤支持 `--skip-xxx` 跳过。

| 步骤 | 名称 | 脚本模块 | 输入 | 输出 | DSPy 对应 |
|------|------|----------|------|------|----------|
| ① | **数据摄入** | `ingest_data.py` | `raw/Origin_data/` 中检验图片/DICOM/MRI 报告 | `raw/patient_<deid>/{lab,imaging,papers}/` | — |
| ② | **前置检查** | `pipeline.check_patient_data` | `raw/patient_<deid>/` 目录 | 校验报告 / 失败则退出 | — |
| ③ | **数据加载** | `data_loader.py` | `raw/patient_<deid>/papers/lab_report_*/metrics.md` | `data/<id>/<ts>/lab_metrics.csv` + `.json` | — |
| ④ | **统计分析** | `data_analyzer.py` | lab_metrics.csv | 7 张图表 `fig_01~07.png` + `analysis_results_report.md` | — |
| ⑤ | **文献检索** | `literature_searcher.py` | 检验项目 + 关键指标 | `literature_results.md`(PubMed 摘要) | — |
| ⑥ | **循证解读** | `literature_interpreter.py` / `..._dspy.py` | `literature_results.md` + lab_metrics | `literature_interpretation.md` + `dspy_prompts/` | `dspy_modules/literature_interpreter` |
| ⑦ | **影像分析** | `qwen_vl_report_check.py` / `..._dspy.py` | MRI 报告 + lab_metrics | `mri_report_check_results.md` + `dspy_prompts/` | `dspy_modules/mri_analyzer` |
| ⑧ | **综合报告** | `gen_final_report.py` / `..._dspy.py` | ④⑤⑥⑦ 全部产物 | `final_integrated_report.md` + `dspy_prompts/` | `dspy_modules/final_report_generator` |
| ⑨ | **本地归档** | `organize_local_files.py` | `data/<id>/<ts>/` 全部产物 | `local_upload/<YYYY-MM-DD>/` | — |

### 流程图

```
[① 数据摄入] → [② 前置检查] → [③ 数据加载] → [④ 统计分析]
                                                    ↓
[⑨ 本地归档] ← [⑧ 综合报告] ← [⑦ 影像分析] ← [⑥ 循证解读] ← [⑤ 文献检索]
```

> 步骤 ⑥⑦⑧ 在 `--use-dspy` 时使用对应的 `_dspy.py` 双模式脚本,并自动保存优化 prompt。

---

## 🛠️ 安装与配置

### 环境要求

- **Python**: 3.10+
- **操作系统**: Windows 10/11、macOS、Linux
- **磁盘**: ≥ 5 GB(含 DICOM 解压缓存)

### 1. 克隆与安装

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .
```

### 2. 安装 DSPy 依赖(DSPy 模式必需)

```bash
pip install "dspy-ai>=3.2" python-dotenv
```

### 3. 配置环境变量

复制示例并填入真实 Key:

```bash
cp .env.example .env
```

`.env` 关键字段说明:

| 变量 | 必填 | 用途 | 提供方 |
|------|------|------|--------|
| `WORK_ROOT` | ✅ | 项目工作根目录(默认当前目录) | — |
| `DEEPSEEK_API_KEY` | ✅ | 文献解读 / 报告生成 | DeepSeek |
| `DASHSCOPE_API_KEY` | ✅ | 影像分析(Qwen-VL) | 阿里云百炼 |
| `ZHIPU_API_KEY` | ⭕ | 检验报告 OCR | 智谱 AI |
| `FEISHU_FOLDER_TOKEN` | ⭕ | 飞书云盘上传(实验性) | 飞书开放平台 |
| `ANALYSIS_TS` | ⭕ | 指定时间戳(单步调试用) | — |

`.env` 示例:

```env
WORK_ROOT=E:/2026Workplace/Code/Lab-Analysis
DEEPSEEK_API_KEY=sk-xxxxxxxx
DASHSCOPE_API_KEY=sk-xxxxxxxx
ZHIPU_API_KEY=xxxxxxxx.xxxxxxxx
FEISHU_FOLDER_TOKEN=xxxxxxxx
```

---

## 🚀 运行示例

### 一键运行完整 Pipeline

```bash
# 标准模式(默认)
python -m lab_analysis --patient-id 846552421134373347

# 启用 DSPy 优化模式(覆盖 ⑥⑦⑧)
python -m lab_analysis --patient-id 846552421134373347 --use-dspy
```

### 跳过指定步骤

```bash
python -m lab_analysis --patient-id ID --skip-llm      # 跳过 ⑥ 文献解读
python -m lab_analysis --patient-id ID --skip-imaging  # 跳过 ⑦ 影像分析
python -m lab_analysis --patient-id ID --skip-ingest   # 跳过 ① 数据摄入
```

### 单独运行某一步骤(便于调试)

```bash
python -m lab_analysis.data_loader --patient-id ID
python -m lab_analysis.data_analyzer --patient-id ID
python -m lab_analysis.literature_searcher --patient-id ID
python -m lab_analysis.literature_interpreter_dspy --patient-id ID --use-dspy
python -m lab_analysis.qwen_vl_report_check_dspy --patient-id ID --use-dspy
python -m lab_analysis.gen_final_report_dspy --patient-id ID --use-dspy
```

> 单独运行 ⑥⑦⑧ 时需先设置 `ANALYSIS_TS` 环境变量指向已生成的时间戳目录:
> ```powershell
> $env:ANALYSIS_TS="20260611_111343"
> python -m lab_analysis.literature_interpreter_dspy --patient-id ID --use-dspy
> ```

### DSPy 训练与编译

```bash
# 准备训练数据
python examples/prepare_dspy_training_data.py

# 编译优化文献解读模块
python examples/compile_dspy_module.py

# 端到端 DSPy 测试
python examples/test_dspy_e2e.py
```

### Prompt 对比报告生成

```bash
# 1. 先用双模式各运行一次,产物会落在 data/<id>/<ts>/
python -m lab_analysis --patient-id ID --skip-ingest --skip-llm
python -m lab_analysis.literature_interpreter_dspy --patient-id ID
python -m lab_analysis.literature_interpreter_dspy --patient-id ID --use-dspy
# 2. 生成对比报告
python examples/dspy_prompt_comparison.py --data-dir data/<id>/<ts>
```

---

## 📊 输出文件说明

### 目录结构

```
data/{patient_id}/{timestamp}/
├── lab_metrics.csv                       # 检验数据(CSV,分析输入)
├── lab_metrics.json                      # 检验数据(JSON,含脱敏)
├── fig_01_trend_regression.png           # 趋势回归
├── fig_02_correlation_heatmap.png        # 相关性热图
├── fig_03_inflammation_assessment.png    # 炎症评估
├── fig_04_anomaly_detection.png          # 异常检测
├── fig_05_stability_analysis.png         # 稳定性分析
├── fig_06_trend_smoothing.png            # 趋势平滑
├── fig_07_comprehensive_dashboard.png    # 综合仪表板
├── analysis_results_report.md            # 统计分析详细报告
├── literature_results.md                 # PubMed 检索结果
├── literature_interpretation.md          # 文献解读(标准/DSPy)
├── mri_report_check_results.md           # 影像一致性报告
├── final_integrated_report.md            # 最终综合报告
├── reports/                              # 对比报告
│   ├── dspy_prompt_comparison.md         # Prompt 对比(Markdown)
│   └── dspy_prompt_comparison.json       # Prompt 对比(JSON)
├── 03_literature/                        # 文献解读工作目录
│   └── dspy_prompts/
│       ├── literature_interpreter_standard_prompt.txt
│       ├── literature_interpreter_dspy_prompts.json
│       └── literature_interpreter_dspy_prompts.md
├── 04_reports/                           # 报告生成工作目录
│   └── dspy_prompts/
│       ├── final_report_standard_prompt.txt
│       ├── final_report_dspy_prompts.json
│       └── final_report_dspy_prompts.md
└── dspy_prompts/                         # 影像/检验 prompt
    ├── mri_analyzer_standard_prompt.txt
    ├── mri_analyzer_dspy_prompts.json
    ├── mri_analyzer_dspy_prompts.md
    ├── lab_data_extractor_dspy_prompts.json
    └── lab_data_extractor_dspy_prompts.md
```

### `dspy_prompt_comparison.md` 内容示例

```markdown
# DSPy Prompt 对比报告

## 模块: literature_interpreter

| 维度 | 标准模式 | DSPy 模式 |
|------|---------|----------|
| Prompt 长度 | 975 字符 | 1546 字符(估算) |
| Few-shot 数 | 0 | 0 |
| 长度提升 | — | 1.59x(+571 字符) |

## 关键改进点
- DSPy 自动追加 ChainOfThought 推理指令
- 字段描述更结构化(Pathological → Output)
- 模板化输出格式引导更明确
```

---

## 📚 进阶文档

- [docs/DSPY_INTEGRATION.md](docs/DSPY_INTEGRATION.md) — DSPy 集成技术细节
- [docs/DSPY_USAGE.md](docs/DSPY_USAGE.md) — DSPy 使用指南
- [examples/dspy_quickstart.py](examples/dspy_quickstart.py) — DSPy 快速开始示例

---

## 🛠️ 技术栈

| 领域 | 选型 |
|------|------|
| 数据处理 | pandas, numpy, scipy |
| 机器学习 | scikit-learn |
| 可视化 | matplotlib |
| 图像处理 | Pillow, pydicom |
| OCR / Vision | 智谱 GLM-4V, 阿里云 Qwen-VL |
| 文本生成 | DeepSeek API, OpenAI 兼容协议 |
| LLM 优化 | DSPy 3.2+(BootstrapFewShot / MIPROv2) |
| 文献检索 | PubMed E-utilities API |
| 错误处理 | tenacity(重试) + 自研 error_logger |

---

## 📝 开发指南

### 代码规范

- PEP 8 + 类型注解
- 路径统一使用 `pathlib.Path`
- 优先 `WORK_ROOT` + 相对路径
- 双模式脚本命名 `<module>_dspy.py`

### 添加新模块

1. 在 `lab_analysis/` 创建模块
2. 实现 `main_with_args(args)` 标准接口
3. 在 `pipeline.py` 中用 `run_step()` 注册
4. 若涉及 LLM,同步实现 DSPy 版本与 `prompt_inspector` 集成

### 依赖管理

```bash
pip install -e .                    # 安装
pip install pip-tools               # 可选:生成锁定文件
pip-compile pyproject.toml -o requirements.lock
```

> ⚠️ 所有依赖在 `pyproject.toml` 中声明,请勿手动创建 `requirements.txt`。

### 错误日志

- 日志位置: `{WORK_ROOT}/error.log`
- 自动捕获: Pipeline 任一步骤失败时,记录命令、返回码、堆栈摘要
- 查看最近错误:
  ```python
  from lab_analysis.error_logger import get_recent_errors
  errors = get_recent_errors(n=10)
  ```

### 测试

```bash
# 单元 / 集成测试
python examples/test_dspy_prompt_e2e.py
python examples/test_dspy_e2e.py

# 代码检查
pip install ruff
ruff check lab_analysis/
```

---

## 🤝 贡献

欢迎 Issue 与 PR!

1. Fork 仓库
2. 创建特性分支(`git checkout -b feature/xxx`)
3. 提交更改(`git commit -m 'feat: add xxx'`)
4. 推送(`git push origin feature/xxx`)
5. 发起 Pull Request

---

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

## 👤 作者

**nxz1026** — [GitHub @nxz1026](https://github.com/nxz1026)

---

## 🙏 致谢

- DeepSeek、智谱 AI、阿里云百炼(Qwen-VL)提供的 LLM 能力
- Stanford NLP 的 [DSPy](https://dspy.ai/) 框架
- PubMed E-utilities 开放接口

---

⭐ 如果这个项目对您有帮助,请给个 Star!
