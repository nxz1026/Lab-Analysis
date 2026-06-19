# Lab-Analysis

> Multi-source Medical Lab Data + Literature Evidence + Imaging Verification Pipeline (with DSPy Prompt Optimization)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/nxz1026/Lab-Analysis/actions/workflows/tests.yml/badge.svg)](https://github.com/nxz1026/Lab-Analysis/actions/workflows/tests.yml)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Pipeline](https://img.shields.io/badge/Pipeline-9_Steps-success.svg)](#complete-pipeline-flow)

---

## Overview

**Lab-Analysis** is a multi-source integration tool designed for **chronic disease clinical data analysis** (chronic pancreatitis and similar), covering the full clinical pathway: *lab tests → trend analysis → literature evidence → imaging verification → integrated report*. Ingest once, produce a structured clinical analysis report automatically.

### Use Cases

- **Clinical Research**: Long-term lab data trend analysis, inflammation stage progression
- **Single Case Consultation**: Cross-validation of lab + literature + imaging data
- **Teaching / Case Review**: Explainable linkage between literature evidence and clinical data
- **LLM Application Research**: Prompt engineering and comparative evaluation for medical LLMs

### Key Features

| Dimension | Description |
|-----------|-------------|
| **Multi-source Integration** | Lab data (CSV/JSON) + PubMed literature + MRI/DICOM imaging + text reports, with three-source consistency assessment |
| **One-click Automation** | 9-step pipeline runs end-to-end; all intermediate artifacts are traceable |
| **Interpretability** | 7 statistical charts + full logs + error traceback |
| **LLM Enhancement** | DSPy integration with auto-optimized prompts; supports standard vs. optimized dual-mode comparison |
| **Cross-platform** | Windows / Linux auto-adaptation, console encoding auto-fix |
| **Extensibility** | Modular design; add new analysis dimensions by implementing a standard interface |

---

## Complete Pipeline Flow

```bash
python -m lab_analysis
```

At runtime, the program interactively prompts for a valid Chinese ID card number, then executes the following 9 steps in order. Key steps support `--skip-xxx` to skip.

| Step | Name | Module | Input → Output |
|------|------|--------|----------------|
| ① | **Data Ingestion** | `ingest_data.py` | `raw/Origin_data/` lab images / DICOM / MRI reports → `raw/patient_<deid>/` |
| ② | **Pre-check** | `pipeline.steps` | Validate `raw/patient_<deid>/` directory structure → pass/fail |
| ③ | **Data Loading** | `data_loader.py` | `.../metrics.md` → `lab_metrics.csv` + `.json` |
| ④ | **Statistical Analysis** | `analysis/run` | `lab_metrics.csv` → 7 charts + `analysis_results_report.md` |
| ⑤ | **Literature Search** | `literature_searcher.py` | Lab items + key indicators → PubMed abstracts `.md` |
| ⑤b | **Evidence Grading** (optional) | `literature_filter.py` | `literature_results.json` → `literature_results.filtered.json` (top-k ranked by evidence tier) |
| ⑥ | **Evidence Interpretation** | `literature_interpreter(_dspy).py` | Literature abstracts + lab data → interpretation report + DSPy prompt |
| ⑦ | **Imaging Analysis** | `qwen_vl_report_check(_dspy).py` | MRI report + lab data → consistency report + DSPy prompt |
| ⑧ | **Integrated Report** | `gen_final_report(_dspy).py` | ④⑤⑥⑦ artifacts → 9-section integrated report + DSPy prompt |
| ⑨ | **Local Archive** | `organize_local_files.py` | `data/<id>/<ts>/` → `local_upload/<YYYY-MM-DD>/` |

> Steps ⑥⑦⑧ automatically switch to DSPy optimized mode when `--use-dspy` is set, and save the optimized prompts for comparison.

### Flow Diagram

```
[① Data Ingestion] → [② Pre-check] → [③ Data Loading] → [④ Statistical Analysis]
                                                              ↓
[⑨ Local Archive] ← [⑧ Integrated Report] ← [⑦ Imaging Analysis] ← [⑥ Evidence Interpretation] ← [⑤ Literature Search]
```

---

## Project Structure

```
Lab-Analysis/
├── lab_analysis/                         # Core code package
│   ├── __init__.py                       #   Package entry (auto platform adaptation)
│   ├── __main__.py                       #   python -m entry point
│   ├── pipeline.py                       # [Legacy] delegates to pipeline/ subpackage
│   ├── pipeline/                         #   Pipeline orchestration
│   │   ├── cli.py                        #     CLI argument parsing
│   │   ├── steps.py                      #     Sub-steps (check / subprocess / logging)
│   │   ├── ingest.py                     #     Auto data ingestion
│   │   └── run.py                        #     Main orchestrator
│   ├── analysis/                         #   Statistical analysis subpackage
│   │   ├── _base.py                      #     Constants / reference ranges / plotting utils
│   │   ├── _compute.py                   #     Pure computation (regression / classification / outlier detection)
│   │   ├── charts.py                     #     7 chart functions
│   │   └── run.py                        #     Orchestrator + Markdown report generation
│   ├── ingest_data.py                    # ① Data ingestion implementation
│   ├── data_loader.py                    # ③ Data loading
│   ├── data_analyzer.py                  # [Legacy] delegates to analysis/ subpackage
│   ├── literature_searcher.py            # ⑤ PubMed literature search
│   ├── evidence_grader.py                # ⑤b Evidence tier scoring (5 dims + 3 scenarios)
│   ├── literature_filter.py             # ⑤b CLI wrapper (pipeline step entry)
│   ├── literature_interpreter.py         # ⑥ Literature interpretation (standard)
│   ├── literature_interpreter_dspy.py    # ⑥ Literature interpretation (DSPy dual-mode)
│   ├── qwen_vl_report_check.py           # ⑦ Imaging check (standard)
│   ├── qwen_vl_report_check_dspy.py      # ⑦ Imaging check (DSPy dual-mode)
│   ├── gen_final_report.py               # ⑧ Report generation (standard)
│   ├── gen_final_report_dspy.py          # ⑧ Report generation (DSPy dual-mode)
│   ├── extract_lab_data.py               # Lab report OCR extraction
│   ├── vision_extractor.py               # Single-image Vision AI extraction
│   ├── batch_vision_extract.py           # Batch vision extraction
│   ├── llm_client.py                     # Unified LLM API client (DeepSeek / Zhipu / DashScope)
│   ├── patient_id.py                     # AES-GCM ID card de-identification & validation
│   ├── error_logger.py                   # Error logging
│   ├── utils.py                          # Common utilities (platform adaptation / paths / JSON parsing)
│   ├── organize_local_files.py           # ⑨ Local archive
│   ├── upload_to_feishu_backup.py        # Feishu backup (experimental)
│   └── dspy_modules/                     # DSPy optimized modules
│       ├── __init__.py
│       ├── literature_interpreter.py     #   DSPy literature interpretation
│       ├── mri_analyzer.py               #   DSPy imaging analysis
│       ├── final_report_generator.py     #   DSPy report generation
│       ├── lab_data_extractor.py         #   DSPy lab data extraction
│       └── prompt_inspector.py           #   DSPy prompt extraction tool
├── tests/                                # pytest test suite
│   ├── conftest.py                       #   Test configuration (env / fixtures)
│   ├── test_utils.py                     #   Utility function tests
│   ├── test_patient_id.py                #   ID de-identification / validation tests
│   └── test_extract_lab_data.py          #   Lab data extraction tests
├── examples/                             # Examples & tools
│   ├── dspy_quickstart.py
│   ├── dspy_prompt_comparison.py         #   Prompt comparison report generator
│   ├── compile_dspy_module.py            #   DSPy module compilation
│   ├── test_dspy_e2e.py                  #   DSPy end-to-end test
│   ├── test_dspy_prompt_e2e.py           #   Prompt save/compare verification
│   └── ...
├── docs/                                 # Supplementary docs
│   ├── DSPY_INTEGRATION.md               #   DSPy integration technical details
│   └── DSPY_USAGE.md                     #   DSPy usage guide
├── models/dspy/                          # Compiled DSPy models
├── raw/                                  # Raw data
│   └── Origin_data/                      #   Files to process (lab_*.jpg / mri_*.jpg / export_*.zip)
├── data/                                 # Analysis results (by patient + timestamp)
├── local_upload/                         # Local archive (by date)
├── .github/workflows/                    # CI configuration
│   ├── tests.yml                         #   Matrix tests (py3.10~3.12)
│   └── ci.yml                            #   Quick import check
├── .env.example                          # Environment variable example
├── pyproject.toml                        # Project configuration & dependencies
└── run_analysis.py                       # Quick start script
```

---

## Installation & Configuration

### Requirements

- **Python**: 3.10+
- **OS**: Windows 10/11, macOS, Linux
- **Disk**: ≥ 5 GB (including DICOM extraction cache)

### Installation

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .
pip install "dspy-ai>=3.2" python-dotenv   # Optional: for DSPy mode
```

### Environment Variables

```bash
cp .env.example .env
```

| Variable | Required | Purpose | Provider |
|----------|----------|---------|----------|
| `WORK_ROOT` | Yes | Project working root (default: current dir) | — |
| `DEEPSEEK_API_KEY` | Yes | Literature interpretation / report generation | DeepSeek |
| `DASHSCOPE_API_KEY` | Yes | Imaging analysis (Qwen-VL) | Alibaba Cloud Bailian |
| `ZHIPU_API_KEY` | No | Lab report OCR (GLM-4V) | Zhipu AI |
| `FEISHU_FOLDER_TOKEN` | No | Feishu cloud upload (experimental) | Feishu Open Platform |

---

## Usage

### Run Full Pipeline

```bash
# Standard mode — interactive ID card prompt
python -m lab_analysis

# DSPy optimized mode
python -m lab_analysis --use-dspy
```

### Skip Steps

```bash
python -m lab_analysis --skip-ingest   # Skip data ingestion
python -m lab_analysis --skip-llm      # Skip literature interpretation
python -m lab_analysis --skip-imaging  # Skip imaging analysis
```

### Debug a Single Step

```bash
python -m lab_analysis.data_loader --id-card <deid>
python -m lab_analysis.data_analyzer --id-card <deid>
python -m lab_analysis.literature_interpreter_dspy --id-card <deid> --use-dspy
```

For steps ⑥⑦⑧, set `ANALYSIS_TS` to an existing timestamp directory:

```powershell
$env:ANALYSIS_TS="20260611_111343"
python -m lab_analysis.literature_interpreter_dspy --id-card <deid> --use-dspy
```

---

## Output Artifacts

```
data/{patient_id}/{timestamp}/
├── lab_metrics.csv                       # Lab data (CSV, analysis input)
├── lab_metrics.json                      # Lab data (JSON, de-identified)
├── fig_01_trend_regression.png           # Trend regression
├── fig_02_correlation_heatmap.png        # Correlation heatmap
├── fig_03_inflammation_status.png        # Inflammation staging
├── fig_04_abnormal_indicators.png        # Abnormal indicator annotation
├── fig_05_moving_average.png             # Moving average
├── fig_06_cv_stability.png              # CV stability heatmap
├── fig_07_zscore_distribution.png        # Z-score distribution
├── analysis_results_report.md            # Statistical analysis report
├── literature_results.md                 # PubMed search results
├── literature_interpretation.md          # Literature interpretation
├── mri_report_check_results.md           # Imaging consistency report
├── final_integrated_report.md            # Final integrated report
├── reports/dspy_prompt_comparison.{md,json}  # Prompt comparison report
└── dspy_prompts/                         # DSPy prompt snapshots
    ├── *_standard_prompt.txt
    ├── *_dspy_actual_prompt.txt
    └── *_dspy_prompts.{json,md}
```

---

## DSPy Enhancement

This project integrates **DSPy** (Declarative Self-improving Python), implementing a "standard mode + DSPy optimized mode" dual-track on 4 LLM-driven modules.

### Step ⑤b Evidence Grading

For details see [docs/EVIDENCE_GRADING.md](docs/EVIDENCE_GRADING.md).

Summary:
- 5 independent dimensions (topic_match / evidence_level / recency / sample_size / parse_quality)
- 3 scenario weight presets: `early_diagnosis` / `differential_diagnosis` / `prognosis`
- S/A/B/C tier bands
- Pure rule-based scoring — no LLM, fully reproducible and testable

CLI flags:
```
--skip-lit-filter              Skip step ⑤b
--lit-filter-scenario {early_diagnosis|differential_diagnosis|prognosis}
                              Default differential_diagnosis
--lit-filter-top-k INT         Keep top k papers, default 8
```

### 4 DSPy Modules

| Module | Responsibility | Standard Version | DSPy Version |
|--------|---------------|------------------|--------------|
| `literature_interpreter` | Evidence-based interpretation | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` |
| `mri_analyzer` | Imaging report analysis | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` |
| `final_report_generator` | Integrated report generation | `gen_final_report.py` | `dspy_modules/final_report_generator.py` |
| `lab_data_extractor` | Lab data extraction | `extract_lab_data.py` | `dspy_modules/lab_data_extractor.py` |

### Prompt Auto-Extraction & Comparison

After each inference, DSPy modules automatically save both standard prompts and DSPy actual prompts (including ChainOfThought format + few-shot examples) side by side for diff comparison.

Generate comparison report:

```bash
python examples/dspy_prompt_comparison.py --data-dir data/<deid>/<ts>
```

---

## Tech Stack

| Domain | Choice |
|--------|--------|
| Data Processing | pandas, numpy, scipy |
| Machine Learning | scikit-learn |
| Visualization | matplotlib |
| Image Processing | Pillow, pydicom |
| OCR / Vision | Zhipu GLM-4V, Alibaba Qwen-VL |
| Text Generation | DeepSeek API, OpenAI-compatible protocol |
| LLM Optimization | DSPy 3.2+ (BootstrapFewShot / MIPROv2) |
| Literature Search | PubMed E-utilities API |
| Error Handling | tenacity (retry) + self-developed error_logger |
| Testing | pytest, pytest-cov |
| CI | GitHub Actions (Python 3.10~3.12 matrix) |

---

## Development Guide

### Testing

```bash
pip install -e ".[dev]"
python -m pytest                # Run all tests
python -m pytest -v --cov       # With coverage
ruff check lab_analysis/        # Code style check
```

### Code Standards

- PEP 8 + type hints
- Paths use `pathlib.Path` uniformly
- Prefer `WORK_ROOT` + relative paths
- Dual-mode scripts named `<module>_dspy.py`

### Add a New Module

1. Create the module in `lab_analysis/`
2. Implement the `main_with_args(args)` standard interface
3. Register it in `pipeline/run.py` via `run_step()`
4. If LLM-driven, implement the DSPy version and integrate with `prompt_inspector`

### Dependency Management

```bash
pip install -e .                              # Install
pip install pip-tools                         # Optional: generate lock file
pip-compile pyproject.toml -o requirements.lock
```

All dependencies are declared in `pyproject.toml`. Do not manually create `requirements.txt`.

---

## Advanced Docs

- [DSPy Integration Technical Details](docs/DSPY_INTEGRATION.md)
- [DSPy Usage Guide](docs/DSPY_USAGE.md)
- [examples/dspy_quickstart.py](examples/dspy_quickstart.py)

---

## Contributing

Issues and PRs are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/xxx`)
3. Commit your changes (`git commit -m 'feat: add xxx'`)
4. Push (`git push origin feature/xxx`)
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details

---

## Author

**nxz1026** — [GitHub @nxz1026](https://github.com/nxz1026)

---

## Acknowledgments

- DeepSeek, Zhipu AI, Alibaba Cloud Bailian (Qwen-VL) for LLM capabilities
- Stanford NLP's [DSPy](https://dspy.ai/) framework
- PubMed E-utilities open API

---

⭐ If this project helps you, please give it a Star!
