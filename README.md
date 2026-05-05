# Lab-Analysis

慢性胰腺炎患者**检验数据自动化分析**流水线：将检验结构化结果、PubMed 文献与证据解读、以及影像（Qwen-VL）印证**多源融合**，生成综合临床 Markdown 报告，并支持上传至飞书云盘。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 功能概览

| 步骤 | 模块 | 说明 |
|------|------|------|
| ① | `lab_analysis.data_loader` | 从 `lab_report_*/metrics.md` 提取指标 → `lab_metrics.csv` / `lab_metrics.json` |
| ② | `lab_analysis.data_analyzer` | 统计分析 + 4 类图表 |
| ③ | `lab_analysis.literature_searcher` | PubMed（E-utilities）检索 |
| ④ | `lab_analysis.literature_interpreter` | DeepSeek 循证医学解读 |
| ⑤ | `lab_analysis.qwen_vl_report_check` | 阿里云 DashScope / Qwen-VL 影像印证 |
| ⑥ | `lab_analysis.gen_final_report` | 三源融合最终报告 |
| ⑦ | `lab_analysis.upload_to_feishu` | 飞书云盘上传（需本机 `lark-cli`） |

统一编排入口：**`lab_analysis.pipeline`**（也可通过根目录 `run_analysis.py` 或命令 `lab-analysis` 调用）。

---

## 仓库结构

```
Lab-Analysis/
├── README.md
├── LICENSE
├── pyproject.toml          # 包元数据与依赖（pip install -e .）
├── requirements.txt        # 与 pyproject 对齐的固定依赖列表
├── .gitignore
├── run_analysis.py         # 根目录快捷入口（开发时常用）
└── lab_analysis/           # Python 包
    ├── __init__.py
    ├── __main__.py         # 支持 python -m lab_analysis
    ├── pipeline.py         # 全流程串联
    ├── patient_id.py       # 诊疗卡号脱敏 encode/decode
    ├── data_loader.py
    ├── data_analyzer.py
    ├── literature_searcher.py
    ├── literature_interpreter.py
    ├── qwen_vl_report_check.py
    ├── gen_final_report.py
    ├── upload_to_feishu.py
    └── ingest_image.py     # 影像/截图入库辅助
```

---

## 环境要求

- **Python** ≥ 3.10  
- **系统字体（图表中文）**：Linux 上常用文泉驿正黑（`WenQuanYi Zen Hei`）；其它系统请自行配置 matplotlib 中文字体。  
- **API 密钥**（写入 `~/.hermes/.env` 或导出为环境变量）：

```bash
DEEPSEEK_API_KEY=sk-xxxx
DASHSCOPE_API_KEY=sk-xxxx
```

- **可选**：飞书上传依赖本机已登录的 [`lark-cli`](https://open.feishu.cn/)（脚本内为子进程调用）。

---

## 安装

在克隆目录下建议使用虚拟环境并**可编辑安装**，便于 `python -m lab_analysis.*` 解析包路径：

```bash
cd Lab-Analysis
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -U pip
pip install -e .
```

仅安装依赖而不装包也可（需自行保证 `PYTHONPATH` 包含仓库根目录）：

```bash
pip install -r requirements.txt
```

---

## 数据目录约定（工作区 `~/wiki`）

流水线假设工作区位于用户主目录下的 **`wiki`**（与历史上 Hermes Agent 部署一致）：

| 用途 | 路径 |
|------|------|
| 原始检验/结构化报告 | `~/wiki/raw/patient_{脱敏ID}/papers/`（`lab_report_*/metrics.md`） |
| 原始影像 | `~/wiki/raw/patient_{脱敏ID}/imaging/` |
| 输出 | `~/wiki/data/{脱敏ID}/{ANALYSIS_TS}/` |

病人 ID 映射（可选）：`~/.hermes/patient_mapping.json`。无映射时使用 `patient_id.encode()` 做数字脱敏。

---

## 使用方式

### 一键全流程（推荐）

在**仓库根目录**执行（会设置 `PYTHONPATH` 并调用各子模块）：

```bash
python run_analysis.py --patient-id <诊疗卡号>
# 等价
python -m lab_analysis --patient-id <诊疗卡号>
```

安装包后也可：

```bash
lab-analysis --patient-id <诊疗卡号>
```

可选参数：`--skip-llm`、`--skip-imaging`。

### 单步调试

在已 `pip install -e .` 的前提下：

```bash
python -m lab_analysis.data_loader --patient-id <脱敏或原始ID>
python -m lab_analysis.data_analyzer --patient-id <ID>
python -m lab_analysis.literature_searcher --topic "慢性胰腺炎 炎症标志物" --n 20
python -m lab_analysis.literature_interpreter --analysis data/analysis_results.json --lit data/literature_results.json
python -m lab_analysis.qwen_vl_report_check --patient-id <ID>
python -m lab_analysis.gen_final_report --patient-id <ID>
python -m lab_analysis.upload_to_feishu --patient-id <ID>
```

> 单步脚本内的相对路径仍相对于 **`~/wiki/data/...`**；全流程由 `pipeline` 注入环境变量 `ANALYSIS_TS` 区分多次运行的时间戳子目录。

---

## 主要输出

| 文件 | 说明 |
|------|------|
| `lab_metrics.csv` / `lab_metrics.json` | 标准化检验数据 |
| `analysis_results.json` | 统计结果 |
| `fig_01`〜`fig_04` *.png | 四类可视化 |
| `literature_results.json` | 文献列表 |
| `literature_interpretation*.md` / `.json` | 循证解读 |
| `mri_report_check_results.json` | 影像印证 |
| `final_integrated_report.md` | 三源融合最终报告 |

---

## 飞书云盘目录（上传后）

```
检验AI分析/
└── {日期}/
    ├── 原始数据/
    ├── 文献参考/
    ├── 中间结果/
    ├── 统计结果/
    └── Final_report.md
```

父文件夹 token 等配置见 `lab_analysis/upload_to_feishu.py`（生产环境请改为环境变量或配置文件，勿提交密钥）。

---

## 许可证

本项目以 [MIT License](LICENSE) 发布。

---

## 相关链接

- 上游仓库：<https://github.com/nxz1026/Lab-Analysis>
