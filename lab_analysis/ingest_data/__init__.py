"""ingest_data — 统一数据摄入脚本。

支持的数据类型：
1. lab_image: 检验报告图片（JPG/PNG）
2. mri_dicom: MRI DICOM 序列（ZIP 压缩包或目录）
3. mri_report: MRI 文字报告（PDF/TXT/JPG）

用法示例：
  # 检验报告图片
  python -m lab_analysis.ingest_data --type lab_image \\
      --path "lab_2026-03-24.jpg" \\
      --id-card "YOUR_ID_CARD" --report-date "2026-03-24" --report-type "outpatient"

  # MRI DICOM ZIP 文件
  python -m lab_analysis.ingest_data --type mri_dicom \\
      --zip-path "export_part1.zip" \\
      --id-card "YOUR_ID_CARD" --report-date "2026-04-11"

强制要求：
- 所有数据必须提供有效的患者身份证号（18 位或 15 位数字）
- 如果无法识别身份证号 → 交互式输入
- 如果不是身份证号格式 → 交互式确认或放弃
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from lab_analysis.patient_id import validate_id_card

from ._log import WORK_ROOT, _ensure_handlers, append_log, logger
from .batch import print_batch_summary, process_batch
from .dicom import ingest_mri_dicom
from .lab import ingest_lab_image
from .report import ingest_mri_report

# P1-2: import 期就建立 logger handlers (但 FileHandler 内部已降级为 OSError-best-effort)
_ensure_handlers()

__all__ = [
    "ingest_lab_image",
    "ingest_mri_dicom",
    "ingest_mri_report",
    "process_batch",
    "print_batch_summary",
    "append_log",
    "WORK_ROOT",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="统一数据摄入脚本")
    parser.add_argument(
        "--type",
        "-t",
        required=True,
        choices=["lab_image", "mri_dicom", "mri_report"],
        help="数据类型",
    )
    parser.add_argument("--path", help="文件路径（lab_image / mri_report）")
    parser.add_argument("--zip-path", help="ZIP 文件路径（mri_dicom）")
    parser.add_argument("--dicom-dir", help="DICOM 目录路径（mri_dicom）")
    parser.add_argument("--id-card", help="脱敏 ID（pipeline 模式必填）")
    parser.add_argument("--report-date", help="报告日期（YYYY-MM-DD）")
    parser.add_argument(
        "--report-type", default="outpatient", help="报告类型（outpatient/inpatient）"
    )
    parser.add_argument("--batch", action="store_true", help="批量模式")
    args = parser.parse_args()

    id_card = args.id_card or os.environ.get("LAB_RAW_ID_CARD", "")
    if not id_card:
        logger.error("[ERROR] 必须提供 --id-card 或设置 LAB_RAW_ID_CARD 环境变量")
        raise SystemExit(1)

    if not validate_id_card(id_card):
        logger.error("[ERROR] 身份证号格式无效")
        raise SystemExit(1)

    if args.type == "lab_image":
        if not args.path:
            logger.error("[ERROR] lab_image 需要 --path")
            raise SystemExit(1)
        record = ingest_lab_image(
            Path(args.path), id_card, args.report_date or "", args.report_type
        )
        logger.info(f"[OK] 检验图片摄入成功: {record['saved_path']}")

    elif args.type == "mri_dicom":
        if args.zip_path:
            record = ingest_mri_dicom(
                zip_path=Path(args.zip_path),
                patient_id=id_card,
                report_date=args.report_date,
            )
        elif args.dicom_dir:
            record = ingest_mri_dicom(
                dicom_dir=Path(args.dicom_dir),
                patient_id=id_card,
                report_date=args.report_date,
            )
        else:
            logger.error("[ERROR] mri_dicom 需要 --zip-path 或 --dicom-dir")
            raise SystemExit(1)
        logger.info(f"[OK] MRI DICOM 摄入成功: {record['sequence_count']} 个序列")

    elif args.type == "mri_report":
        if not args.path:
            logger.error("[ERROR] mri_report 需要 --path")
            raise SystemExit(1)
        record = ingest_mri_report(Path(args.path), id_card, args.report_date or "")
        logger.info(f"[OK] MRI 报告摄入成功: {record['saved_path']}")


if __name__ == "__main__":
    main()
