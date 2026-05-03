#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_loader.py
读取指定病人的 lab_report_*/metrics.md，提取数值写入 data/{patient_id}/lab_metrics.csv + lab_metrics.json

用法：python data_loader.py --patient-id 513229198801040014
"""

import re
import csv
import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

WIKI_ROOT = Path.home() / "wiki"


def build_paths(patient_id: str):
    """根据 patient_id 和 ANALYSIS_TS 环境变量构建路径字典。"""
    import os
    raw_papers = WIKI_ROOT / "raw" / f"patient_{patient_id}" / "papers"
    # 支持时间戳目录：ANALYSIS_TS=patient_id/YYYYMMDD_HHMMSS
    ts = os.environ.get("ANALYSIS_TS", patient_id)
    output_dir = WIKI_ROOT / "data" / patient_id / ts
    return {
        "raw_papers": raw_papers,
        "output_dir": output_dir,
        "csv": output_dir / "lab_metrics.csv",
        "json": output_dir / "lab_metrics.json",
    }


# 所有指标（顺序与表格列一致）
ALL_METRICS = [
    "WBC", "RBC", "HGB", "HCT", "PLT", "PCT", "P-LCR",
    "MCV", "MCH", "MCHC",
    "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
    "NEUT#", "LYMPH#", "MONO#", "EO#", "BASO#",
    "RDW-SD", "RDW-CV", "MPV", "PDW",
    "CRP", "hs-CRP",
]

# 参考范围（用于判断正常/异常，仅作参考，notes.md 中有精确值时以notes为准）
REF_RANGES = {
    "WBC": (3.5, 9.5),
    "RBC": (4.3, 5.8),
    "HGB": (130, 175),
    "HCT": (40, 50),
    "PLT": (125, 350),
    "PCT": (0.108, 0.272),
    "NEUT%": (40, 75),
    "LYMPH%": (20, 50),
    "MONO%": (2, 10),
    "EO%": (0.4, 8),
    "BASO%": (0, 1),
    "NEUT#": (1.8, 6.3),
    "LYMPH#": (1.1, 3.2),
    "MONO#": (0.1, 0.6),
    "RDW-SD": (37, 50),
    "RDW-CV": (0, 15),
    "CRP": (0, 10),
    "hs-CRP": (0, 1.0),
}


def extract_value(result_str: str):
    """从结果字符串提取数值，支持 >10、<0.5 等格式。"""
    if not result_str or result_str.strip() in ("—", "–", "-", ""):
        return None
    s = result_str.strip().strip("*").strip()
    m = re.search(r"^[^0-9]*([0-9]+\.?\d*)", s)
    return float(m.group(1)) if m else None


def load_reports(raw_papers: Path):
    """扫描所有报告目录，读取 metadata.md 和 metrics.md。"""
    reports = []
    if not raw_papers.exists():
        return reports

    for dir_path in sorted(raw_papers.glob("lab_report_*")):
        if not dir_path.is_dir():
            continue

        meta_path = dir_path / "metadata.md"
        metrics_path = dir_path / "metrics.md"

        if not meta_path.exists():
            continue

def parse_metadata_table(text: str) -> dict:
    """解析 Markdown 表格格式的 metadata（| 字段 | 值 |）。"""
    row = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or "---" in line or line.startswith("|字段"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3 and parts[1]:
            key = parts[1].strip()
            val = parts[2].strip()
            if key:
                row[key] = val
    return row


def parse_metrics_yaml(text: str) -> dict:
    """解析 metrics.md 中的 YAML 格式数据。"""
    metrics = {}
    in_metrics = False
    for line in text.splitlines():
        if re.match(r"^\s*metrics\s*:", line):
            in_metrics = True
            continue
        if in_metrics and line.strip().startswith("- date:"):
            continue
        if in_metrics:
            m = re.match(r"^\s+(\w+)\s*:\s*(.+)$", line)
            if m:
                key, val = m.group(1).strip(), m.group(2).strip().strip('"').strip("'")
                if val and val.lower() != "null":
                    try:
                        metrics[key] = float(val)
                    except ValueError:
                        metrics[key] = val
            elif line.strip() and not line.startswith(" ") and not line.startswith("-"):
                in_metrics = False
    return metrics


def load_reports(raw_papers: Path):
    """扫描所有报告目录，读取 metadata.md 和 metrics.md。"""
    reports = []
    if not raw_papers.exists():
        return reports

    for dir_path in sorted(raw_papers.glob("lab_report_*")):
        if not dir_path.is_dir():
            continue

        meta_path = dir_path / "metadata.md"
        metrics_path = dir_path / "metrics.md"

        if not meta_path.exists():
            continue

        meta_text = meta_path.read_text(encoding="utf-8")
        meta = parse_metadata_table(meta_text)

        report_date = meta.get("报告日期", "") or meta.get("date", "")

        # 兼容表格格式的科室字段
        department = meta.get("科室", "") or meta.get("department", "")
        physician = meta.get("医生", "") or meta.get("physician", meta.get("送检医生", ""))
        visit_type = meta.get("报告类型", "") or meta.get("type", "")

        is_inpatient = "住院" in department

        row = {
            "report_id": dir_path.name,
            "report_date": report_date,
            "diagnosis": meta.get("诊断", ""),
            "department": department,
            "physician": physician,
            "visit_type": visit_type,
            "is_inpatient": is_inpatient,
        }

        # 读取 metrics.yaml
        metrics_data = {}
        if metrics_path.exists():
            metrics_text = metrics_path.read_text(encoding="utf-8")
            metrics_data = parse_metrics_yaml(metrics_text)

        # 映射 metrics.md 中的字段名到标准名
        METRIC_ALIASES = {
            "hsCRP": "hs-CRP",
            "CRP": "CRP",
            "WBC": "WBC",
            "RBC": "RBC",
            "HGB": "HGB",
            "HCT": "HCT",
            "PLT": "PLT",
            "PCT": "PCT",
            "P_LCR": "P-LCR",
            "MCV": "MCV",
            "MCH": "MCH",
            "MCHC": "MCHC",
            "NEUT_percent": "NEUT%",
            "NEUT_abs": "NEUT#",
            "LYMPH_percent": "LYMPH%",
            "LYMPH_abs": "LYMPH#",
            "MONO_percent": "MONO%",
            "MONO_abs": "MONO#",
            "EO_percent": "EO%",
            "EO_abs": "EO#",
            "BASO_percent": "BASO%",
            "BASO_abs": "BASO#",
            "RDW_SD": "RDW-SD",
            "RDW_CV": "RDW-CV",
            "MPV": "MPV",
            "PDW": "PDW",
        }

        for alias, std_name in METRIC_ALIASES.items():
            if alias in metrics_data:
                val = metrics_data[alias]
                row[std_name] = val
                # 判断异常状态
                ref = REF_RANGES.get(std_name)
                if ref and isinstance(val, (int, float)):
                    lo, hi = ref
                    status = ""
                    if val < lo:
                        status = "↓"
                    elif val > hi:
                        status = "↑"
                    row[f"{std_name}_status"] = status
                else:
                    row[f"{std_name}_status"] = ""

        reports.append(row)

    return reports


def to_csv(reports, output_path):
    """写入 CSV（宽表，每行一份报告）。"""
    if not reports:
        return

    # 列顺序：固定字段 + ALL_METRICS（数值 + 状态交替）
    fixed_cols = ["report_id", "report_date", "diagnosis", "department",
                  "physician", "visit_type", "is_inpatient"]
    metric_cols = []
    for m in ALL_METRICS:
        metric_cols.append(m)
        metric_cols.append(f"{m}_status")

    fieldnames = fixed_cols + metric_cols

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in reports:
            # 确保所有列都存在
            for col in fieldnames:
                r.setdefault(col, "")
            writer.writerow(r)

    print(f"CSV 已写入: {output_path}")


def to_json(reports, output_path):
    """写入 JSON（带元数据）。"""
    # 按日期排序
    reports_sorted = sorted(reports, key=lambda x: x["report_date"])

    # 计算报告时间范围
    dates = [r["report_date"] for r in reports_sorted if r["report_date"]]
    date_range = (min(dates), max(dates)) if dates else ("", "")

    output = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "report_count": len(reports),
        "date_range": {"start": date_range[0], "end": date_range[1]},
        "reports": reports_sorted,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"JSON 已写入: {output_path}")


def main():
    import os
    parser = argparse.ArgumentParser(description="数据加载：读取检验报告，生成结构化数据")
    parser.add_argument("--patient-id", required=True, help="诊疗卡号，如 513229198801040014")
    args = parser.parse_args()

    paths = build_paths(args.patient_id)

    # 前置检查：原始数据目录存在
    if not paths["raw_papers"].exists():
        print(f"❌ 原始数据目录不存在: {paths['raw_papers']}")
        print(f"   预期路径: raw/patient_{{patient_id}}/papers/lab_report_*/")
        print(f"   当前 patient_id: {args.patient_id}")
        sys.exit(1)

    reports = load_reports(paths["raw_papers"])
    if not reports:
        print("❌ 未找到任何报告（lab_report_*/ 目录），退出")
        sys.exit(1)

    print(f"[{datetime.now().isoformat()}] 数据加载开始...")
    print(f"  病人: {args.patient_id}")
    print(f"  原始数据: {paths['raw_papers']}")
    print(f"  输出目录: {paths['output_dir']}")

    paths["output_dir"].mkdir(parents=True, exist_ok=True)

    print(f"找到 {len(reports)} 份报告")

    for r in reports:
        print(f"  {r['report_date']} | {r['diagnosis']}")

    to_csv(reports, paths["csv"])
    to_json(reports, paths["json"])

    print(f"[{datetime.now().isoformat()}] 数据加载完成")


if __name__ == "__main__":
    main()
