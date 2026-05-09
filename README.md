# Lab-Analysis

慢性胰腺炎检验数据自动化分析 Pipeline（检验 + 文献 + 影像 + 综合报告）

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📋 简介

全自动医学检验数据分析系统：

- 🔬 **自动提取** - 检验报告 OCR 识别
- 📊 **智能分析** - 7 张图表可视化
- 📚 **文献检索** - PubMed + AI 解读
- 🖼️ **影像检查** - MRI/DICOM 验证
- 📝 **综合报告** - 三源一致性评估

## ✨ 核心功能

### 1. 数据摄入
- 检验报告图片 OCR 识别
- DICOM 影像解压与重命名
- MRI 文字报告解析
- 患者 ID 脱敏

### 2. 数据分析（7 张图表）
- 趋势回归、相关性热图
- 炎症评估、异常检测
- 移动平均、变异系数、综合仪表板

### 3. 文献检索与解读
- PubMed 自动检索
- DeepSeek AI 循证解读

### 4. 影像报告检查
- Qwen-VL 模型验证 MRI 报告
- 影像与检验数据一致性检查

### 5. 综合报告生成
- 三源一致性评估
- 结构化报告 + 本地归档

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .
```

### 配置环境变量

创建 `.env` 文件：

```env
WORK_ROOT=/path/to/your/work
ZHIPU_API_KEY=your_zhipu_key
DEEPSEEK_API_KEY=your_deepseek_key
DASHSCOPE_API_KEY=your_dashscope_key
```

### 运行

```bash
# 推荐方式
python -m lab_analysis --patient-id YOUR_PATIENT_ID

# 或便捷方式
python run_analysis.py --patient-id YOUR_PATIENT_ID
```

#### 跳过步骤

```bash
python -m lab_analysis --patient-id ID --skip-llm      # 跳过文献解读
python -m lab_analysis --patient-id ID --skip-imaging  # 跳过影像分析
python -m lab_analysis --patient-id ID --skip-ingest   # 跳过数据摄入
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
├── pyproject.toml             # 项目配置与依赖管理
└── run_analysis.py            # 运行脚本入口
```

## 📊 输出

### 7 张分析图表

1. **fig_01** - 趋势回归
2. **fig_02** - 相关性热图
3. **fig_03** - 炎症评估
4. **fig_04** - 异常检测
5. **fig_05** - 稳定性分析
6. **fig_06** - 趋势平滑
7. **fig_07** - 综合仪表板

### 报告文件

- `final_integrated_report.md` - 最终综合报告
- `analysis_results_report.md` - 统计分析详细报告
- `literature_interpretation.md` - 文献解读
- `mri_report_check_results.md` - 影像检查结果

## 🔧 高级用法

### 批量处理

```bash
python -m lab_analysis.batch_vision_extract [--interactive]
```

自动扫描 `Origin_data` 目录，批量识别并摄入检验报告。

### 单独运行模块

```bash
python -m lab_analysis.data_analyzer --patient-id ID           # 数据分析
python -m lab_analysis.literature_searcher --patient-id ID     # 文献检索
python -m lab_analysis.organize_local_files --patient-id ID    # 本地归档
```

## 🛠️ 技术栈

- **数据处理**: pandas, numpy, scipy
- **机器学习**: scikit-learn
- **可视化**: matplotlib
- **图像处理**: Pillow
- **AI 模型**: 智谱 GLM-4V、DeepSeek、阿里云 Qwen-VL
- **文献检索**: PubMed API

## 📝 开发指南

### 代码规范

- PEP 8 编码规范
- 类型注解（Type Hints）
- 路径使用 `WORK_ROOT` + 相对路径
- 使用 `pathlib.Path`

### 依赖管理

```bash
pip install -e .                    # 安装依赖
pip install pip-tools               # 可选：生成锁定文件
pip-compile pyproject.toml -o requirements.lock
```

> ⚠️ 所有依赖在 `pyproject.toml` 中声明，勿手动创建 `requirements.txt`。

### 错误日志

- **日志文件**: `{WORK_ROOT}/error.log`
- **自动记录**: Pipeline 失败时记录详细信息
- **查看最近错误**:
  ```python
  from lab_analysis.error_logger import get_recent_errors
  errors = get_recent_errors(n=10)
  ```

### 添加新模块

1. 在 `lab_analysis/` 创建模块
2. 实现标准接口（接受 `--patient-id`）
3. 在 `pipeline.py` 注册步骤

### 测试

```bash
python -m lab_analysis.data_analyzer --patient-id TEST_ID  # 测试模块
pip install ruff; ruff check lab_analysis/                 # 代码检查
```

## 🤝 贡献

欢迎提交 Issue 和 PR！

1. Fork 仓库
2. 创建分支 (`git checkout -b feature/xxx`)
3. 提交更改 (`git commit -m 'Add xxx'`)
4. 推送 (`git push origin feature/xxx`)
5. 开启 PR

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 👤 作者

**nxz1026** - [GitHub](https://github.com/nxz1026)

## 🙏 致谢

- 智谱 AI、DeepSeek、阿里云

---

⭐ 如果这个项目对您有帮助，请给个 Star！
