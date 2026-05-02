# Lab-Analysis Pipeline

## 项目概述

慢性胰腺炎患者检验数据自动化分析 pipeline，将检验数据、影像数据和文献证据三源融合，生成综合临床报告。

## 技术栈

- **语言**：Python 3.11
- **依赖管理**：venv（`~/.venv/bin/python`）
- **关键库**：pandas, numpy, scipy, scikit-learn, matplotlib
- **外部集成**：DeepSeek API（循证解读）、DashScope API（Qwen-VL 影像分析）、PubMed 文献检索、飞书云盘上传

## 目录结构

```
/workspace/projects/
├── run_analysis.py          # Pipeline 统一入口
├── data_loader.py           # 步骤①：从 PDF/TXT 检验报告提取结构化数据
├── data_analyzer.py         # 步骤②：统计分析 + 4类图表生成
├── literature_searcher.py   # 步骤③：PubMed 文献检索
├── literature_interpreter.py # 步骤④：DeepSeek 循证医学解读
├── qwen_vl_report_check.py  # 步骤⑤：Qwen3-VL 影像印证分析
├── gen_final_report.py      # 步骤⑥：三源融合综合报告
├── upload_to_feishu.py      # 步骤⑦：结果上传飞书云盘
└── .coze                    # Coze 项目配置
```

## Pipeline 步骤

| 步骤 | 脚本 | 输出 |
|------|------|------|
| ① 数据加载 | `data_loader.py` | `data/{patient_id}/lab_metrics.csv` + `.json` |
| ② 统计分析 | `data_analyzer.py` | `analysis_results.json` + 4张图 |
| ③ 文献检索 | `literature_searcher.py` | `literature_results.json` |
| ④ 循证解读 | `literature_interpreter.py` | `literature_interpretation.json` |
| ⑤ 影像分析 | `qwen_vl_report_check.py` | `mri_report_check_results.json` |
| ⑥ 三源融合 | `gen_final_report.py` | `final_integrated_report.md` |
| ⑦ 飞书上云 | `upload_to_feishu.py` | 上传到飞书云盘 |

## 关键入口

- **Pipeline 入口**：`python run_analysis.py --patient-id <诊疗卡号>`
- **运行环境**：`~/wiki/.venv/bin/python`
- **数据路径**：`~/wiki/raw/{patient_id}/`（lab/imaging/papers 子目录）
- **输出路径**：`~/wiki/data/{patient_id}/`

## 用户偏好与长期约束

1. 使用 venv 虚拟环境（`~/.venv/bin/python`），不混用系统 Python
2. 脚本硬编码路径为 `~/wiki` 前缀
3. API Keys 存储在 `~/.hermes/.env`
4. 中文字体依赖 WenQuanYi Zen Hei（matplotlib 使用）

## 常见问题和预防

- **路径依赖**：所有脚本依赖 `~/wiki` 目录结构，需确保软链接或目录存在
- **API 配额**：文献检索和 LLM 解读依赖外部 API，注意配额限制
- **数据格式**：data_loader 输出 CSV 和 JSON 两种格式供后续步骤使用
