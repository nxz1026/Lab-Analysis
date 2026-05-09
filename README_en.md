# Lab-Analysis

Automated Analysis Pipeline for Chronic Pancreatitis Lab Data (Lab Tests + Literature + Imaging + Integrated Report)

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 📋 Overview

Fully automated medical lab data analysis system:

- 🔬 **Auto Extraction** - OCR recognition of lab reports
- 📊 **Smart Analysis** - 7 visualization charts
- 📚 **Literature Search** - PubMed + AI interpretation
- 🖼️ **Imaging Check** - MRI/DICOM verification
- 📝 **Integrated Report** - Three-source consistency assessment

## ✨ Core Features

### 1. Data Ingestion
- OCR recognition of lab report images
- DICOM image extraction and renaming
- MRI text report parsing
- Patient ID de-identification

### 2. Data Analysis (7 Charts)
- Trend regression, correlation heatmap
- Inflammation assessment, anomaly detection
- Moving average, coefficient of variation, comprehensive dashboard

### 3. Literature Search & Interpretation
- Automated PubMed search
- DeepSeek AI evidence-based interpretation

### 4. Imaging Report Check
- Qwen-VL model validates MRI reports
- Consistency check between imaging and lab data

### 5. Integrated Report Generation
- Three-source consistency assessment
- Structured report + local archiving

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/nxz1026/Lab-Analysis.git
cd Lab-Analysis
pip install -e .
```

### Configure Environment Variables

Create `.env` file:

```env
WORK_ROOT=/path/to/your/work
ZHIPU_API_KEY=your_zhipu_key
DEEPSEEK_API_KEY=your_deepseek_key
DASHSCOPE_API_KEY=your_dashscope_key
```

### Run

```bash
# Recommended method
python -m lab_analysis --patient-id YOUR_PATIENT_ID

# Or convenient method
python run_analysis.py --patient-id YOUR_PATIENT_ID
```

#### Skip Steps

```bash
python -m lab_analysis --patient-id ID --skip-llm      # Skip literature interpretation
python -m lab_analysis --patient-id ID --skip-imaging  # Skip imaging analysis
python -m lab_analysis --patient-id ID --skip-ingest   # Skip data ingestion
```

## 📂 Project Structure

```
Lab-Analysis/
├── lab_analysis/              # Core modules
│   ├── pipeline.py            # Pipeline main entry
│   ├── ingest_data.py         # Data ingestion
│   ├── data_loader.py         # Data loading
│   ├── data_analyzer.py       # Data analysis (7 charts)
│   ├── literature_searcher.py # Literature search
│   ├── literature_interpreter.py  # Literature interpretation
│   ├── qwen_vl_report_check.py    # Imaging report check
│   ├── gen_final_report.py    # Integrated report generation
│   ├── organize_local_files.py    # Local file organization
│   ├── vision_extractor.py    # Vision AI extraction
│   ├── batch_vision_extract.py    # Batch vision extraction
│   ├── extract_lab_data.py    # Lab data extraction
│   ├── patient_id.py          # Patient ID processing
│   └── utils.py               # Utility functions
├── raw/                       # Raw data directory
│   └── Origin_data/           # Raw files to be processed
├── data/                      # Analysis results (organized by patient ID)
│   └── {patient_id}/
│       └── {timestamp}/
│           ├── lab_metrics.csv/json      # Lab data
│           ├── fig_01~07.png             # 7 analysis charts
│           ├── literature_results.md     # Literature search results
│           ├── literature_interpretation.md  # Literature interpretation
│           ├── mri_report_check_results.md   # Imaging check results
│           ├── analysis_results_report.md    # Analysis report
│           └── final_integrated_report.md    # Final integrated report
├── local_upload/              # Local archive directory
│   └── {YYYY-MM-DD}/
│       ├── Raw_Data/
│       ├── Literature/
│       ├── Intermediate_Results/
│       ├── Statistical_Results/
│       └── final_integrated_report.md
├── .env                       # Environment variables (not committed to Git)
├── .env.example               # Environment variable example
├── pyproject.toml             # Project configuration and dependency management
└── run_analysis.py            # Run script entry point
```

## 📊 Output

### 7 Analysis Charts

1. **fig_01** - Trend Regression
2. **fig_02** - Correlation Heatmap
3. **fig_03** - Inflammation Assessment
4. **fig_04** - Anomaly Detection
5. **fig_05** - Stability Analysis
6. **fig_06** - Trend Smoothing
7. **fig_07** - Comprehensive Dashboard

### Report Files

- `final_integrated_report.md` - Final integrated report
- `analysis_results_report.md` - Detailed statistical analysis report
- `literature_interpretation.md` - Literature interpretation
- `mri_report_check_results.md` - Imaging check results

## 🔧 Advanced Usage

### Batch Processing

```bash
python -m lab_analysis.batch_vision_extract [--interactive]
```

Automatically scans `Origin_data` directory for batch recognition and ingestion of lab reports.

### Run Individual Modules

```bash
python -m lab_analysis.data_analyzer --patient-id ID           # Data analysis
python -m lab_analysis.literature_searcher --patient-id ID     # Literature search
python -m lab_analysis.organize_local_files --patient-id ID    # Local archiving
```

## 🛠️ Tech Stack

- **Data Processing**: pandas, numpy, scipy
- **Machine Learning**: scikit-learn
- **Visualization**: matplotlib
- **Image Processing**: Pillow
- **AI Models**: Zhipu GLM-4V, DeepSeek, Alibaba Cloud Qwen-VL
- **Literature Search**: PubMed API

## 📝 Development Guide

### Code Standards

- PEP 8 coding standards
- Type hints
- Paths use `WORK_ROOT` + relative paths
- Use `pathlib.Path`

### Dependency Management

```bash
pip install -e .                    # Install dependencies
pip install pip-tools               # Optional: generate lock file
pip-compile pyproject.toml -o requirements.lock
```

> ⚠️ All dependencies are declared in `pyproject.toml`. Do not manually create `requirements.txt`.

### Error Logging

- **Log file**: `{WORK_ROOT}/error.log`
- **Auto logging**: Records detailed information when Pipeline fails
- **View recent errors**:
  ```python
  from lab_analysis.error_logger import get_recent_errors
  errors = get_recent_errors(n=10)
  ```

### Add New Modules

1. Create module in `lab_analysis/`
2. Implement standard interface (accept `--patient-id`)
3. Register step in `pipeline.py`

### Testing

```bash
python -m lab_analysis.data_analyzer --patient-id TEST_ID  # Test module
pip install ruff; ruff check lab_analysis/                 # Code linting
```

## 🤝 Contributing

Issues and PRs are welcome!

1. Fork the repository
2. Create a branch (`git checkout -b feature/xxx`)
3. Commit changes (`git commit -m 'Add xxx'`)
4. Push (`git push origin feature/xxx`)
5. Open a Pull Request

## 📄 License

MIT License - See [LICENSE](LICENSE) for details

## 👤 Author

**nxz1026** - [GitHub](https://github.com/nxz1026)

## 🙏 Acknowledgments

- Zhipu AI, DeepSeek, Alibaba Cloud

---

⭐ If this project helps you, please give it a Star!
