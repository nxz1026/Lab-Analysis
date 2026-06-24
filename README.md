# Lab-Analysis

> 医学检验 + 文献循证 + 影像印证 多源整合分析 Pipeline（DSPy 双轨 + 量化评估 + CI Gate）
>
> Multi-source clinical analysis pipeline: lab tests × PubMed evidence × MRI imaging, with DSPy dual-mode, quant eval, and CI gate.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-passing-success.svg)](.github/workflows/tests.yml)
[![Quant Gate](https://img.shields.io/badge/Quant_Gate-6/6_PASS-success.svg)](lab_analysis/quant_metrics.py)
[![DSPy](https://img.shields.io/badge/DSPy-3.2+-orange.svg)](https://dspy.ai/)
[![Tests](https://img.shields.io/badge/Tests-606_✔️-success.svg)](tests/)
[![MCP](https://img.shields.io/badge/MCP-6_Tools-purple.svg)](mcp_server.py)
[![Coverage](https://img.shields.io/badge/Coverage-60%25-yellow.svg)](pyproject.toml)
[![Code Style](https://img.shields.io/badge/Code-Ruff-blueviolet.svg)](pyproject.toml)

---

## TL;DR

```bash
pip install -e ".[dspy]" && python -m lab_analysis
```

一次命令，自动产出：

| 产物 | 形式 | 说明 |
|------|------|------|
| 7 张统计图表 + 异常告警 | PNG + JSON | 趋势/相关/炎症/异常/移动均值/CV/Z-score |
| 文献循证解读 | Markdown | PubMed top-k + 5 维证据打分 + LLM 解读 |
| 影像一致性报告 | Markdown | MRI + 检验交叉印证（Qwen-VL） |
| 综合临床报告 | Markdown / JSON / FHIR | 9 章节 + 可选 FHIR R4 Bundle |
| **量化评估报告** | **PNG + HTML** | **6 指标 std vs dspy 自动打分 + 可视化** |
| **多 run 趋势图** | **PNG** | **同患者跨多次跑分的纵向趋势** |
| 评分卡 & 诊断假设 | JSON + MD | 5 维 0-100 + top-3 假设 |

LLM agent (Claude Desktop / Cursor) 可通过 **MCP server 6 个 tool** 直接调度整条流水线。

---

## Features

| Dimension | Description |
|-----------|-------------|
| **Multi-source** | Lab test CSV/JSON + PubMed literature + MRI/DICOM + text reports |
| **Quant Eval** | 6 metrics (entity F1 / coverage / failure rate / recall / confidence / feedback Δ) + cross-modality consistency |
| **Visualization** | 7 stat charts + per-run PNG/HTML + cross-run trend PNG (dark / responsive / print) |
| **CI Gate** | 6 metrics must pass thresholds before merge; auto PR comment |
| **LLM Dual-mode** | 4 DSPy modules: Standard vs DSPy optimized, auto-compile, prompt snapshots |
| **MCP Server** | 6 tools exposing pipeline to LLM agents (stdio transport) |
| **Decision Support** | 5-dimension scoring card + weighted diagnosis hypotheses + feedback loop |
| **PHI Protection** | AES-256-GCM deterministic de-identification; no plaintext ID in logs/CLI/env |
| **Cross-platform** | Windows / Linux auto-adapt, PowerShell compatible |
| **Extensible** | Modular design; add new analysis dimensions via standard interface |

---

## Pipeline Flow

```bash
python -m lab_analysis [--use-dspy] [--skip-xxx]
```

| Step | Phase | Module | Input → Output |
|------|-------|--------|----------------|
| ① | **Ingest** | `ingest_data/` | `raw/Origin_data/` images/DICOM/MRI → `raw/patient_<deid>/` |
| ② | **Pre-check** | `pipeline.steps` | Validate directory structure |
| ③ | **Data Load** | `data_loader.py` | `metrics.md` → `lab_metrics.csv` + `.json` |
| ④ | **Analysis** | `analysis/` | CSV → 7 charts + `analysis_results_report.md` + `alerts.json` |
| ⑤ | **Literature** | `literature_searcher/` | Lab metrics → PubMed abstracts `.md` (auto-query generation) |
| ⑤b | **Evidence Grade** | `literature_filter.py` | Results → filtered 5-dim + S/A/B/C tier |
| ⑥ | **Interpretation** | `literature_interpreter(_dspy).py` | Literature + lab data → interpretation report |
| ⑦ | **Imaging** | `qwen_vl_report_check(_dspy).py` | MRI report + lab data → consistency report |
| ⑧ | **Report** | `gen_final_report(_dspy).py` | Steps ④⑤⑥⑦ → 9-section integrated report |
| ⑧b | **Scoring Card** | `scoring_card/` | Multi-source → 5-dim scores + top-3 hypotheses |
| ⑧c | **Quant Eval** ★ | `quant_metrics.py` + `quant_visualizer.py` | std vs dspy → 6 metrics + PNG + HTML + gate |
| ⑨ | **Archive** | `organize_local_files.py` | `data/<id>/<ts>/` → `local_upload/<YYYY-MM-DD>/` |
| ⑨b | **FHIR Export** | `fhir_exporter.py` | Results → HL7 FHIR R4 Bundle |
| ⑩ | **Cleanup** | `cleanup_runs.py` | Auto-remove old runs, keep last N (`--keep-last 3`) |

> Steps ⑥⑦⑧ switch to DSPy mode with `--use-dspy`, saving optimized prompts.
> Step ⑧c auto-triggers when both std and dspy runs exist.

### Flow Diagram

```
[① Ingest] → [② Pre-check] → [③ Load] → [④ Analysis]
                                               ↓
[⑩ Cleanup] ← [⑨ Archive] ← [⑨b FHIR] ← [⑧b Scoring] ← [⑧c Quant] ← [⑧ Report] ← [⑦ Imaging] ← [⑥ Interpret] ← [⑤b Grade] ← [⑤ Lit Search]
```

---

## Quant Eval & Visualization ★

6 quantitative metrics comparing DSPy vs Standard mode, with CI gate auto-decision.

### 6 Metrics (`lab_analysis/quant_metrics.py`)

| # | Metric | Meaning | OK Threshold |
|---|--------|---------|-------------|
| 1 | `entity_f1` | DSPy entities vs standard entities F1 | ≥ 0.70 |
| 2 | `section_coverage` | 9-section coverage | ≥ 0.80 |
| 3 | `failure_rate` | Parse failure rate (inverse) | is_failure = False |
| 4 | `entity_recall` | Standard entities recalled by DSPy | ≥ 0.70 |
| 5 | `confidence` | DSPy confidence calibration | ≥ 0.60 |
| 6 | `feedback_delta` | Δ confidence before/after user feedback | n_corrections ≥ 0 |
| 7 | `cross_modality_consistency` 🆕 | Imaging-lab cross-modality alignment | ≥ 0.70 |

### Per-Run Outputs

```
data/<deid>/<ts>/04_reports/
├── quant_eval_report.json              # Full 6-metric results + cross_modality #7
├── quant_eval_report.png               # Bar chart with OK/FAIL labels
├── quant_eval_report.html              # Single-file viz (dark / responsive / collapsible)
├── quant_eval_gate_result.json         # Gate decision (PASS/FAIL) per metric
└── .latest.txt                         # Text pointer to latest dspy_ts

data/_all/trend/
└── quant_eval_trend.png                # Cross-run trend across multiple patients
```

### CI Gate

GitHub Actions on PR: all 6 metrics must pass thresholds, or merge is blocked. Result auto-posted as PR comment (marker prevents spam).

---

## MCP Server (LLM Agent Integration)

`python mcp_server.py` exposes **6 tools** via stdio for Claude Desktop / Cursor:

| # | Tool | Purpose | Key Params |
|---|------|---------|------------|
| 1 | `audit_dspy_models` | Check 4 compiled DSPy JSONs for staleness | — |
| 2 | `run_quant_eval` | Run 6-metric quant eval + gate + viz | `deid`, `ts` |
| 3 | `list_patients` | List all patients with stats + std/dspy pairs | — |
| 4 | `get_pipeline_status` | Check pipeline run status by patient + ts | `patient_id`, `timestamp` |
| 5 | `trigger_dspy_recompile` | Incremental/full DSPy recompile (subprocess) | `force`, `timeout_sec` |
| 6 | `render_quant_trend` | Multi-run trend PNG from quant report chain | `patient_id`, `out_dir` |

Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lab-analysis": {
      "command": "python",
      "args": ["/path/to/Lab-Analysis/mcp_server.py"]
    }
  }
}
```

---

## Project Structure

```
Lab-Analysis/
├── lab_analysis/                     # Core package (76 modules, 11.3k lines)
│   ├── pipeline/                     #   Pipeline orchestration
│   │   ├── cli.py                    #     CLI parser (--use-dspy, --skip-*, etc.)
│   │   ├── steps.py                  #     Step runner (subprocess, logging)
│   │   ├── ingest.py                 #     Auto data ingestion
│   │   └── run.py                    #     Main orchestrator
│   ├── analysis/                     #   Statistical analysis subpackage
│   │   ├── _base.py                  #     Constants, reference ranges, charts
│   │   ├── _compute.py               #     Pure computation (regression, robust Z-score, MAD)
│   │   ├── charts.py                 #     7 stat charts (trend, correlation, etc.)
│   │   └── run.py                    #     Orchestrator + markdown report
│   ├── quant_metrics.py              # ★ 6-dimension quality metrics + gate
│   ├── quant_visualizer.py           # ★ PNG/HTML/trend rendering
│   ├── alert_generator.py            #   Structured alert summary
│   ├── scoring_card/                 #   Decision support (5 dims + hypotheses)
│   ├── compare_report_modes.py       #   Standard vs DSPy comparison
│   ├── evidence_grader.py            #   5-dim literature evidence grading
│   ├── patient_id.py                 #   AES-256-GCM de-identification (PHI-safe)
│   ├── error_logger.py               #   Structured error logging with PHI redaction
│   ├── _phi_filter.py                #   Global PHI logging filter
│   ├── fhir_exporter.py              #   HL7 FHIR R4 Bundle export
│   ├── feedback.py                   #   User feedback loop
│   ├── ingest_data/                  #   Data ingestion (lab/DICOM/MRI)
│   ├── extract_lab_data/             #   Lab report OCR (SCNet + regex parser)
│   ├── literature_searcher/          #   PubMed search (batched fetch, auto-queries)
│   ├── dspy_modules/                 #   DSPy optimized modules
│   │   ├── literature_interpreter.py
│   │   ├── mri_analyzer.py
│   │   ├── final_report_generator.py
│   │   ├── lab_data_extractor.py
│   │   ├── prompt_inspector.py
│   │   └── _retry.py                 #     LLM retry with exponential backoff
│   └── _log.py                       #   Logging infra (rotation, thread-safe, PHI sanitize)
├── mcp_server.py                     # ★ MCP server (6 tools, stdio)
├── tests/                            # pytest (606 cases, 37 files)
│   ├── test_pipeline_e2e.py
│   ├── test_mcp_server.py            # ★ MCP tool unit tests
│   ├── test_quant_metrics.py         # ★ 6-metric unit tests
│   ├── test_quant_visualizer.py      # ★ PNG/HTML rendering tests
│   ├── test_quant_eval_gate.py       # ★ Gate decision tests
│   ├── test_dspy_modules.py
│   └── ...                           # 31 more test files
├── scripts/                          # CI/dev utilities (18 scripts)
├── examples/                         # DSPy demos & tools (18 examples)
├── docs/                             # Extended documentation
├── models/dspy/                      # Compiled DSPy models
├── data/                             # Pipeline output (per patient × timestamp)
├── raw/                              # Source data (DICOM, paper metadata)
├── .github/workflows/tests.yml       # CI: test + quant gate + PR comment
├── pyproject.toml                    # Config: mypy strict, ruff S/T10/PTH, coverage 60%
└── mcp_server.py                     # MCP server entry
```

---

## Installation

### Requirements

- **Python**: 3.10+
- **OS**: Windows 10/11, macOS, Linux
- **Disk**: ≥ 5 GB (DICOM cache)

### Setup

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .

# Optional dependency groups
pip install "lab-analysis[dspy]"       # DSPy mode (dspy-ai, pydicom)
pip install "lab-analysis[pdf]"        # PDF reports (weasyprint, markdown)
pip install "lab-analysis[dashboard]"  # Streamlit dashboard
pip install "lab-analysis[mcp]"        # MCP server (mcp)
pip install "lab-analysis[dev]"        # Dev tools (ruff, pytest, mypy)
```

### Environment Variables

```bash
cp .env.example .env
```

| Variable | Required | Purpose | Provider |
|----------|----------|---------|----------|
| `WORK_ROOT` | Yes | Working root (default: current dir) | — |
| `DEEPSEEK_API_KEY` | Yes | LLM for interpretation / report generation | DeepSeek |
| `DASHSCOPE_API_KEY` | Yes | Qwen-VL imaging analysis | Alibaba Cloud |
| `SCNET_OCR_API_KEY` | No | Lab report OCR | SCNet |
| `LAB_DEID_KEY` | No | De-identification master key (auto-generated) | — |
| `LOG_LEVEL` | No | Override noisy-logger level (default: WARNING) | — |

---

## Usage

### One-Command Run

```bash
python -m lab_analysis                          # Standard mode (interactive ID input)
python -m lab_analysis --use-dspy               # DSPy optimized mode
```

### Skip Steps

```bash
python -m lab_analysis --skip-ingest --skip-pdf --skip-cleanup
```

### Key Options

```bash
--auto-queries                  # Auto-generate PubMed search terms
--compare-report-modes          # Std vs DSPy comparison
--keep-last 5                   # Keep last 5 runs
--no-interactive                # Non-interactive mode (fail if ID mismatch)
--skip-lit-filter               # Skip literature filtering
--lit-filter-scenario <scenario> # early_diagnosis | differential_diagnosis | prognosis
```

### Debug Individual Steps

```bash
python -m lab_analysis.data_loader    --id-card <deid>
python -m lab_analysis.scoring_card   --id-card <deid>
python -m lab_analysis.fhir_exporter  --id-card <deid>
python -m lab_analysis.cleanup_runs   --keep-last 3 --dry-run
```

Steps ⑥⑦⑧ need `ANALYSIS_TS` env var:

```powershell
$env:ANALYSIS_TS="20260611_111343"
python -m lab_analysis.literature_interpreter --id-card <deid>
```

### Quant Eval & Trend

```python
# Run quant eval for a specific run
python -c "from mcp_server import run_quant_eval; print(run_quant_eval('846552421134373347','20260620_175730'))"

# Multi-run trend chart
python -c "from mcp_server import render_quant_trend; print(render_quant_trend('846552421134373347'))"

# Streamlit dashboard
pip install "lab-analysis[dashboard]"
streamlit run lab_analysis/dashboard.py
```

---

## Output Artifacts

```
data/{patient_id}/{timestamp}/
├── lab_metrics{.csv,.json}               # Lab data
├── analysis_results.json                 # Statistical analysis
├── alerts.json                           # Structured alerts (CRITICAL/WARNING/INFO)
├── fig_01~fig_07.png                     # 7 stat charts
├── analysis_results_report.md            # Analysis report
├── literature_results{.json,.filtered.json}  # PubMed + evidence grade
├── literature_interpretation.md          # Literature interpretation
├── mri_report_check_results.md           # Imaging consistency
├── final_integrated_report{.md,.json}    # Final integrated report (9 sections)
├── scoring_card{.json,.md}               # Scoring card + top-3 hypotheses
├── mode_comparison_report.md             # Standard/DSPy comparison
├── quant_eval_report{.json,.png,.html}   # ★ 6-metric quant eval
├── quant_eval_gate_result.json           # ★ Gate decision
├── .latest.txt                           # Latest dspy_ts pointer
├── fhir_bundle.json                      # HL7 FHIR R4 Bundle
├── feedback.json                         # User feedback
└── dspy_prompts/                         # DSPy prompt snapshots

data/_all/trend/
└── quant_eval_trend.png                  # ★ Cross-run trend
```

---

## DSPy Enhancement

4 LLM core modules with Standard + DSPy dual-track:

| Module | Standard | DSPy |
|--------|----------|------|
| Literature Interpretation | `literature_interpreter.py` | `dspy_modules/literature_interpreter.py` |
| MRI Analysis | `qwen_vl_report_check.py` | `dspy_modules/mri_analyzer.py` |
| Final Report | `gen_final_report.py` | `dspy_modules/final_report_generator.py` |
| Lab Data Extraction | `extract_lab_data/` | `dspy_modules/lab_data_extractor.py` |

See [docs/DSPY_INTEGRATION.md](docs/DSPY_INTEGRATION.md) and [docs/DSPY_USAGE.md](docs/DSPY_USAGE.md).

### Retry & Resilience

All DSPy modules use `safe_predict()` with 3x exponential backoff, catching all LLM API exceptions (OpenAI, LiteLLM, connection errors). Failed modules fall back to `make_empty_prediction()` with zero-initialized outputs.

---

## Evidence Grading (Step ⑤b)

See [docs/EVIDENCE_GRADING.md](docs/EVIDENCE_GRADING.md):

- 5 dims: topic match / evidence level / timeliness / sample size / parse quality
- 3 scenario weights: `early_diagnosis` / `differential_diagnosis` / `prognosis`
- S / A / B / C tier rating
- Pure rule engine, no LLM, reproducible

CLI: `--lit-filter-scenario <scenario> --lit-filter-top-k <N>`

---

## CI / CD

GitHub Actions `.github/workflows/tests.yml`:

| Job | Trigger | Content |
|-----|---------|---------|
| `test` | push / PR | pytest matrix (3.10~3.13) + ruff + mypy |
| `quant_eval_gate` | push / PR | 6-metric quant eval + gate + **auto PR comment** |

PR comment example:

> ### Quant Eval Gate
> **deid=846552421134373347 ts=20260620_175730**
> | metric | value | status |
> |--------|-------|--------|
> | entity_f1 | 0.94 | OK |
> | ... | ... | ... |
> **Overall: PASS ✅**

---

## Tech Stack

| Domain | Choice |
|--------|--------|
| Data | pandas, numpy, scipy |
| ML | scikit-learn (robust Z-score with MAD) |
| Visualization | matplotlib, Streamlit |
| Imaging | Pillow, pydicom |
| PDF | weasyprint, markdown (optional) |
| OCR | SCNet OCR API + regex parser |
| Vision | Alibaba Qwen-VL |
| LLM | DeepSeek API (OpenAI-compatible) |
| LLM Optimization | DSPy 3.2+ (BootstrapFewShot / MIPROv2) |
| Literature | PubMed E-utilities (batched 100/request) |
| MCP | FastMCP (stdio transport) |
| Security | AES-256-GCM de-identification, PHI-safe logging |
| Error Handling | tenacity retry + error_logger with PHI redaction |
| Testing | pytest (606 cases, 37 files) |
| Linting | ruff (S/T10/PTH rules), mypy strict |
| Coverage | ≥ 60% (pytest-cov) |
| CI | GitHub Actions |

---

## Development

```bash
pip install -e ".[dev]"
python -m pytest                       # 606 tests
python -m pytest -v --cov              # With coverage
ruff check lab_analysis/               # Lint (security + pathlib rules)
mypy lab_analysis/                     # Type check (strict mode)
```

### Code Conventions

- PEP 8 + type annotations (`from __future__ import annotations`)
- `pathlib.Path` for all paths
- `WORK_ROOT` from `utils.py` (single source of truth)
- Dual-mode scripts: `<module>.py` + `<module>_dspy.py`
- Logging: `_log.get_logger(__name__)` everywhere
- Exceptions: `SAFE_EXCEPTIONS` from `_exceptions.py` for non-critical paths

### Adding a New Module

1. Create module in `lab_analysis/`
2. Implement `main_with_args(args)` standard interface
3. Register via `run_step()` in `pipeline/run.py`
4. If LLM involved: implement DSPy version + `prompt_inspector` integration

### Adding a Quant Metric

1. Add function in `lab_analysis/quant_metrics.py` + `available=True` fallback
2. Add threshold in `DEFAULT_THRESHOLDS`
3. Add branch in `quant_visualizer.py` `_extract_metric_value`
4. Add unit tests in `tests/test_quant_metrics.py` + `tests/test_quant_visualizer.py`
5. Update README table

---

## Documentation

- [DSPy Integration](docs/DSPY_INTEGRATION.md)
- [DSPy Usage Guide](docs/DSPY_USAGE.md)
- [Evidence Grading](docs/EVIDENCE_GRADING.md)
- [MCP Integration](docs/MCP_INTEGRATION.md)

---

## Contributing

1. Fork
2. `git checkout -b feature/xxx`
3. `git commit -m 'feat: xxx'`
4. `git push origin feature/xxx`
5. Open PR

---

## License

MIT — see [LICENSE](LICENSE)

---

## Author

**nxz1026** — [GitHub @nxz1026](https://github.com/nxz1026)

---

## Acknowledgements

- DeepSeek / SCNet / Alibaba Cloud (Qwen-VL)
- Stanford NLP [DSPy](https://dspy.ai/)
- PubMed E-utilities
- [FastMCP](https://github.com/jlowin/fastmcp) MCP framework

---

⭐ If this project helps you, please give it a Star!
