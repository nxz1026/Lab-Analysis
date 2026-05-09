# Lab-Analysis

> 医学检验数据自动化分析流水线 — 从检验报告图片到临床综合报告的端到端解决方案

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 简介

Lab-Analysis 自动完成从检验报告图片到结构化分析报告的全流程：

```
检验报告图片 → AI指标提取 → 统计分析 → PubMed文献检索 → 循证解读 → 综合报告
```

**核心能力：**
- AI 视觉识别：从检验报告图片自动提取指标（智谱 GLM-4V-Flash）
- 统计分析：趋势回归、相关性热图、炎症分期、异常检测、Z-score 分布
- 循证医学：基于分析结果自动检索 PubMed，DeepSeek 深度解读文献
- 多源融合：检验数据 + 文献证据 → 生成结构化临床报告

---

## 🚀 快速开始

### 1. 环境准备

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
pip install --upgrade pip
pip install -e .
```

### 2. 配置 API 密钥

```bash
cp .env.example .env
# 编辑 .env，填入以下密钥：
```

| 密钥 | 说明 | 获取地址 |
|------|------|---------|
| `DEEPSEEK_API_KEY` | 文献解读（DeepSeek 模型） | https://platform.deepseek.com/ |
| `DASHSCOPE_API_KEY` | 影像分析（Qwen-VL 模型） | https://dashscope.console.aliyun.com/ |
| `ZHIPU_API_KEY` | 检验报告识别（GLM-4V-Flash） | https://open.bigmodel.cn/ |

### 3. 放入检验报告

将原始图片放入 `raw/Origin_Data/`，命名规范：

```
raw/Origin_Data/
├── lab_2026-03-24_outpatient.jpg    # 检验报告（门诊）
├── lab_2026-04-08_inpatient.jpg     # 检验报告（住院）
├── mri_2026-04-11.jpg               # MRI 文字报告
└── export_part1_20260501.zip        # DICOM 压缩包（可选）
```

### 4. 运行 Pipeline

```bash
# 推荐用法（需在仓库根目录，或先 pip install -e .）
python -m lab_analysis --patient-id <身份证号>

# 跳过 MRI 影像分析
python -m lab_analysis --patient-id <身份证号> --skip-imaging

# 跳过 LLM 循证解读
python -m lab_analysis --patient-id <身份证号> --skip-llm
```

> 患者 ID 传入原始身份证号，系统自动 hex 编码为脱敏目录名，保护隐私。

---

## 📂 项目结构

```
Lab-Analysis/
├── .env                        # API 密钥配置（不要提交）
├── .env.example                # 配置模板
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── init_dirs.py               # 创建必要目录结构
└── lab_analysis/               # 核心模块（统一入口 python -m lab_analysis）
    ├── __init__.py
    ├── __main__.py             # python -m lab_analysis 入口
    ├── config.py               # 统一配置管理（dotenv 加载）
    ├── validators.py            # 类型安全验证工具
    ├── utils.py                # 路径构建等工具函数
    ├── patient_id.py           # 患者 ID hex 脱敏
    ├── pipeline.py             # Pipeline 编排器（9步）
    ├── ingest_data.py          # 数据摄入（DICOM 解压、文件分类）
    ├── extract_lab_data.py     # 检验指标提取（Vision AI）
    ├── vision_extractor.py     # 智谱 GLM-4V-Flash 调用封装
    ├── data_loader.py          # 加载 metrics.md → CSV/JSON
    ├── data_analyzer.py        # 统计分析 + 7张图表生成
    ├── literature_searcher.py  # PubMed E-utilities 文献检索
    ├── literature_interpreter.py # DeepSeek 循证解读
    ├── qwen_vl_report_check.py  # 阿里 Qwen-VL MRI 影像分析
    ├── organize_local_files.py  # 整理输出文件结构
    └── gen_final_report.py     # 生成综合临床报告
