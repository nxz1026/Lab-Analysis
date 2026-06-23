"""ingest_data.lab — 检验报告图片摄入。"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from ._log import WORK_ROOT, append_log


def save_image(
    image_path: Path,
    patient_id_obf: str,
    report_date: str,
    report_type: str,
    data_type: str = "lab",
) -> str:
    """保存图片到 raw/patient_{脱敏ID}/{data_type}/"""
    target_dir = WORK_ROOT / "raw" / f"patient_{patient_id_obf}" / data_type
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_name = image_path.name
    dest_path = target_dir / dest_name
    if dest_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        stem = image_path.stem
        suffix = image_path.suffix
        dest_path = target_dir / f"{stem}_{ts}{suffix}"
    shutil.copy2(image_path, dest_path)
    return str(dest_path.relative_to(WORK_ROOT))


def ingest_lab_image(
    image_path: Path,
    patient_id: str,
    report_date: str,
    report_type: str,
) -> dict:
    """摄入检验报告图片。"""
    from lab_analysis.pipeline.cli import get_deid

    patient_id_obf = get_deid(patient_id)
    saved_path = save_image(image_path, patient_id_obf, report_date, report_type, "lab")
    record = {
        "timestamp": datetime.now().isoformat(),
        "type": "lab_image",
        "source_path": str(image_path),
        "saved_path": saved_path,
        "patient_id_obf": patient_id_obf,
        "report_date": report_date,
        "report_type": report_type,
    }
    append_log(record)
    return record
