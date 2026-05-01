#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_loader.py
读取所有 lab_report_*/metrics.md，提取数值写入 data/lab_metrics.csv（宽表）+ data/lab_metrics.json
"""

import re
import csv
import json
from datetime import datetime
from pathlib import Path

WIKI_ROOT = Path.home() / "wiki"
RAW_PAPERS = WIKI_ROOT / "raw" / "papers"
OUTPUT_DIR = WIKI_ROOT / "data"
OUTPUT_CSV = OUTPUT_DIR / "lab_metrics.csv"
OUTPUT_JSON = OUTPUT_DIR / "lab_metrics.json"

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


def load_reports():
    """扫描所有报告目录，读取 metadata.md 和 metrics.md。"""
    reports = []
    if not RAW_PAPERS.exists():
        return reports

    for dir_path in sorted(RAW_PAPERS.glob("lab_report_*")):
        if not dir_path.is_dir():
            continue

        meta_path = dir_path / "metadata.md"
        metrics_path = dir_path / "metrics.md"

        if not meta_path.exists():
            continue

        # 读取 metadata
        meta_text = meta_path.read_text(encoding="utf-8")

        date_m = re.search(r'report_date:\s*"?(\d{4}-\d{2}-\d{2})"?', meta_text)
        report_date = date_m.group(1) if date_m else ""

        diag_m = re.search(r"primary_diagnosis:\s*(.+?)(?:\n|$)", meta_text)
        diagnosis = diag_m.group(1).strip() if diag_m else ""

        dept_m = re.search(r"department:\s*(.+?)(?:\n|$)", meta_text)
        department = dept_m.group(1).strip() if dept_m else ""

        physician_m = re.search(r"attending_physician:\s*(.+?)(?:\n|$)", meta_text)
        physician = physician_m.group(1).strip() if physician_m else ""

        visit_m = re.search(r"visit_type:\s*(.+?)(?:\n|$)", meta_text)
        visit_type = visit_m.group(1).strip() if visit_m else ""

        is_inpatient = "住院" in department

        # 读取 metrics
        row = {
            "report_id": dir_path.name,
            "report_date": report_date,
            "diagnosis": diagnosis,
            "department": department,
            "physician": physician,
            "visit_type": visit_type,
            "is_inpatient": is_inpatient,
        }

        metrics_text = ""
        if metrics_path.exists():
            metrics_text = metrics_path.read_text(encoding="utf-8")

        # 按字符串长度从长到短排序，避免子串被短名先匹配
        metrics_sorted = sorted(ALL_METRICS, key=lambda x: -len(x))

        for line in metrics_text.split("\n"):
            if "|" not in line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 6:
                continue
            # 在当前行匹配指标
            for metric in metrics_sorted:
                item_col = None
                for i, p in enumerate(parts):
                    # 精确匹配：指标名必须是该列的主要内容
                    if p == metric or p.startswith(metric + "（") or p.startswith(metric + " "):
                        item_col = i
                        break
                if item_col is None:
                    continue
                result_col = item_col + 1
                if result_col >= len(parts):
                    continue
                result_str = parts[result_col]
                # 跳过中文描述行
                if re.search(r"[\u4e00-\u9fff]", result_str) and len(result_str) > 3:
                    continue
                val = extract_value(result_str)
                # 判断状态（↑↓）
                status = ""
                for p in parts:
                    if "↑" in p:
                        status = "↑"
                        break
                    elif "↓" in p:
                        status = "↓"
                        break
                row[metric] = val
                row[f"{metric}_status"] = status
                break  # 一个指标只取第一行

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
    print(f"[{datetime.now().isoformat()}] 数据加载开始...")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    reports = load_reports()
    print(f"找到 {len(reports)} 份报告")

    if not reports:
        print("没有报告，退出")
        return

    for r in reports:
        print(f"  {r['report_date']} | {r['diagnosis']}")

    to_csv(reports, OUTPUT_CSV)
    to_json(reports, OUTPUT_JSON)

    print(f"[{datetime.now().isoformat()}] 数据加载完成")


if __name__ == "__main__":
    main()
