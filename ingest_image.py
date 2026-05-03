#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_image.py — 第0步自动化（存盘脚本）

用法（由 Hermes 调用，不单独使用）：
  python ingest_image.py --path /root/wiki/raw/xxx.jpg \
      --patient-id 513229198801040014 \
      --report-date 2026-03-24 \
      --report-type outpatient

流程：
  1. encode(patient_id) 脱敏
  2. 保存图片到 raw/patient_{脱敏ID}/lab/
  3. 记录摄入日志
"""
import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from patient_id import encode

WIKI_ROOT = Path(os.environ.get("WIKI_ROOT", "/root/wiki"))
INGEST_LOG = WIKI_ROOT / ".ingest_log.json"


def save_image(image_path: Path, patient_id_obf: str, report_date: str, report_type: str) -> str:
    """保存图片到 raw/patient_{脱敏ID}/lab/"""
    lab_dir = WIKI_ROOT / "raw" / f"patient_{patient_id_obf}" / "lab"
    lab_dir.mkdir(parents=True, exist_ok=True)

    dest_name = f"lab_{report_date}_{report_type}.jpg"
    dest_path = lab_dir / dest_name

    if dest_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        dest_path = lab_dir / f"lab_{report_date}_{report_type}_{ts}.jpg"

    shutil.copy2(image_path, dest_path)
    return str(dest_path.relative_to(WIKI_ROOT))


def load_log() -> dict:
    if INGEST_LOG.exists():
        return json.loads(INGEST_LOG.read_text(encoding="utf-8"))
    return {"ingested": []}


def append_log(record: dict):
    log = load_log()
    log["ingested"].append(record)
    log["last_updated"] = datetime.now().isoformat()
    INGEST_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="检验报告图片摄入 — 第0步（存盘）")
    parser.add_argument("--path", "-p", required=True, type=Path, help="图片路径")
    parser.add_argument("--patient-id", required=True, help="患者ID（脱敏前）")
    parser.add_argument("--report-date", required=True, help="报告日期 YYYY-MM-DD")
    parser.add_argument("--report-type", required=True, help="outpatient / inpatient")
    parser.add_argument("--confidence", type=float, default=1.0, help="vision 识别置信度")
    args = parser.parse_args()

    image_path = args.path
    if not image_path.exists():
        print(f"❌ 文件不存在: {image_path}")
        return 1

    patient_id_raw = args.patient_id
    patient_id_obf = encode(patient_id_raw)
    report_date = args.report_date
    report_type = args.report_type

    print(f"🔒 脱敏: {patient_id_raw} → {patient_id_obf}")
    print(f"📅 日期: {report_date}")
    print(f"🏥 类型: {report_type}")
    print(f"📷 来源: {image_path}")

    saved_path = save_image(image_path, patient_id_obf, report_date, report_type)
    print(f"✅ 已保存: {saved_path}")

    record = {
        "timestamp": datetime.now().isoformat(),
        "image_path": str(image_path),
        "saved_path": saved_path,
        "patient_id_raw": patient_id_raw,
        "patient_id_obf": patient_id_obf,
        "report_date": report_date,
        "report_type": report_type,
        "confidence": args.confidence,
    }
    append_log(record)
    print(f"📊 摄入记录已保存，共 {len(load_log())['ingested']} 条")

    # 提示用户是否执行后续流程
    print("\n" + "=" * 50)
    print("📤 摄入完成，是否执行后续 Pipeline？")
    print("   回复「执行」开始 7 步分析")
    print("   回复「继续追加」保存更多图片，稍后一起分析")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    sys.exit(main())