```

---

## 🔄 Pipeline 9 步流程

```
① 数据摄入          ingest_data          Origin_Data → raw/patient_{deid}/
② 数据校验          pipeline              验证目录结构
③ 数据加载          data_loader           metrics.md → lab_metrics.csv/json
④ 统计分析          data_analyzer         生成7张分析图表
⑤ 文献检索          literature_searcher   PubMed → literature_results.json
⑥ 循证解读          literature_interpreter DeepSeek → 临床建议
⑦ 影像分析          qwen_vl_report_check  Qwen-VL → MRI 印证报告
⑧ 生成报告          gen_final_report      三源融合 → final_integrated_report.md
⑨ 文件归档          organize_local_files  整理输出目录
```

### 数据分析（④）生成 7 张图表

| 图表 | 内容 |
|------|------|
| `fig_01_trend_regression.png` | 关键指标趋势回归（线性拟合 + R²） |
| `fig_02_correlation_heatmap.png` | 指标间 Pearson 相关系数热图 |
| `fig_03_inflammation_status.png` | 炎症状态分期（急性/慢性/恢复期） |
| `fig_04_abnormal_indicators.png` | 超出参考范围的异常指标高亮 |
| `fig_05_moving_average.png` | 2期移动平均趋势 |
| `fig_06_cv_stability.png` | 变异系数稳定性分析 |
| `fig_07_zscore_distribution.png` | Z-score 标准化分布箱线图 |

---

## 📊 输出结构

```
data/{脱敏ID}/{时间戳}/
├── 02_analyzed/
│   ├── lab_metrics.csv
│   ├── lab_metrics.json
│   ├── analysis_results.json         # 统计分析结果
│   ├── analysis_results_report.md    # 统计摘要
│   └── figures/                     # 7张图表
│       ├── fig_01_trend_regression.png
│       ├── fig_02_correlation_heatmap.png
│       └── ...（共7张）
├── 03_literature/
│   ├── literature_results.json      # PubMed 检索结果
│   ├── literature_results.md
│   ├── literature_interpretation.json  # DeepSeek 循证解读
│   └── literature_interpretation.md
└── 04_reports/
    ├── analysis_results_report.md
    └── final_integrated_report.md   # 最终临床报告
```

---

## 🛠 高级用法

### 手动摄入单张检验报告

```bash
python -m lab_analysis.extract_lab_data \
    --image "lab_report.jpg" \
    --patient-id "510XXXXXXXXXXXXXXX"
```

### 手动摄入 DICOM

```bash
python -m lab_analysis.ingest_data \
    --type mri_dicom \
    --zip-path "export.zip" \
    --patient-id "510XXXXXXXXXXXXXXX" \
    --report-date "2026-04-11"
```

### 分步运行 Pipeline

```bash
# 只做数据摄入
python -m lab_analysis --patient-id <ID> --skip-llm --skip-imaging

# 只做分析和报告（跳过摄入）
python -m lab_analysis --patient-id <ID> --skip-ingest
```

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `WORK_ROOT` | 工作区根目录 | 项目根目录 |
| `ORIGIN_DATA_DIR` | 原始数据目录 | `{WORK_ROOT}/raw` |
| `DEEPSEEK_API_KEY` | DeepSeek 密钥 | — |
| `DASHSCOPE_API_KEY` | 阿里云密钥 | — |
| `ZHIPU_API_KEY` | 智谱 AI 密钥 | — |

### 工作目录结构

```
{WORK_ROOT}/
├── raw/
│   ├── Origin_Data/                    # 原始文件（用户放置）
│   └── patient_{hex(ID)}/              # 结构化数据（自动生成）
│       ├── lab/                        # 检验报告原图
│       ├── papers/                     # Vision 提取的结构化报告
│       │   └── lab_report_YYYYMMDD_type/
│       │       ├── metadata.md
│       │       └── metrics.md
│       └── imaging/                    # MRI/DICOM 影像
└── data/
    └── {hex(ID)}/{时间戳}/            # Pipeline 输出
```

---

## 🔧 故障排查

**API 密钥验证：**
```bash
python -c "from lab_analysis.config import DEEPSEEK_API_KEY; print(DEEPSEEK_API_KEY[:8]+'...')"
```

**Vision 识别失败：** 检查 `ZHIPU_API_KEY` 是否有效，图片是否清晰。

**图表中文乱码：** Linux 服务器需安装中文字体，如 `apt install fonts-noto-cjk`。

---

## 📝 开发指南

- Python ≥ 3.10
- 所有模块从 `lab_analysis.config` 统一导入配置，不再各自加载 `.env`
- 新增模块：在 `lab_analysis/` 创建文件，在 `pipeline.py` 中注册步㵖
- 提交规范：使用 [Conventional Commits](https://www.conventionalcommits.org/)

---

## 📄 许可证

MIT License — 详见 [LICENSE](LICENSE)
