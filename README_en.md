# Lab-Analysis

> Multi-source Medical Lab Data + Literature Evidence + Imaging Verification Pipeline (with DSPy Prompt Optimization)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/nxz1026/Lab-Analysis/actions/workflows/tests.yml/badge.svg)](https://github.com/nxz1026/Lab-Analysis/actions/workflows/tests.yml)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Tests](https://img.shields.io/badge/Tests-606_✔️-success.svg)](tests/)
[![Pipeline](https://img.shields.io/badge/Pipeline-11_Steps-success.svg)](#complete-pipeline-flow)

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
| **One-click Automation** | 11-step pipeline runs end-to-end; all intermediate artifacts are traceable |
| **Interpretability** | 7 statistical charts + structured alert summary + full logs |
| **LLM Enhancement** | DSPy integration; Standard vs. DSPy dual-mode auto-comparison |
| **Decision Support** | 5-dimension scoring card + weighted diagnostic hypotheses (pure rule engine, no LLM) |
| **Cross-platform** | Windows / Linux auto-adaptation, console encoding auto-fix |
| **Extensibility** | Modular design; add new analysis dimensions by implementing a standard interface |

---

## Complete Pipeline Flow

```bash
python -m lab_analysis
```

At runtime, the program interactively prompts for a valid Chinese ID card number, then executes 11 steps in order. Key steps support `--skip-xxx` to bypass.

| Step | Name | Module | Input → Output |
|------|------|--------|----------------|
| ① | **Data Ingestion** | `ingest_data/` | `raw/Origin_data/` lab images / DICOM / MRI reports → `raw/patient_<deid>/` |
| ② | **Pre-check** | `pipeline.steps` | Validate directory structure → pass/fail |
| ③ | **Data Loading** | `data_loader.py` | `.../metrics.md` → `lab_metrics.csv` + `.json` |
| ④ | **Statistical Analysis** | `analysis/run` | `lab_metrics.csv` → 7 charts + report + `alerts.json` |
| ⑤ | **Literature Search** | `literature_searcher/` | Lab items + key indicators → PubMed abstracts (supports `--auto-queries`) |
| ⑤b | **Evidence Grading** (optional) | `literature_filter.py` | `literature_results.json` → `.filtered.json` (top-k by evidence tier) |
| ⑥ | **Evidence Interpretation** | `literature_interpreter(_dspy).py` | Abstracts + lab data → interpretation report + DSPy prompt |
| ⑦ | **Imaging Analysis** | `qwen_vl_report_check(_dspy).py` | MRI report + lab data → consistency report + DSPy prompt |
| ⑧ | **Integrated Report** | `gen_final_report(_dspy).py` | ④⑤⑥⑦ artifacts → 9-chapter report (supports `--compare-mode`) |
| ⑧b | **Scoring Card** (optional, new) | `scoring_card/` | Multi-source → 5-dimension scores + top-3 hypotheses |
| ⑨ | **Local Archive** | `organize_local_files.py` | `data/<id>/<ts>/` → `local_upload/<YYYY-MM-DD>/` |
| ⑨b | **FHIR Export** (optional, new) | `fhir_exporter.py` | Multi-source → HL7 FHIR R4 Bundle (Patient/Observation/RiskAssessment) |
| ⑩ | **Run Cleanup** (optional, new) | `cleanup_runs.py` | Auto-delete old runs, keep last N (`--keep-last 3`) |

> Steps ⑥⑦⑧ automatically switch to DSPy optimized mode when `--use-dspy` is set.

### Flow Diagram

```
[① Data Ingestion] → [② Pre-check] → [③ Data Loading] → [④ Statistical Analysis]
                                                                ↓
[⑩ Cleanup] ← [⑨ Archive] ← [⑧b Scoring] ← [⑧ Report] ← [⑦ Imaging] ← [⑥ Interpretation] ← [⑤ Literature]
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

# Optional dependency groups
pip install "lab-analysis[dspy]"       # DSPy mode (dspy-ai, pydicom)
pip install "lab-analysis[pdf]"        # PDF output (weasyprint, markdown)
pip install "lab-analysis[dashboard]"  # Streamlit dashboard
pip install "lab-analysis[dev]"        # Dev tools (ruff, pytest)
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
| `SCNET_OCR_API_KEY` | No | Lab report image OCR text extraction | SCNet |
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
python -m lab_analysis --skip-ingest       # Skip ingestion
python -m lab_analysis --skip-llm          # Skip literature interpretation
python -m lab_analysis --skip-imaging      # Skip imaging analysis
python -m lab_analysis --skip-lit-filter   # Skip evidence grading
python -m lab_analysis --skip-scoring      # Skip scoring card
python -m lab_analysis --skip-pdf          # Skip PDF generation
python -m lab_analysis --skip-fhir         # Skip FHIR export
python -m lab_analysis --skip-cleanup      # Skip old run cleanup
```

### New Features

**Auto-generated PubMed queries** (from abnormal metrics):
```bash
python -m lab_analysis --auto-queries
```

**Standard / DSPy dual-mode comparison**:
```bash
python -m lab_analysis --compare-report-modes
```

**Run cleanup** (keep last 5):
```bash
python -m lab_analysis --keep-last 5
```

**Streamlit dashboard** (standalone):
```bash
pip install "lab-analysis[dashboard]"
streamlit run lab_analysis/dashboard.py
```

### Debug a Single Step

```bash
python -m lab_analysis.data_loader --id-card <deid>
python -m lab_analysis.scoring_card --id-card <deid>
python -m lab_analysis.cleanup_runs --keep-last 3 --dry-run
```

For steps ⑥⑦⑧, set `ANALYSIS_TS` to an existing timestamp directory:

```powershell
$env:ANALYSIS_TS="20260611_111343"
python -m lab_analysis.literature_interpreter --id-card <deid>
```

---

## New Features Detail

### Structured Alert Summary

Auto-generated by step ④, outputs `alerts.json`:

| Level | Trigger |
|-------|---------|
| 🚨 CRITICAL | Acute inflammation / severe Z-score outliers / ≥3x out-of-range |
| ⚠️ WARNING | Out-of-range / high CV (>0.2) / significant upward trend |
| ℹ️ INFO | Mild Z-score outliers / downward trend |

### Scoring Card & Clinical Decision Support (step ⑧b)

Pure rule engine (no LLM). 5 dimensions (0-100) + weighted diagnostic hypotheses:

| Dimension | Source | Meaning |
|-----------|--------|---------|
| `inflammation` | hs-CRP stage + trend | High → active inflammation |
| `lab_abnormality` | Abnormal metrics + Z-scores | High → significant abnormality |
| `literature_support` | Evidence grading | High → strong literature support |
| `imaging_consistency` | MRI consistency report | High → imaging agrees with labs |
| `variability_stability` | CV stability | High → stable metrics |

### Auto PubMed Queries

```bash
python -m lab_analysis --auto-queries
# or standalone:
python -m lab_analysis.literature_searcher --id-card <deid> --auto-queries
```

Generates search strategies based on abnormal metrics, e.g.:
- hs-CRP↑ → `"chronic pancreatitis" AND ("hs-CRP" OR "high-sensitivity CRP")`
- Acute phase → `"acute pancreatitis" biomarker PCT CRP severity`

### Standard / DSPy Dual-mode Comparison

```bash
python -m lab_analysis.gen_final_report --id-card <deid> --compare-mode
```

Runs both Standard API and DSPy module simultaneously, compares 9 chapters section-by-section: character count, overlap rate, entity mention differences. Output to `04_reports/mode_comparison_report.md`.

### PDF Report

```bash
pip install "lab-analysis[pdf]"
python -m lab_analysis.gen_final_report_pdf \
    --md data/<deid>/<ts>/04_reports/final_integrated_report.md \
    --img-dir data/<deid>/<ts>/02_analyzed/figures \
    --out data/<deid>/<ts>/04_reports/final_integrated_report.pdf
```

Enabled by default in pipeline (if deps installed). `--skip-pdf` to bypass. CJK typesetting.

### Streamlit Dashboard

```bash
pip install "lab-analysis[dashboard]"
streamlit run lab_analysis/dashboard.py
```

4 tabs: Overview (inflammation timeline + alerts) / Charts / Lab Data Table / Final Report. Sidebar selects patient and run batch.

### Run Cleanup

```bash
# Keep last 3, delete older runs
python -m lab_analysis.cleanup_runs --keep-last 3

# Preview only
python -m lab_analysis.cleanup_runs --keep-last 5 --dry-run

# Clean specific patient only
python -m lab_analysis.cleanup_runs --keep-last 2 --id-card <deid>
```

Pipeline step ⑩ enabled by default (keep last 3). `--skip-cleanup` to bypass.

### Lab Metric Prediction

Auto-executed in step ④. Uses linear regression + 95% CI on time-series data to predict next-visit values.

```
   hs-CRP: next=14.300  95%CI=[11.200, 17.400]  rising ⚠️ exceeds threshold 3.0
```

Results written to `analysis_results.json` under `predictions` field, also printed to console.

### FHIR Export (step ⑨b)

Maps pipeline results to HL7 FHIR R4 Bundle:

| FHIR Resource | Source |
|---------------|--------|
| `Patient` | De-identified patient ID |
| `Observation` | Lab metrics with LOINC codes + reference ranges |
| `Observation` | Inflammation status |
| `Observation` | Alert summary (CRITICAL/WARNING) |
| `RiskAssessment` | Scoring card top-3 hypotheses |
| `DiagnosticReport` | Final integrated report conclusion |

```bash
# Pipeline default enabled
python -m lab_analysis --skip-fhir   # Skip

# Standalone
python -m lab_analysis.fhir_exporter --id-card <deid>
```

Output to `04_reports/fhir_bundle.json`.

### Feedback Loop

Record user corrections to scoring card hypotheses, auto-adjusts confidence weights on next run.

```bash
# Show current feedback
python -m lab_analysis.feedback --id-card <deid> --show

# Record a correction
python -m lab_analysis.feedback --id-card <deid> --correct \
  --original "Chronic pancreatitis (active)" --corrected "Acute pancreatitis" \
  --confidence 0.90 --comment "Confirmed clinically"

# Clear feedback
python -m lab_analysis.feedback --id-card <deid> --clear
```

Feedback stored in `data/<deid>/feedback.json`, auto-loaded by scoring card on next pipeline run.

---

## Output Artifacts

```
data/{patient_id}/{timestamp}/
├── lab_metrics.csv                       # Lab data (CSV)
├── lab_metrics.json                      # Lab data (JSON, de-identified)
├── analysis_results.json                 # Full statistical results
├── alerts.json                           # Structured alert summary (NEW)
├── fig_01~fig_07.png                     # 7 statistical charts
├── analysis_results_report.md            # Statistical report
├── literature_results.json               # PubMed search results
├── literature_results.filtered.json      # Evidence-graded results
├── literature_interpretation.md          # Literature interpretation
├── mri_report_check_results.md           # Imaging consistency report
├── final_integrated_report.md            # Final integrated report
├── final_integrated_report.pdf           # PDF report (optional, NEW)
├── scoring_card.json                     # Scoring card & hypotheses (NEW)
├── scoring_card.md                       # Scoring card readable (NEW)
├── mode_comparison_report.md             # Standard/DSPy comparison (NEW)
├── mode_comparison.json                  # Comparison data (NEW)
├── fhir_bundle.json                      # HL7 FHIR R4 Bundle (NEW)
├── reports/dspy_prompt_comparison.{md,json}  # Prompt comparison
└── dspy_prompts/                         # DSPy prompt snapshots
```

---

## Evidence Grading (Step ⑤b)

See [docs/EVIDENCE_GRADING.md](docs/EVIDENCE_GRADING.md).

Summary:
- 5 independent dimensions (topic_match / evidence_level / recency / sample_size / parse_quality)
- 3 scenario weight presets: `early_diagnosis` / `differential_diagnosis` / `prognosis`
- S/A/B/C tier bands
- Pure rule-based — no LLM, fully reproducible

---

## DSPy Enhancement

| Module | Standard | DSPy |
|--------|----------|------|
| Literature Interpretation | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` |
| MRI Analysis | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` |
| Report Generation | `gen_final_report.py` | `dspy_modules/final_report_generator.py` |
| Lab Data Extraction | `extract_lab_data/` | `dspy_modules/lab_data_extractor.py` |

---

## Tech Stack

| Domain | Choice |
|--------|--------|
| Data Processing | pandas, numpy, scipy |
| ML | scikit-learn |
| Visualization | matplotlib, Streamlit (dashboard) |
| Image | Pillow, pydicom |
| PDF | weasyprint, markdown (optional) |
| OCR / Vision | SCNet OCR, Qwen-VL |
| Text Generation | DeepSeek API (OpenAI-compatible) |
| LLM Optimization | DSPy 3.2+ |
| Literature Search | PubMed E-utilities |
| Error Handling | tenacity + error_logger |
| Testing | pytest (606 test cases) |
| CI | GitHub Actions (py3.10~3.12 matrix) |

---

## Development

### Testing

```bash
pip install -e ".[dev]"
python -m pytest                # 606 tests
python -m pytest -v --cov       # With coverage
ruff check lab_analysis/        # Code style
```

### Code Standards

- PEP 8 + type hints
- `pathlib.Path` for all paths
- `WORK_ROOT` + relative paths preferred
- `<module>_dspy.py` for DSPy variants
- Platform detection via `utils.is_windows()`

---

## License

MIT — see [LICENSE](LICENSE)

---

## Author

**nxz1026** — [GitHub @nxz1026](https://github.com/nxz1026)

⭐ Star if this project helps you!
