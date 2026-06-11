"""端到端测试:DSPy Prompt 对比

流程:
1. 创建模拟的 analysis_results.json 和 literature_results.json
2. 运行标准模式 literature_interpreter,生成标准 prompt
3. 运行 DSPy 模式 literature_interpreter_dspy,生成优化 prompt
4. 运行 dspy_prompt_comparison.py 生成对比报告
"""

import json
import os
import subprocess
import sys
from pathlib import Path

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))
os.environ.setdefault("WORK_ROOT", str(WORK_ROOT))
os.environ.setdefault("ANALYSIS_TS", "20260611_test")

DATA_DIR = WORK_ROOT / "data" / "846552421134373347" / "20260611_test"
LIT_DIR = DATA_DIR / "03_literature"
ANALYZED_DIR = DATA_DIR / "02_analyzed"

# 创建目录
LIT_DIR.mkdir(parents=True, exist_ok=True)
ANALYZED_DIR.mkdir(parents=True, exist_ok=True)

print(f"[INFO] Data directory: {DATA_DIR}")

# 1. 准备 analysis_results.json
analysis_results = {
    "patient_id": "846552421134373347",
    "timestamp": "2026-04-28",
    "metrics_summary": {
        "WBC": [4.5, 5.1, 3.8, 4.2, 4.8],
        "hs-CRP": [85.3, 92.1, 78.5, 88.0, 105.2],
        "NEUT%": [0.65, 0.62, 0.58, 0.60, 0.63],
        "RDW": [13.5, 14.2, 15.1, 15.8, 16.2],
        "MONO%": [0.08, 0.09, 0.11, 0.12, 0.13],
    },
    "abnormal_summary": {
        "hs-CRP": {"n_abnormal": 5, "abnormal_dates": ["2026-03-24"], "ref_range": "<5"},
        "RDW": {"n_abnormal": 4, "abnormal_dates": ["2026-04-15"], "ref_range": "11.5-14.5"},
    },
    "correlation_matrix": {
        "hs-CRP_RDW": 0.92,
        "WBC_NEUT%": 0.85,
    },
    "linear_regression": {
        "RDW_vs_time": {"slope": 0.65, "r_squared": 0.94}
    }
}
analysis_path = ANALYZED_DIR / "analysis_results.json"
with open(analysis_path, 'w', encoding='utf-8') as f:
    json.dump(analysis_results, f, ensure_ascii=False, indent=2)
print(f"[OK] Created: {analysis_path}")

# 2. 准备 literature_results.json
literature_results = {
    "query": "chronic pancreatitis hs-CRP RDW",
    "total_unique_papers": 5,
    "all_papers": [
        {
            "pmid": "12345678",
            "title": "RDW as a prognostic marker in chronic inflammation",
            "abstract": "This study investigates the relationship between red cell distribution width (RDW) and chronic inflammatory conditions. RDW elevation correlates with disease severity and poor prognosis...",
            "year": "2023",
            "journal": "J Inflamm Res",
            "url": "https://pubmed.ncbi.nlm.nih.gov/12345678"
        },
        {
            "pmid": "23456789",
            "title": "hs-CRP and WBC dissociation in autoimmune conditions",
            "abstract": "We report a series of patients showing hs-CRP elevation without corresponding WBC increase, suggesting immune dysregulation...",
            "year": "2024",
            "journal": "Autoimmun Rev",
            "url": "https://pubmed.ncbi.nlm.nih.gov/23456789"
        },
    ]
}
lit_path = LIT_DIR / "literature_results.json"
with open(lit_path, 'w', encoding='utf-8') as f:
    json.dump(literature_results, f, ensure_ascii=False, indent=2)
print(f"[OK] Created: {lit_path}")

# 3. 运行标准模式 (不传 --use-dspy)
print("\n[Step 1] Running standard mode...")
result = subprocess.run(
    [sys.executable, "-m", "lab_analysis.literature_interpreter_dspy",
     "--patient-id", "846552421134373347",
     "--analysis", str(analysis_path), "--lit", str(lit_path),
     "--out", str(LIT_DIR / "literature_interpretation.json")],
    cwd=str(WORK_ROOT),
    capture_output=True,
    text=True
)
print(f"  Return code: {result.returncode}")
if result.stdout:
    print("  STDOUT (last 500 chars):", result.stdout[-500:])
if result.stderr:
    print("  STDERR:", result.stderr[-500:])

# 4. 运行 DSPy 模式 (传 --use-dspy)
print("\n[Step 2] Running DSPy mode...")
result = subprocess.run(
    [sys.executable, "-m", "lab_analysis.literature_interpreter_dspy",
     "--patient-id", "846552421134373347", "--use-dspy",
     "--analysis", str(analysis_path), "--lit", str(lit_path),
     "--out", str(LIT_DIR / "literature_interpretation_dspy.json")],
    cwd=str(WORK_ROOT),
    capture_output=True,
    text=True
)
print(f"  Return code: {result.returncode}")
if result.stdout:
    print("  STDOUT (last 500 chars):", result.stdout[-500:])
if result.stderr:
    print("  STDERR:", result.stderr[-500:])


# 5. 运行对比工具
print("\n[Step 3] Running comparison tool...")
result = subprocess.run(
    [sys.executable, "examples/dspy_prompt_comparison.py",
     "--data-dir", str(DATA_DIR)],
    cwd=str(WORK_ROOT),
    capture_output=True,
    text=True
)
print(f"  Return code: {result.returncode}")
if result.stdout:
    print("  STDOUT:", result.stdout)
if result.stderr:
    print("  STDERR:", result.stderr[-500:])

print("\n[DONE] Test completed!")