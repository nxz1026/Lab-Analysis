# Lab-Analysis

> 慢性胰腺炎检验数据自动化分析 Pipeline（检验 + 文献 + 影像 + 综合报告）

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📋 项目简介

Lab-Analysis 是一个全自动化的医学检验数据分析系统，专为慢性胰腺炎患者设计。系统能够：

- 🔬 **自动提取**检验报告图片中的数据（OCR + Vision AI）
- 📊 **智能分析**检验指标趋势、相关性和异常检测
- 📚 **文献检索**与循证医学解读（PubMed + DeepSeek）
- 🖼️ **影像分析**MRI/DICOM 报告检查
- 📝 **生成综合报告**整合所有分析结果

## ✨ 核心功能

### 1. 数据摄入 (Data Ingestion)
- 支持检验报告图片自动识别（Vision AI）
- DICOM 影像数据解压和序列重命名
- MRI 文字报告解析
- 患者 ID 脱敏处理

### 2. 数据分析 (Data Analysis)
- **趋势回归分析** - 时间序列指标变化趋势
- **相关性热图** - 多指标间相关性可视化
- **炎症状态评估** - 综合炎症指标分析
- **异常指标检测** - 基于统计学的异常值识别
- **移动平均平滑** - 减少数据波动噪声
- **变异系数分析** - 指标稳定性评估

### 3. 文献检索与解读 (Literature)
- PubMed 自动检索相关文献
- DeepSeek AI 循证医学解读
- 文献与患者数据关联分析

### 4. 影像报告检查 (Imaging)
- Qwen-VL 模型检查 MRI 报告
- 影像学发现与检验数据一致性验证

### 5. 综合报告生成 (Final Report)
- 三源一致性评估（检验+文献+影像）
- 自动生成结构化综合报告
- 本地文件自动组织归档

## 🚀 快速开始

### 前置要求

- Python 3.10+
- 环境变量配置（见下方）

### 安装

```bash
# 克隆仓库
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis

# 安装依赖
pip install -r requirements.txt

# 或作为包安装
pip install -e .
```

### 配置环境变量

创建 `.env` 文件（参考 `.env.example`）：

```env
# ===== 基础配置 =====
WIKI_ROOT=/path/to/your/wiki  # 项目数据根目录

# ===== AI API 密钥 =====
ZHIPU_API_KEY=your_zhipu_key           # 智谱 AI（Vision 模型）
DEEPSEEK_API_KEY=your_deepseek_key     # DeepSeek（文献解读）
DASHSCOPE_API_KEY=your_dashscope_key   # 阿里云（Qwen-VL）

# ===== 可选：飞书云盘 =====
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_FOLDER_TOKEN=your_folder_token
```

### 运行 Pipeline

#### 方式 1：完整流程

```bash
# 使用诊疗卡号运行
python run_analysis.py --patient-id YOUR_PATIENT_ID

# 或使用模块方式
python -m lab_analysis --patient-id YOUR_PATIENT_ID
```

#### 方式 2：跳过某些步骤

```bash
# 跳过 LLM 文献解读
python run_analysis.py --patient-id YOUR_PATIENT_ID --skip-llm

# 跳过影像分析
python run_analysis.py --patient-id YOUR_PATIENT_ID --skip-imaging

# 跳过数据摄入（使用已有数据）
python run_analysis.py --patient-id YOUR_PATIENT_ID --skip-ingest
```

#### 方式 3：手动摄入数据

```bash
# 摄入检验报告图片
python run_analysis.py \
  --patient-id YOUR_PATIENT_ID \
  --ingest-lab report1.jpg report2.jpg \
  --report-date 2026-05-07 \
  --report-type outpatient

# 摄入 DICOM 影像
python run_analysis.py \
  --patient-id YOUR_PATIENT_ID \
  --ingest-dicom-zip dicom_scan.zip
```

## 📂 项目结构

