"""ingest_data.report — MRI 文字报告摄入。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ._log import append_log
from .lab import save_image


def ingest_mri_report(report_path: Path, patient_id: str, report_date: str) -> dict:
    """摄入 MRI 文字报告。"""
    from lab_analysis.pipeline.cli import get_deid

    patient_id_obf = get_deid(patient_id)
    saved_path = save_image(report_path, patient_id_obf, report_date, "report", "papers")
    record = {
        "timestamp": datetime.now().isoformat(),
        "type": "mri_report",
        "source_path": str(report_path),
        "saved_path": saved_path,
        "patient_id_obf": patient_id_obf,
        "report_date": report_date,
    }
    append_log(record)
    return record
