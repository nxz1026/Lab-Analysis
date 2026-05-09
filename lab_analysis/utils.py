"""
utils.py — 公共工具函数，替换各模块重复定义的 build_paths 等。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from .config import ANALYSIS_TS, WORK_ROOT


class PatientPaths(TypedDict):
    """build_paths 返回的路径字典类型。"""
    raw_papers:   Path
    output_dir:   Path
    analyzed_dir: Path
    data_dir:     Path
    figures_dir:  Path
    reports_dir:  Path
    csv:          Path
    json:         Path
    metrics_csv:  Path
    output_json:  Path
    lit_dir:      Path


def build_paths(patient_id: str, ts: str | None = None) -> PatientPaths:
    """
    根据 patient_id 和 ANALYSIS_TS 构建路径字典。

    消除 data_loader.py 和 data_analyzer.py 中的重复定义。
    """
    if ts is None:
        ts = ANALYSIS_TS or patient_id

    data_dir    = WORK_ROOT / "data" / patient_id / ts
    analyzed_dir = data_dir / "02_analyzed"
    figures_dir  = analyzed_dir / "figures"
    reports_dir  = data_dir / "04_reports"

    return PatientPaths(
        raw_papers  = WORK_ROOT / "raw" / f"patient_{patient_id}" / "papers",
        output_dir  = data_dir,
        analyzed_dir= analyzed_dir,
        data_dir    = data_dir,
        figures_dir = figures_dir,
        reports_dir = reports_dir,
        csv         = analyzed_dir / "lab_metrics.csv",
        json        = analyzed_dir / "lab_metrics.json",
        metrics_csv = analyzed_dir / "lab_metrics.csv",
        output_json = analyzed_dir / "analysis_results.json",
        lit_dir     = data_dir / "03_literature",
    )