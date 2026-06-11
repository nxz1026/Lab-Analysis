# Lab-Analysis

> Multi-source Medical Lab Data + Literature Evidence + Imaging Verification Pipeline (with DSPy Prompt Optimization)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Pipeline](https://img.shields.io/badge/Pipeline-9_Steps-success.svg)](#-complete-pipeline-flow)

---

## 📋 Overview

**Lab-Analysis** is a multi-source integration tool designed for **chronic disease clinical data analysis** (chronic pancreatitis and similar), running the full clinical pathway: *lab tests → trend analysis → literature evidence → imaging verification → integrated report* — "ingest once, produce a structured clinical analysis report automatically".

### Use Cases

- 🏥 **Clinical Research**: Long-term lab data trend analysis for chronic pancreatitis, tumor markers, etc.
- 🧪 **Single Case Consultation**: Cross-validation of multi-source data (lab + literature + imaging)
- 📚 **Teaching / Case Review**: Explainable linkage between literature evidence and clinical data
- 🤖 **LLM Application Research**: Prompt engineering and comparative evaluation for medical LLMs

### Core Value

| Dimension | Value |
|------|------|
| **Multi-source Integration** | Lab data (CSV/JSON) + PubMed literature + MRI/DICOM imaging + text reports, three-source consistency assessment |
| **Automation** | One-click 9-step pipeline with traceable intermediate artifacts |
| **Interpretability** | 7 statistical charts + full logs + error traceback |
| **LLM Enhancement** | DSPy integration, auto-optimized prompts, supports standard vs. optimized dual-mode comparison |
| **Extensibility** | Modular design, new analysis dimensions only need to implement the standard interface |

---

## ✨ Core Features

### 1. Data Ingestion (Lab + Imaging + Literature Preprocessing)
- Lab report image OCR (Zhipu GLM-4V)
- DICOM image extraction and series renaming
- MRI text report parsing
- Automatic patient ID de-identification

### 2. Statistical Analysis (7 Charts)
- Trend regression, correlation heatmap
- Inflammation assessment, anomaly detection
- Moving average, coefficient of variation, comprehensive dashboard

### 3. Literature Search & Evidence-Based Interpretation
- Automated PubMed search (MeSH + free-text combinations)
- DeepSeek AI evidence-based interpretation
- 🧠 **DSPy Optimized**: Hierarchical pathophysiology analysis with built-in confidence scoring

### 4. Imaging Report Check
- Qwen-VL model validates MRI reports
- Cross-check imaging findings against lab data
- 🧠 **DSPy Optimized**: Structured extraction of imaging signs

### 5. Integrated Report Generation
- Three-source consistency assessment (lab / literature / imaging)
- 9-section structured clinical diagnostic report
- 🧠 **DSPy Optimized**: Automatic section organization, differential diagnosis supplementation

### 6. Local Archive & Upload Backup
- Date-organized local archive
- Feishu cloud auto-upload (experimental, see `lark-cli` integration)

---

## 🧠 DSPy Enhancement

This project integrates the **DSPy** (Declarative Self-improving Python) framework, implementing a "standard mode + DSPy optimized mode" dual-track on 4 LLM-driven core modules — both stable production and automated prompt iteration are supported.

### 4 DSPy Modules

| Module | Responsibility | Standard Version | DSPy Version | Save Path |
|------|------|--------|---------|----------|
| `literature_interpreter` | Literature evidence-based interpretation | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` | `data/<id>/<ts>/03_literature/dspy_prompts/` |
| `mri_analyzer` | Imaging report analysis | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` | `data/<id>/<ts>/dspy_prompts/` |
| `final_report_generator` | Integrated report generation | `gen_final_report.py` | `dspy_modules/final_report_generator.py` | `data/<id>/<ts>/04_reports/dspy_prompts/` |
| `lab_data_extractor` | Lab data extraction | `extract_lab_data.py` | `dspy_modules/lab_data_extractor.py` | `data/<id>/<ts>/dspy_prompts/` |

### Dual-Mode Operation

Each dual-mode script (e.g. `literature_interpreter_dspy.py`) supports:
- **Standard Mode**: Hand-crafted prompt template + one-shot LLM call
- **DSPy Mode**: Load compiled module (if exists) / dynamically generate prompts + auto call

CLI arguments:
```bash
# Standard mode
python -m lab_analysis.literature_interpreter_dspy --patient-id <id>

# DSPy optimized mode
python -m lab_analysis.literature_interpreter_dspy --patient-id <id> --use-dspy
```

### Prompt Extraction & Comparison Tools

#### `lab_analysis/dspy_modules/prompt_inspector.py`

Prompt extractor for DSPy modules, providing 3 core functions:

```python
from lab_analysis.dspy_modules.prompt_inspector import (
    extract_module_prompts,      # Extract prompt info from all predictors in a module
    save_prompts_to_json,         # Save as JSON
    save_prompts_to_markdown,     # Save as readable Markdown
)

prompts_data = extract_module_prompts(my_dspy_module, "literature_interpreter")
save_prompts_to_json("literature_interpreter", prompts_data, output_dir)
save_prompts_to_markdown("literature_interpreter", prompts_data, output_dir)
```

Extracted content: Signature instructions, input/output field descriptions, few-shot demos, reconstructed DSPy internal full prompt.

#### `examples/dspy_prompt_comparison.py`

Standard vs. DSPy mode prompt comparison tool, generating Markdown + JSON dual-format reports:

```bash
python examples/dspy_prompt_comparison.py --data-dir data/<patient_id>/<timestamp>
```

Output: `data/<id>/<ts>/reports/dspy_prompt_comparison.{md,json}`, containing:
- Dual-mode prompt length, sections, few-shot count comparison
- Key improvement analysis (length_ratio, length_increase, etc.)
- Full prompt text snapshots

#### `examples/test_dspy_prompt_e2e.py`

End-to-end validation script, runnable directly to verify the full saving and comparison mechanism:

```bash
python examples/test_dspy_prompt_e2e.py
```

---

## 📂 Project Structure

```
Lab-Analysis/
├── lab_analysis/                     # Core code package
│   ├── pipeline.py                   # Pipeline unified entry
│   ├── ingest_data.py                # ① Data ingestion (lab images / DICOM / MRI reports)
│   ├── data_loader.py                # ③ Data loading & preprocessing
│   ├── data_analyzer.py              # ④ Statistical analysis (7 charts)
│   ├── literature_searcher.py        # ⑤ PubMed literature search
│   ├── literature_interpreter.py     # ⑥ Literature interpretation (standard)
│   ├── literature_interpreter_dspy.py    # ⑥ Literature interpretation (dual-mode)
│   ├── qwen_vl_report_check.py       # ⑦ Imaging report check (standard)
│   ├── qwen_vl_report_check_dspy.py  # ⑦ Imaging report check (dual-mode)
│   ├── gen_final_report.py           # ⑧ Integrated report generation (standard)
│   ├── gen_final_report_dspy.py      # ⑧ Integrated report generation (dual-mode)
│   ├── extract_lab_data.py           # Lab data extraction (OCR)
│   ├── vision_extractor.py           # Vision AI single-image extraction
│   ├── batch_vision_extract.py       # Batch vision extraction
│   ├── organize_local_files.py       # ⑨ Local file organization
│   ├── upload_to_feishu_backup.py    # Feishu upload backup implementation
│   ├── patient_id.py                 # Patient ID de-identification
│   ├── error_logger.py               # Error log recorder
│   ├── utils.py                      # Common utilities
│   └── dspy_modules/                 # 🧠 DSPy optimized modules
│       ├── __init__.py               # Package exports
│       ├── literature_interpreter.py # DSPy literature interpretation
│       ├── mri_analyzer.py           # DSPy imaging analysis
│       ├── final_report_generator.py # DSPy report generation
│       ├── lab_data_extractor.py     # DSPy lab data extraction
│       └── prompt_inspector.py       # DSPy prompt extractor
├── examples/                         # Examples & utility scripts
│   ├── dspy_quickstart.py            # DSPy quickstart
│   ├── dspy_prompt_comparison.py     # Prompt comparison tool
│   ├── prepare_dspy_training_data.py # Training data preparation
│   ├── collect_dspy_training_data.py # Training data collection
│   ├── compile_dspy_module.py        # DSPy module compilation
│   ├── monitor_dspy_performance.py   # DSPy performance monitoring
│   ├── test_dspy_basic.py            # DSPy basic tests
│   ├── test_dspy_e2e.py              # DSPy end-to-end tests
│   ├── test_dspy_llm.py              # DSPy LLM connection tests
│   ├── test_dspy_prompt_e2e.py       # DSPy prompt end-to-end tests
│   ├── test_prompt_extraction.py     # Prompt extraction unit tests
│   ├── test_dashscope_compatibility.py # DashScope compatibility tests
│   └── quick_ingest.py               # Quick data ingestion
├── docs/                             # Supplementary documentation
│   ├── DSPY_INTEGRATION.md           # DSPy integration technical scheme
│   └── DSPY_USAGE.md                 # DSPy usage guide
├── models/                           # Compiled model storage
│   └── dspy/
│       └── literature_interpreter_compiled.json
├── raw/                              # Raw data
│   └── Origin_data/                  # Raw files to process (lab_*.jpg / mri_*.jpg / export_*.zip)
├── data/                             # Analysis results (organized by patient ID & timestamp)
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
├── local_upload/                     # Local archive (organized by date)
│   └── {YYYY-MM-DD}/
│       ├── 原始数据/                  # Raw data
│       ├── 文献参考/                  # Literature reference
│       ├── 中间结果/                  # Intermediate results
│       ├── 统计结果/                  # Statistical results
│       └── final_integrated_report.md
├── .env                              # Environment variables (not committed)
├── .env.example                      # Environment variable example
├── pyproject.toml                    # Project config & dependencies
└── run_analysis.py                   # Run script entry
```

---

## 🔁 Complete Pipeline Flow

`python -m lab_analysis --patient-id <id>` will execute the following 9 steps in order. Failures at any step are logged; key steps support `--skip-xxx` to skip.

| Step | Name | Script Module | Input | Output | DSPy Mapping |
|------|------|------|------|------|----------|
| ① | **Data Ingestion** | `ingest_data.py` | `raw/Origin_data/` lab images / DICOM / MRI reports | `raw/patient_<deid>/{lab,imaging,papers}/` | — |
| ② | **Pre-check** | `pipeline.check_patient_data` | `raw/patient_<deid>/` directory | Validation report / exit on failure | — |
| ③ | **Data Loading** | `data_loader.py` | `raw/patient_<deid>/papers/lab_report_*/metrics.md` | `data/<id>/<ts>/lab_metrics.csv` + `.json` | — |
| ④ | **Statistical Analysis** | `data_analyzer.py` | lab_metrics.csv | 7 charts `fig_01~07.png` + `analysis_results_report.md` | — |
| ⑤ | **Literature Search** | `literature_searcher.py` | Lab items + key indicators | `literature_results.md` (PubMed abstracts) | — |
| ⑥ | **Evidence Interpretation** | `literature_interpreter.py` / `..._dspy.py` | `literature_results.md` + lab_metrics | `literature_interpretation.md` + `dspy_prompts/` | `dspy_modules/literature_interpreter` |
| ⑦ | **Imaging Analysis** | `qwen_vl_report_check.py` / `..._dspy.py` | MRI report + lab_metrics | `mri_report_check_results.md` + `dspy_prompts/` | `dspy_modules/mri_analyzer` |
| ⑧ | **Integrated Report** | `gen_final_report.py` / `..._dspy.py` | ④⑤⑥⑦ all artifacts | `final_integrated_report.md` + `dspy_prompts/` | `dspy_modules/final_report_generator` |
| ⑨ | **Local Archive** | `organize_local_files.py` | `data/<id>/<ts>/` all artifacts | `local_upload/<YYYY-MM-DD>/` | — |

### Flow Diagram

```
[① Data Ingestion] → [② Pre-check] → [③ Data Loading] → [④ Statistical Analysis]
                                                              ↓
[⑨ Local Archive] ← [⑧ Integrated Report] ← [⑦ Imaging Analysis] ← [⑥ Evidence Interpretation] ← [⑤ Literature Search]
```

> Steps ⑥⑦⑧ use the corresponding `_dspy.py` dual-mode scripts when `--use-dspy` is set, and automatically save the optimized prompts.

---

## 🛠️ Installation & Configuration

### Requirements

- **Python**: 3.10+
- **OS**: Windows 10/11, macOS, Linux
- **Disk**: ≥ 5 GB (including DICOM extraction cache)

### 1. Clone & Install

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .
```

### 2. Install DSPy Dependencies (Required for DSPy Mode)

```bash
pip install "dspy-ai>=3.2" python-dotenv
```

### 3. Configure Environment Variables

Copy the example and fill in real keys:

```bash
cp .env.example .env
```

`.env` key fields:

| Variable | Required | Purpose | Provider |
|------|------|------|--------|
| `WORK_ROOT` | ✅ | Project working root (default: current dir) | — |
| `DEEPSEEK_API_KEY` | ✅ | Literature interpretation / report generation | DeepSeek |
| `DASHSCOPE_API_KEY` | ✅ | Imaging analysis (Qwen-VL) | Alibaba Cloud Bailian |
| `ZHIPU_API_KEY` | ⭕ | Lab report OCR | Zhipu AI |
| `FEISHU_FOLDER_TOKEN` | ⭕ | Feishu cloud upload (experimental) | Feishu Open Platform |
| `ANALYSIS_TS` | ⭕ | Specify timestamp (for single-step debugging) | — |

`.env` example:

```env
WORK_ROOT=E:/2026Workplace/Code/Lab-Analysis
DEEPSEEK_API_KEY=sk-xxxxxxxx
DASHSCOPE_API_KEY=sk-xxxxxxxx
ZHIPU_API_KEY=xxxxxxxx.xxxxxxxx
FEISHU_FOLDER_TOKEN=xxxxxxxx
```

---

## 🚀 Run Examples

### Run the Full Pipeline with One Command

```bash
# Standard mode (default)
python -m lab_analysis --patient-id 846552421134373347

# Enable DSPy optimized mode (overrides ⑥⑦⑧)
python -m lab_analysis --patient-id 846552421134373347 --use-dspy
```

### Skip Specific Steps

```bash
python -m lab_analysis --patient-id ID --skip-llm      # Skip ⑥ literature interpretation
python -m lab_analysis --patient-id ID --skip-imaging  # Skip ⑦ imaging analysis
python -m lab_analysis --patient-id ID --skip-ingest   # Skip ① data ingestion
```

### Run a Single Step (for Debugging)

```bash
python -m lab_analysis.data_loader --patient-id ID
python -m lab_analysis.data_analyzer --patient-id ID
python -m lab_analysis.literature_searcher --patient-id ID
python -m lab_analysis.literature_interpreter_dspy --patient-id ID --use-dspy
python -m lab_analysis.qwen_vl_report_check_dspy --patient-id ID --use-dspy
python -m lab_analysis.gen_final_report_dspy --patient-id ID --use-dspy
```

> When running ⑥⑦⑧ separately, set the `ANALYSIS_TS` environment variable to point to the existing timestamp directory:
> ```powershell
> $env:ANALYSIS_TS="20260611_111343"
> python -m lab_analysis.literature_interpreter_dspy --patient-id ID --use-dspy
> ```

### DSPy Training & Compilation

```bash
# Prepare training data
python examples/prepare_dspy_training_data.py

# Compile optimized literature interpretation module
python examples/compile_dspy_module.py

# End-to-end DSPy test
python examples/test_dspy_e2e.py
```

### Prompt Comparison Report Generation

```bash
# 1. Run both modes first; artifacts will land in data/<id>/<ts>/
python -m lab_analysis --patient-id ID --skip-ingest --skip-llm
python -m lab_analysis.literature_interpreter_dspy --patient-id ID
python -m lab_analysis.literature_interpreter_dspy --patient-id ID --use-dspy
# 2. Generate comparison report
python examples/dspy_prompt_comparison.py --data-dir data/<id>/<ts>
```

---

## 📊 Output File Description

### Directory Structure

```
data/{patient_id}/{timestamp}/
├── lab_metrics.csv                       # Lab data (CSV, analysis input)
├── lab_metrics.json                      # Lab data (JSON, de-identified)
├── fig_01_trend_regression.png           # Trend regression
├── fig_02_correlation_heatmap.png        # Correlation heatmap
├── fig_03_inflammation_assessment.png    # Inflammation assessment
├── fig_04_anomaly_detection.png          # Anomaly detection
├── fig_05_stability_analysis.png         # Stability analysis
├── fig_06_trend_smoothing.png            # Trend smoothing
├── fig_07_comprehensive_dashboard.png    # Comprehensive dashboard
├── analysis_results_report.md            # Detailed statistical analysis report
├── literature_results.md                 # PubMed search results
├── literature_interpretation.md          # Literature interpretation (standard / DSPy)
├── mri_report_check_results.md           # Imaging consistency report
├── final_integrated_report.md            # Final integrated report
├── reports/                              # Comparison reports
│   ├── dspy_prompt_comparison.md         # Prompt comparison (Markdown)
│   └── dspy_prompt_comparison.json       # Prompt comparison (JSON)
├── 03_literature/                        # Literature interpretation working dir
│   └── dspy_prompts/
│       ├── literature_interpreter_standard_prompt.txt
│       ├── literature_interpreter_dspy_prompts.json
│       └── literature_interpreter_dspy_prompts.md
├── 04_reports/                           # Report generation working dir
│   └── dspy_prompts/
│       ├── final_report_standard_prompt.txt
│       ├── final_report_dspy_prompts.json
│       └── final_report_dspy_prompts.md
└── dspy_prompts/                         # Imaging / lab prompts
    ├── mri_analyzer_standard_prompt.txt
    ├── mri_analyzer_dspy_prompts.json
    ├── mri_analyzer_dspy_prompts.md
    ├── lab_data_extractor_dspy_prompts.json
    └── lab_data_extractor_dspy_prompts.md
```

### `dspy_prompt_comparison.md` Content Sample

```markdown
# DSPy Prompt Comparison Report

## Module: literature_interpreter

| Dimension | Standard Mode | DSPy Mode |
|------|---------|----------|
| Prompt Length | 975 chars | 1546 chars (estimated) |
| Few-shot Count | 0 | 0 |
| Length Improvement | — | 1.59x (+571 chars) |

## Key Improvements
- DSPy auto-appends ChainOfThought reasoning instructions
- More structured field descriptions (Pathological → Output)
- Clearer templated output format guidance
```

---

## 📚 Advanced Documentation

- [docs/DSPY_INTEGRATION.md](docs/DSPY_INTEGRATION.md) — DSPy integration technical details
- [docs/DSPY_USAGE.md](docs/DSPY_USAGE.md) — DSPy usage guide
- [examples/dspy_quickstart.py](examples/dspy_quickstart.py) — DSPy quickstart example

---

## 🛠️ Tech Stack

| Domain | Choice |
|------|------|
| Data Processing | pandas, numpy, scipy |
| Machine Learning | scikit-learn |
| Visualization | matplotlib |
| Image Processing | Pillow, pydicom |
| OCR / Vision | Zhipu GLM-4V, Alibaba Qwen-VL |
| Text Generation | DeepSeek API, OpenAI-compatible protocol |
| LLM Optimization | DSPy 3.2+ (BootstrapFewShot / MIPROv2) |
| Literature Search | PubMed E-utilities API |
| Error Handling | tenacity (retry) + self-developed error_logger |

---

## 📝 Development Guide

### Code Standards

- PEP 8 + type hints
- Paths use `pathlib.Path` uniformly
- Prefer `WORK_ROOT` + relative paths
- Dual-mode scripts named `<module>_dspy.py`

### Add a New Module

1. Create the module in `lab_analysis/`
2. Implement the `main_with_args(args)` standard interface
3. Register it in `pipeline.py` via `run_step()`
4. If it involves LLM, implement the DSPy version and integrate with `prompt_inspector` synchronously

### Dependency Management

```bash
pip install -e .                    # Install
pip install pip-tools               # Optional: generate lock file
pip-compile pyproject.toml -o requirements.lock
```

> ⚠️ All dependencies are declared in `pyproject.toml`. Do not manually create `requirements.txt`.

### Error Logging

- Log location: `{WORK_ROOT}/error.log`
- Auto-capture: When any pipeline step fails, record the command, return code, and stack trace summary
- View recent errors:
  ```python
  from lab_analysis.error_logger import get_recent_errors
  errors = get_recent_errors(n=10)
  ```

### Testing

```bash
# Unit / integration tests
python examples/test_dspy_prompt_e2e.py
python examples/test_dspy_e2e.py

# Code linting
pip install ruff
ruff check lab_analysis/
```

---

## 🤝 Contributing

Issues and PRs are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/xxx`)
3. Commit your changes (`git commit -m 'feat: add xxx'`)
4. Push (`git push origin feature/xxx`)
5. Open a Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details

---

## 👤 Author

**nxz1026** — [GitHub @nxz1026](https://github.com/nxz1026)

---

## 🙏 Acknowledgments

- DeepSeek, Zhipu AI, Alibaba Cloud Bailian (Qwen-VL) for LLM capabilities
- Stanford NLP's [DSPy](https://dspy.ai/) framework
- PubMed E-utilities open API

---

⭐ If this project helps you, please give it a Star!