```
Lab-Analysis/
├── lab_analysis/              # 核心模块
│   ├── pipeline.py            # Pipeline 主入口
│   ├── ingest_data.py         # 数据摄入
│   ├── data_loader.py         # 数据加载
│   ├── data_analyzer.py       # 数据分析（7张图表）
│   ├── literature_searcher.py # 文献检索
│   ├── literature_interpreter.py  # 文献解读
│   ├── qwen_vl_report_check.py    # 影像报告检查
│   ├── gen_final_report.py    # 综合报告生成
│   ├── organize_local_files.py    # 本地文件组织
│   ├── vision_extractor.py    # Vision AI 提取
│   ├── batch_vision_extract.py    # 批量视觉提取
│   ├── extract_lab_data.py    # 检验数据提取
│   ├── patient_id.py          # 患者ID处理
│   └── utils.py               # 工具函数
├── raw/                       # 原始数据目录
│   └── Origin_data/           # 待处理的原始文件
├── data/                      # 分析结果（按患者ID组织）
│   └── {patient_id}/
│       └── {timestamp}/
│           ├── lab_metrics.csv/json      # 检验数据
│           ├── fig_01~07.png             # 7张分析图表
│           ├── literature_results.md     # 文献检索结果
│           ├── literature_interpretation.md  # 文献解读
│           ├── mri_report_check_results.md   # 影像检查结果
│           ├── analysis_results_report.md    # 分析报告
│           └── final_integrated_report.md    # 最终综合报告
├── local_upload/              # 本地归档目录
│   └── {YYYY-MM-DD}/
│       ├── 原始数据/
│       ├── 文献参考/
│       ├── 中间结果/
│       ├── 统计结果/
│       └── final_integrated_report.md
├── .env                       # 环境变量配置（不提交到Git）
├── .env.example               # 环境变量示例
├── requirements.txt           # Python 依赖
├── pyproject.toml             # 项目配置
└── run_analysis.py            # 运行脚本入口
```

## 📊 输出说明

### 生成的 7 张分析图表

1. **fig_01_trend_regression.png** - 关键指标趋势回归分析
2. **fig_02_correlation_heatmap.png** - 指标相关性热图
3. **fig_03_inflammation_status.png** - 炎症状态综合评估
4. **fig_04_abnormal_indicators.png** - 异常指标检测
5. **fig_05_indicator_stability.png** - 指标稳定性分析（变异系数）
6. **fig_06_trend_smoothing.png** - 趋势平滑对比（移动平均）
7. **fig_07_comprehensive_dashboard.png** - 综合分析仪表板

### 报告文件

- **final_integrated_report.md** - 最终综合报告（包含三源一致性评估）
- **analysis_results_report.md** - 统计分析详细报告
- **literature_interpretation.md** - 文献循证解读
- **mri_report_check_results.md** - 影像报告检查结果

## 🔧 高级用法

### 批量处理检验报告

```bash
python -m lab_analysis.batch_vision_extract [--interactive]
```

自动扫描 `Origin_data` 目录下的所有检验报告图片，批量识别并摄入。

### 单独运行某个模块

```bash
# 只运行数据分析
python -m lab_analysis.data_analyzer --patient-id YOUR_PATIENT_ID

# 只运行文献检索
python -m lab_analysis.literature_searcher --patient-id YOUR_PATIENT_ID

# 只生成本地归档
python -m lab_analysis.organize_local_files --patient-id YOUR_PATIENT_ID
```

## 🛠️ 技术栈

- **数据处理**: pandas, numpy, scipy
- **机器学习**: scikit-learn
- **可视化**: matplotlib
- **图像处理**: Pillow
- **AI 模型**:
  - 智谱 GLM-4V（检验报告 OCR）
  - DeepSeek（文献解读）
  - 阿里云 Qwen-VL（影像报告检查）
- **文献检索**: PubMed API

## 📝 开发指南

### 代码规范

- 遵循 PEP 8 编码规范
- 使用类型注解（Type Hints）
- 所有路径使用 `WIKI_ROOT` 环境变量 + 相对路径

### 添加新分析模块

1. 在 `lab_analysis/` 目录下创建新模块
2. 实现标准接口（接受 `--patient-id` 参数）
3. 在 `pipeline.py` 中注册新步骤

### 测试

```bash
# 运行单个模块测试
python -m lab_analysis.data_analyzer --patient-id TEST_ID

# 检查代码风格
pip install ruff
ruff check lab_analysis/
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 👤 作者

- **nxz1026** - [GitHub](https://github.com/nxz1026)

## 🙏 致谢

- 智谱 AI - 提供 Vision 模型支持
- DeepSeek - 提供文献解读能力
- 阿里云 - 提供 Qwen-VL 模型

---

**⭐ 如果这个项目对您有帮助，请给个 Star！**
