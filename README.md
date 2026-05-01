# Lab-Analysis Pipeline

慢性胰腺炎患者检验数据自动化分析 pipeline，将检验数据、影像数据和文献证据三源融合，生成综合临床报告。

## 目录结构

```
Lab-Analysis/
├── README.md
├── data_loader.py              # 步骤①：从 PDF/TXT 检验报告提取结构化数据
├── data_analyzer.py            # 步骤②：统计分析 + 4类图表生成
├── literature_searcher.py      # 步骤③：PubMed 文献检索
├── literature_interpreter.py   # 步骤④：DeepSeek 循证医学解读
├── qwen_vl_report_check.py     # 步骤⑤：Qwen3-VL 影像印证分析
├── gen_final_report.py         # 步骤⑥：三源融合综合报告
└── upload_to_feishu.py         # 步骤⑦：结果上传飞书云盘
```

## Pipeline 步骤

| 步骤 | 脚本 | 输出 |
|------|------|------|
| ① 数据加载 | `data_loader.py` | `data/lab_metrics.csv` + `data/lab_metrics.json` |
| ② 统计分析 | `data_analyzer.py` | `data/analysis_results.json` + 4张图 |
| ③ 文献检索 | `literature_searcher.py` | `data/literature_results.json` |
| ④ 循证解读 | `literature_interpreter.py` | `data/literature_interpretation.json` |
| ⑤ 影像分析 | `qwen_vl_report_check.py` | `data/mri_report_check_results.json` |
| ⑥ 三源融合 | `gen_final_report.py` | `data/final_integrated_report.md` |
| ⑦ 飞书上云 | `upload_to_feishu.py` | 上传到飞书云盘「检验AI分析」 |

## 环境依赖

```bash
# Python 环境（建议 venv）
~/wiki/.venv/bin/python

# 关键依赖
pandas, numpy, scipy, scikit-learn  # data_analyzer.py
matplotlib, WenQuanYi Zen Hei         # 图表（中文字体）

# API Keys（写入 ~/.hermes/.env）
DEEPSEEK_API_KEY=sk-xxxx
DASHSCOPE_API_KEY=sk-xxxx
```

## 使用方式

Pipeline 通常由 Hermes Agent 调用执行。如需手动运行：

```bash
# 单步执行
python data_loader.py
python data_analyzer.py
python literature_searcher.py --topic "慢性胰腺炎 炎症标志物" --n 20
python literature_interpreter.py --analysis data/analysis_results.json --lit data/literature_results.json
python qwen_vl_report_check.py
python gen_final_report.py
python upload_to_feishu.py
```

## 飞书云盘结构

上传后目录结构：
```
检验AI分析/
└── {日期}/
    ├── 原始数据/         # lab_metrics.csv, lab_metrics.json
    ├── 文献参考/         # literature_results.json
    ├── 中间结果/         # literature_interpretation_report.md
    ├── 统计结果/         # analysis_results_report.md + 4张图
    └── Final_report.md   # 三源融合最终报告
```

## 输入文件

- 检验报告：PDF/TXT，位于 `/root/wiki/data/` 或 `/root/wiki/raw/lab/`
- 影像文件：DICOM/JPEG，位于 `/root/wiki/raw/imaging/`

## 输出文件

- `data/lab_metrics.csv` / `lab_metrics.json` — 标准化检验数据
- `data/analysis_results.json` — 统计分析结果
- `data/fig_01~04.png` — 4类可视化图表
- `data/literature_results.json` — PubMed 文献列表
- `data/literature_interpretation_report.md` — 循证解读（人类可读）
- `data/analysis_results_report.md` — 统计分析报告（人类可读）
- `data/final_integrated_report.md` — 三源融合最终报告
