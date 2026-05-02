#!/usr/bin/env python3
"""从 lab_report_*/metrics.md 提取检验数据，输出 CSV + JSON"""
import re, csv, json, argparse
from datetime import datetime
from pathlib import Path

WIKI_ROOT = Path.home() / "wiki"

# 指标别名映射
METRIC_ALIASES = {
    "hsCRP": "hs-CRP", "P_LCR": "P-LCR", "RDW_SD": "RDW-SD", "RDW_CV": "RDW-CV",
    "NEUT_percent": "NEUT%", "NEUT_abs": "NEUT#", "LYMPH_percent": "LYMPH%",
    "LYMPH_abs": "LYMPH#", "MONO_percent": "MONO%", "MONO_abs": "MONO#",
    "EO_percent": "EO%", "EO_abs": "EO#", "BASO_percent": "BASO%", "BASO_abs": "BASO#",
}

ALL_METRICS = [
    "WBC", "RBC", "HGB", "HCT", "PLT", "PCT", "P-LCR",
    "MCV", "MCH", "MCHC", "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%",
    "NEUT#", "LYMPH#", "MONO#", "EO#", "BASO#",
    "RDW-SD", "RDW-CV", "MPV", "PDW", "CRP", "hs-CRP",
]

REF_RANGES = {
    "WBC": (3.5, 9.5), "RBC": (4.3, 5.8), "HGB": (130, 175), "HCT": (40, 50),
    "PLT": (125, 350), "PCT": (0.108, 0.272), "NEUT%": (40, 75), "LYMPH%": (20, 50),
    "MONO%": (2, 10), "EO%": (0.4, 8), "BASO%": (0, 1),
    "NEUT#": (1.8, 6.3), "LYMPH#": (1.1, 3.2), "MONO#": (0.1, 0.6),
    "RDW-SD": (37, 50), "RDW-CV": (0, 15), "CRP": (0, 10), "hs-CRP": (0, 1.0),
}


def parse_meta(text):
    """解析 metadata.md 表格"""
    return {p[1]: p[2] for line in text.splitlines()
            if line.startswith("|") and "---" not in line
            for p in [line.split("|")] if len(p) >= 3}


def parse_metrics(text):
    """解析 metrics.md YAML 数据"""
    data, in_m = {}, False
    for line in text.splitlines():
        if re.match(r"^\s*metrics\s*:", line): in_m = True; continue
        if in_m and line.strip().startswith("- date:"): continue
        m = re.match(r"^\s+(\w+)\s*:\s*(.+)$", line)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip().strip('"').strip("'")
            try: data[k] = float(v) if v.lower() != "null" else None
            except: data[k] = v
        elif in_m and line.strip() and not line.startswith(" ") and not line.startswith("-"):
            in_m = False
    return data


def load_reports(raw_dir):
    """扫描 lab_report_* 目录，提取报告数据"""
    reports = []
    for d in sorted(Path(raw_dir).glob("lab_report_*")) if Path(raw_dir).exists() else []:
        meta = parse_meta((d / "metadata.md").read_text(encoding="utf-8")) if (d / "metadata.md").exists() else {}
        metrics = parse_metrics((d / "metrics.md").read_text(encoding="utf-8")) if (d / "metrics.md").exists() else {}

        row = {
            "report_id": d.name,
            "report_date": meta.get("报告日期") or meta.get("date", ""),
            "diagnosis": meta.get("诊断", ""),
            "department": meta.get("科室") or meta.get("department", ""),
            "physician": meta.get("医生") or meta.get("physician", ""),
            "visit_type": meta.get("报告类型") or meta.get("type", ""),
            "is_inpatient": "住院" in (meta.get("科室") or ""),
        }

        for alias, std in METRIC_ALIASES.items():
            if alias in metrics:
                row[std] = val = metrics[alias]
                ref = REF_RANGES.get(std)
                row[f"{std}_status"] = ("↓" if val < ref[0] else "↑" if val > ref[1] else "") if ref and isinstance(val, (int, float)) else ""
        reports.append(row)
    return reports


def save_csv(reports, path):
    fixed = ["report_id", "report_date", "diagnosis", "department", "physician", "visit_type", "is_inpatient"]
    cols = fixed + [m for m in ALL_METRICS for m in (m, f"{m}_status")]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); [w.writerow({**r, **{c: "" for c in cols}} | r) for r in reports]
    print(f"CSV: {path}")


def save_json(reports, path):
    out = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "report_count": len(reports),
           "reports": sorted(reports, key=lambda x: x["report_date"])}
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"JSON: {path}")


def main():
    p = argparse.ArgumentParser(); p.add_argument("--patient-id", required=True); args = p.parse_args()
    raw = WIKI_ROOT / "raw" / f"patient_{args.patient_id}" / "papers"
    out = WIKI_ROOT / "data" / args.patient_id; out.mkdir(parents=True, exist_ok=True)

    reports = load_reports(raw)
    print(f"找到 {len(reports)} 份报告")
    [[print(f"  {r['report_date']} | {r['diagnosis']}")] for r in reports]
    save_csv(reports, out / "lab_metrics.csv")
    save_json(reports, out / "lab_metrics.json")


if __name__ == "__main__":
    main()
