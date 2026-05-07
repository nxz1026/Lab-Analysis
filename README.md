# Lab-Analysis

> 医学检验数据自动化分析流水线 - 多源融合临床决策支持系统

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](https://github.com/nxz1026/Lab-Analysis)

---

## 📋 目录

- [简介](#简介)
- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [数据准备](#数据准备)
- [Vision模块](#vision模块)
- [输出说明](#输出说明)
- [配置](#配置)
- [故障排查](#故障排查)
- [开发](#开发)

---

## 简介

Lab-Analysis 是一个**端到端的医学数据分析流水线**，专为慢性胰腺炎等复杂病例设计。

**处理流程：**
```
原始数据 → 数据加载 → 统计分析 → 文献检索 → 循证解读 → 影像分析 → 综合报告 → 归档
```

---

## 核心特性

- **多模态数据融合**: 检验报告 + PubMed文献 + MRI影像
- **AI驱动分析**: 趋势检测、相关性分析、炎症分期、异常检测
- **专业可视化**: 趋势回归图、相关性热图、炎症状态图、异常指标图
- **循证医学支持**: 智能文献检索 + LLM深度解读
- **临床实用性**: 三源质控、分级行动计划、随访计划、预后评估
- **Vision智能识别**: OCR提取检验报告信息，支持批量处理

---

## 快速开始

### 前置要求

- Python ≥ 3.10
- API密钥：`DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY`

### 安装

```bash
# 克隆仓库
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install --upgrade pip
pip install -e .
```

### 配置API密钥

```bash
# Linux/macOS
export DEEPSEEK_API_KEY=sk-your-key
export DASHSCOPE_API_KEY=sk-your-key

# 或写入 ~/.hermes/.env 文件
```

### 运行

```bash
# 方式一：完整Pipeline（推荐）
python run_full_pipeline.py

# 方式二：直接调用
python -m lab_analysis.pipeline --patient-id 513229198801040014

# 方式三：快捷脚本
python run_analysis.py --patient-id 513229198801040014
```

**可选参数：**
- `--skip-llm`: 跳过文献检索和循证解读
- `--skip-imaging`: 跳过MRI影像分析

---

## 数据准备

### 目录结构

```
~/wiki/
├── raw/
│   ├── Origin_data/          # 原始文件
│   │   ├── lab_*.jpg         # 检验报告图片
│   │   └── export_*.zip      # DICOM压缩包
│   └── patient_{ID}/         # 结构化数据
│       ├── papers/           # 检验报告
│       │   └── lab_report_YYYYMMDD_type/
│       │       ├── metadata.md
│       │       └── metrics.md
│       └── imaging/          # 医学影像
│           └── seq_01/*.dcm
└── data/                     # 输出目录
    └── {ID}/{TIMESTAMP}/     # 时间戳子目录
```

### 文件格式

**metadata.md:**
```markdown
| 字段 | 值 |
|------|-----|
| 患者ID | 513229198801040014 |
| 报告日期 | 2026-03-24 |
| 报告类型 | outpatient |
```

**metrics.md:**
```text
WBC: 6.7
RBC: 4.52
HGB: 142
CRP: 10
hs-CRP: 2.78
```

---

## Vision模块

### 功能

使用Qwen-VL从检验报告图片中自动识别：
- 患者ID（身份证号）
- 报告日期
- 报告类型

### 使用方法

```bash
# 单张图片（自动模式）
python -m lab_analysis.vision_extractor --image "lab_report.jpg"

# 单张图片（交互模式）
python -m lab_analysis.vision_extractor --image "lab_report.jpg" --interactive

# 批量处理
python -m lab_analysis.batch_vision_extract [--interactive]

# 完整指标提取
python -m lab_analysis.extract_lab_data --image "lab_report.jpg" --patient-id <ID>
```

### 患者ID验证规则

- ✅ 18位身份证号（最后一位可为X）
- ✅ 15位身份证号
- ❌ 其他格式无效

---

## 输出说明

### 输出文件

| 文件 | 说明 |
|------|------|
| `lab_metrics.csv/json` | 标准化检验数据 |
| `analysis_results.json` | 统计分析结果 |
| `fig_01~04_*.png` | 4张可视化图表 |
| `literature_results.json/md` | PubMed文献 |
| `literature_interpretation.json/md` | 循证医学解读 |
| `mri_report_check_results.json/md` | 影像印证报告 |
| `final_integrated_report.md` | 三源融合综合报告 |

### 最终报告结构

- 患者基本信息
- 检验数据与炎症状态分析
- MRI影像学分析
- 多学科联合诊断意见
- 核心诊断结论
- 三源质控结论
- 行动计划（紧急/重要/常规）
- 随访与监测计划
- 预后评估

---

## 配置

### 环境变量

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API密钥（必需） |
| `DASHSCOPE_API_KEY` | 阿里云DashScope密钥（必需） |
| `OPENROUTER_API_KEY` | OpenRouter密钥（可选） |

### 配置文件位置

- API密钥: `~/.hermes/.env`
- 患者映射: `~/.hermes/patient_mapping.json`

---

## 故障排查

### 常见问题

1. **API密钥未配置**
   ```bash
   export DEEPSEEK_API_KEY=sk-your-key
   ```

2. **找不到患者数据目录**
   ```bash
   python run_full_pipeline.py  # 自动创建测试数据
   ```

3. **图表中文乱码**
   ```python
   import matplotlib
   matplotlib.rcParams['font.sans-serif'] = ['SimHei']
   ```

4. **LLM输出被截断**
   - 修改 `literature_interpreter.py` 中的 `max_tokens` 参数

---

## 开发

### 代码规范

- Python ≥ 3.10
- 遵循 PEP 8
- 使用 type hints
- 提交信息使用 Conventional Commits

### 添加新模块

1. 创建 `lab_analysis/your_module.py`
2. 实现 `main(patient_id, output_dir)` 函数
3. 注册到 `pipeline.py`

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 数据处理 | pandas, numpy, scipy |
| 可视化 | matplotlib, seaborn |
| 医学影像 | pydicom |
| 文献检索 | requests (PubMed) |
| LLM | DeepSeek, Qwen-VL |

---

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

<div align="center">
**Made with ❤️ for Clinical Decision Support**
</div>