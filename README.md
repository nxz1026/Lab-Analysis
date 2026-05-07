# Lab-Analysis

> 医学检验数据自动化分析流水线 - 多源融合临床决策支持系统

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)](https://github.com/nxz1026/Lab-Analysis)

---

## 🎯 简介

Lab-Analysis 是端到端的医学数据分析系统，专为慢性胰腺炎等复杂病例设计。自动完成从原始数据到综合报告的全流程分析。

**核心流程：**
```
原始数据 → 智能摄入 → 统计分析 → 文献检索 → 循证解读 → 影像分析 → 综合报告
```

---

## ✨ 核心特性

- **🤖 AI驱动识别**：智谱AI GLM-4V-Flash自动提取检验报告指标
- **📊 多模态融合**：检验数据 + PubMed文献 + MRI影像三源质控
- **🔬 专业分析**：趋势检测、相关性分析、炎症分期、异常检测
- **📈 智能可视化**：自动生成趋势图、热图、炎症状态图、异常指标图
- **📚 循证医学**：PubMed智能检索 + DeepSeek深度解读
- **🏥 临床实用**：分级行动计划、随访计划、预后评估

---

## 🚀 快速开始

### 1️⃣ 环境准备

```bash
# 克隆仓库
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# 安装依赖
pip install --upgrade pip
pip install -e .
```

### 2️⃣ 配置环境变量

创建 `.env` 文件（项目根目录）：

```env
# ===== 必需配置 =====
DEEPSEEK_API_KEY=sk-your-deepseek-key
DASHSCOPE_API_KEY=sk-your-dashscope-key

# ===== Vision识别（智谱AI）=====
ZHIPU_API_KEY=your-zhipu-api-key

# ===== 可选配置 =====
WIKI_ROOT=F:\Lab_analysis\          # 工作区根目录（默认：项目根目录）
ORIGIN_DATA_DIR=F:\Lab_analysis\raw # 原始数据目录
```

> 💡 **获取API密钥**：
> - DeepSeek: https://platform.deepseek.com/
> - DashScope (阿里云): https://dashscope.console.aliyun.com/
> - 智谱AI: https://open.bigmodel.cn/

### 3️⃣ 准备数据

将原始文件放入 `Origin_data` 目录：

```
F:\Lab_analysis\raw\Origin_data\
├── lab_2026-03-24_outpatient.jpg      # 检验报告图片
├── lab_2026-03-30_outpatient.jpg
├── mri_2026-04-11.jpg                 # MRI报告图片
└── export_part1_20260501172611350.zip # DICOM压缩包
```

**文件命名规范：**
- 检验报告：`lab_YYYY-MM-DD_type.jpg`（type: outpatient/inpatient）
- MRI报告：`mri_YYYY-MM-DD.jpg`
- DICOM压缩包：`export_*.zip` 或 `dicom_*.zip`

### 4️⃣ 运行Pipeline

```bash
# 完整流程（推荐）
python -m lab_analysis.pipeline --patient-id YOUR_PATIENT_ID

# 跳过MRI影像分析（无DICOM数据时）
python -m lab_analysis.pipeline --patient-id YOUR_PATIENT_ID --skip-imaging

# 使用已有数据，跳过自动摄入
python -m lab_analysis.pipeline --patient-id YOUR_PATIENT_ID --skip-ingest
```

> ⚠️ **首次运行**会提示输入患者身份证号（18位），系统会自动脱敏处理。

> ⚠️ **patient-id 参数说明**：应传入原始身份证号（18位），系统自动 hex-encode 为脱敏ID后再写入数据目录。传入已脱敏ID会导致路径不匹配。

---

## 📂 项目结构

```
Lab-Analysis/
├── .env                          # 环境变量配置
├── pyproject.toml                # 包管理配置
├── requirements.txt              # Python依赖
└── lab_analysis/                 # 核心模块
    ├── pipeline.py               # Pipeline编排器
    ├── ingest_data.py            # 统一数据摄入
    ├── patient_id.py             # 患者ID脱敏（hex encode）
    ├── extract_lab_data.py       # 检验指标提取（Vision）
    ├── vision_extractor.py       # Vision图片识别
    ├── data_loader.py            # 数据加载器
    ├── data_analyzer.py          # 统计分析引擎（7张图）
    ├── literature_searcher.py    # PubMed文献检索
    ├── literature_interpreter.py # LLM循证解读
    ├── qwen_vl_report_check.py   # MRI影像分析
    ├── gen_final_report.py       # 综合报告生成
    └── upload_to_feishu.py       # 飞书云盘上传
```

---

## 🔄 完整工作流程

### Step ①：自动数据摄入

系统自动扫描 `Origin_data` 目录，识别并处理以下文件：

| 文件类型 | 处理方式 | 输出位置 |
|---------|---------|---------|
| `lab_*.jpg/png` | Vision提取检验指标 | `raw/patient_{ID}/papers/lab_report_*/` |
| `mri_*.jpg/png` | MRI文字报告摄入 | `raw/patient_{ID}/imaging/` |
| `export_*.zip` | DICOM序列解压 | `raw/patient_{ID}/imaging/seq_XX/` |

**智能特性：**
- ✅ 自动解析文件名提取日期和类型
- ✅ 单个文件失败不影响其他文件
- ✅ 实时进度显示和错误统计

### Step ②：数据加载

从结构化目录加载检验数据：
- 读取 `metadata.md`（患者信息、报告日期、类型）
- 读取 `metrics.md`（检验指标数值）
- 合并多份报告为时间序列数据

### Step ③：统计分析

自动执行4项分析并生成图表（7张）：

1. **趋势回归分析** → `fig_01_trend_regression.png`
   - WBC、CRP、hs-CRP等关键指标趋势
   - 线性回归拟合 + R²值

2. **相关性热图** → `fig_02_correlation_heatmap.png`
   - 指标间Pearson相关系数
   - 显著性标记（*p<0.05, **p<0.01）

3. **炎症状态图** → `fig_03_inflammation_status.png`
   - CRP-WBC分离现象检测
   - 炎症分期（急性/慢性/恢复期）

4. **异常指标图** → `fig_04_abnormal_indicators.png`
   - 超出参考范围的指标高亮
   - 异常程度可视化

5. **移动平均图** → `fig_05_moving_average.png`
   - 关键指标2期移动平均趋势

6. **CV稳定性图** → `fig_06_cv_stability.png`
   - 各指标变异系数对比，高变异指标预警

7. **Z-score分布图** → `fig_07_zscore_distribution.png`
   - 各指标Z-score标准化分布箱线图

### Step ④：文献检索

基于分析结果自动生成检索词，查询PubMed：

**检索主题示例：**
- 慢性胰腺炎 + 炎症标志物
- RDW预后价值
- PCT脓毒症诊断
- CRP-WBC分离机制

输出：`literature_results.json` / `.md`（含PMID、标题、摘要）

### Step ⑤：循证解读

调用DeepSeek API对文献进行深度解读：

**解读内容：**
- 病理生理机制分析
- 临床意义阐释
- 治疗建议推荐
- 预后评估依据

输出：`literature_interpretation.json` / `.md`

### Step ⑥：MRI影像分析（可选）

使用Qwen-VL分析DICOM序列：

**分析内容：**
- 胰腺实质萎缩程度
- 主胰管扩张测量
- 肝内胆管扩张
- 胆囊结石检测
- 与检验数据印证

输出：`mri_report_check_results.json` / `.md`

### Step ⑦：生成综合报告

三源融合生成最终临床诊断报告：

**报告结构：**
```markdown
# 综合临床诊断报告

## 1. 患者基本信息
## 2. 检验数据与炎症状态分析
## 3. MRI影像学分析
## 4. 多学科联合诊断意见
## 5. 核心诊断结论
## 6. 三源质控结论
## 7. 行动计划（紧急/重要/常规）
## 8. 随访与监测计划
## 9. 预后评估
```

输出：`final_integrated_report.md`

### Step ⑧：归档上云（可选）

自动上传至飞书云盘备份。

---

## 📊 输出文件说明

所有输出保存在 `{WIKI_ROOT}/data/{脱敏ID}/{时间戳}/`：

```
{时间戳}/
├── 02_analyzed/               # 检验分析结果
│   ├── lab_metrics.csv/json    # 标准化检验数据
│   ├── analysis_results.json   # 统计分析结果（趋势、相关性、炎症分期）
│   ├── analysis_results_report.md  # 分析报告摘要
│   └── figures/                # 可视化图表（7张）
│       ├── fig_01_trend_regression.png
│       ├── fig_02_correlation_heatmap.png
│       ├── fig_03_inflammation_status.png
│       ├── fig_04_abnormal_indicators.png
│       ├── fig_05_moving_average.png
│       ├── fig_06_cv_stability.png
│       └── fig_07_zscore_distribution.png
├── 03_literature/              # 文献研究结果
│   ├── literature_results.json/md   # PubMed检索结果
│   ├── literature_interpretation.json/md  # 循证医学解读
│   └── mri_report_check_results.json/md   # MRI影像印证报告
└── 04_reports/                 # 综合报告
    ├── analysis_results_report.md   # 统计分析报告
    └── final_integrated_report.md   # 三源融合综合报告
```

---

## 🛠️ 高级用法

### 手动数据摄入

```bash
# 检验报告图片
python -m lab_analysis.ingest_data --type lab_image \
    --path "lab_report.jpg" \
    --patient-id "YOUR_PATIENT_ID" \
    --report-date "2026-03-24" \
    --report-type "outpatient"

# MRI DICOM压缩包
python -m lab_analysis.ingest_data --type mri_dicom \
    --zip-path "export_part1.zip" \
    --patient-id "YOUR_PATIENT_ID" \
    --report-date "2026-04-11"

# MRI文字报告
python -m lab_analysis.ingest_data --type mri_report \
    --path "mri_report.pdf" \
    --patient-id "YOUR_PATIENT_ID" \
    --report-date "2026-04-11"
```

### Vision单独调用

```bash
# 单张图片识别
python -m lab_analysis.extract_lab_data \
    --image "lab_report.jpg" \
    --patient-id "YOUR_PATIENT_ID"

# 批量识别
python -m lab_analysis.batch_vision_extract [--interactive]
```

### Pipeline参数

```bash
python -m lab_analysis.pipeline \
    --patient-id YOUR_PATIENT_ID \
    --skip-ingest \      # 跳过数据摄入
    --skip-imaging \     # 跳过MRI分析
    --skip-llm           # 跳过文献检索和解读
```

---

## ⚙️ 配置说明

### 环境变量

| 变量 | 说明 | 必需 |
|------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API密钥（文献解读） | ✅ |
| `DASHSCOPE_API_KEY` | 阿里云DashScope密钥（Qwen-VL） | ✅ |
| `ZHIPU_API_KEY` | 智谱AI密钥（检验报告识别） | ✅ |
| `WIKI_ROOT` | 工作区根目录 | ❌ 默认：项目根目录 |
| `ORIGIN_DATA_DIR` | 原始数据目录 | ❌ 默认：`{WIKI_ROOT}/raw` |

### 目录结构

```
{WIKI_ROOT}/
├── raw/
│   ├── Origin_data/          # 原始文件（用户放置）
│   └── patient_{hex(ID)}/     # 结构化数据（自动生成）
│       ├── lab/               # 检验报告原始图片
│       ├── papers/            # Vision提取的结构化报告
│       │   └── lab_report_YYYYMMDD_type/
│       │       ├── metadata.md
│       │       └── metrics.md
│       └── imaging/           # 医学影像（DICOM序列）
│           └── seq_XX/*.dcm
└── data/
    └── {hex(ID)}/{时间戳}/    # 完整pipeline输出
        ├── 02_analyzed/       # 检验分析结果
        ├── 03_literature/     # 文献研究结果
        └── 04_reports/        # 综合报告
```

---

## 🔧 故障排查

### 常见问题

**1. API密钥未配置**
```bash
# 检查 .env 文件是否存在且格式正确
cat .env

# 验证环境变量已加载
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.environ.get('ZHIPU_API_KEY', 'NOT FOUND')[:10])"
```

**2. 找不到患者数据**
```bash
# 确保 Origin_data 目录有文件
ls F:\Lab_analysis\raw\Origin_data\

# 或手动指定患者ID运行
python -m lab_analysis.pipeline --patient-id YOUR_PATIENT_ID
```

**3. Vision识别失败**
- 检查 `ZHIPU_API_KEY` 是否有效
- 确认图片清晰可读
- 查看错误日志中的HTTP状态码

**4. 图表中文乱码**
```python
# 修改 matplotlib 字体配置
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei']  # Windows
# matplotlib.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # macOS
```

**5. LLM输出被截断**
- 修改 `literature_interpreter.py` 中的 `max_tokens` 参数
- 增加API超时时间

---

## 🧪 技术栈

| 类别 | 技术 |
|------|------|
| **语言** | Python 3.10+ |
| **数据处理** | pandas, numpy, scipy |
| **可视化** | matplotlib, seaborn |
| **医学影像** | pydicom |
| **文献检索** | requests (PubMed E-utilities) |
| **AI模型** | 智谱AI GLM-4V-Flash, DeepSeek, Qwen-VL |
| **工具库** | python-dotenv, argparse |

---

## 📝 开发指南

### 代码规范

- Python ≥ 3.10
- 遵循 PEP 8
- 使用 type hints
- 提交信息使用 Conventional Commits

### 添加新模块

1. 创建 `lab_analysis/your_module.py`
2. 实现 `main(patient_id, output_dir)` 函数
3. 在 `pipeline.py` 中注册新步骤

### 模块说明

| 模块 | 功能 |
|------|------|
| `pipeline.py` | Pipeline编排器 |
| `ingest_data.py` | 统一数据摄入 |
| `extract_lab_data.py` | 检验指标提取（Vision） |
| `data_loader.py` | 检验数据加载 |
| `data_analyzer.py` | 统计分析与可视化 |
| `literature_searcher.py` | PubMed文献检索 |
| `literature_interpreter.py` | LLM循证解读 |
| `qwen_vl_report_check.py` | MRI影像分析 |
| `gen_final_report.py` | 综合报告生成 |

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

<div align="center">

**Made with ❤️ for Clinical Decision Support**

[⭐ Star this repo](https://github.com/nxz1026/Lab-Analysis) · [🐛 Report Bug](https://github.com/nxz1026/Lab-Analysis/issues) · [💡 Request Feature](https://github.com/nxz1026/Lab-Analysis/issues)

</div>
