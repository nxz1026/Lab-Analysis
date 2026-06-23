"""lab_analysis.pipeline.ingest — 自动数据摄入"""

from __future__ import annotations

import argparse
import traceback

from lab_analysis.utils import WORK_ROOT

from .. import _log

logger = _log.get_logger(__name__)


def auto_ingest_from_origin_data(
    id_card: str,
    report_date: str | None = None,
    report_type: str | None = None,
    no_interactive: bool = False,
) -> bool:
    """从 Origin_data 目录自动摄入数据。"""
    origin_data_dir = WORK_ROOT / "raw" / "Origin_data"
    if not origin_data_dir.exists():
        logger.info(f"[INFO] Origin_data 目录不存在: {origin_data_dir}")
        return False
    lab_images = list(origin_data_dir.glob("lab_*.jpg")) + list(origin_data_dir.glob("lab_*.png"))
    mri_images = list(origin_data_dir.glob("mri_*.jpg")) + list(origin_data_dir.glob("mri_*.png"))
    dicom_zips = list(origin_data_dir.glob("export_*.zip")) + list(
        origin_data_dir.glob("dicom_*.zip")
    )
    dcm_files = list(origin_data_dir.glob("*.dcm"))
    if not any([lab_images, mri_images, dicom_zips, dcm_files]):
        logger.info("[INFO] Origin_data 目录中没有找到任何可处理的文件")
        return False
    logger.info(f"\n{'=' * 60}\n[STEP ①] 自动数据摄入 - 从 Origin_data 目录\n{'=' * 60}")
    print(
        f"发现 {len(lab_images)} 张检验报告图片, {len(mri_images)} 张MRI报告图片, {len(dicom_zips)} 个DICOM压缩包, {len(dcm_files)} 个DICOM文件"
    )
    total_success = 0
    if lab_images:
        logger.info(f"\n{'─' * 60}\n【检验报告处理】\n{'─' * 60}")
        for idx, img_path in enumerate(lab_images, 1):
            logger.info(f"\n[{idx}/{len(lab_images)}] 处理: {img_path.name}")
            try:
                filename = img_path.stem
                parts = filename.split("_")
                extracted_date = next((p for p in parts if "-" in p and len(p) == 10), None)
                extracted_type = next((p for p in parts if p in ["outpatient", "inpatient"]), None)
                final_date = report_date or extracted_date
                final_type = report_type or extracted_type or "outpatient"
                logger.info(f"  报告日期: {final_date or '未指定'}\n  报告类型: {final_type}")
                from lab_analysis import extract_lab_data

                args_lab = argparse.Namespace(
                    image=str(img_path), id_card=id_card, no_interactive=no_interactive
                )
                if extract_lab_data.main_with_args(args_lab):
                    total_success += 1
                    logger.info("  [OK] 摄入成功")
                else:
                    logger.error("  [FAIL] 摄入失败")
            except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
                logger.info(f"  [ERROR] 处理失败: {e}")
                traceback.print_exc()
    if mri_images:
        logger.info(f"\n{'─' * 60}\n【MRI报告处理】\n{'─' * 60}")
        for idx, img_path in enumerate(mri_images, 1):
            logger.info(f"\n[{idx}/{len(mri_images)}] 处理: {img_path.name}")
            try:
                parts = img_path.stem.split("_")
                extracted_date = next((p for p in parts if "-" in p and len(p) == 10), None)
                final_date = report_date or extracted_date
                logger.info(f"  报告日期: {final_date or '未指定'}")
                from lab_analysis import ingest_data

                if ingest_data.ingest_mri_report(
                    report_path=img_path, patient_id=id_card, report_date=final_date
                ):
                    total_success += 1
                    logger.info("  [OK] MRI报告摄入成功")
                else:
                    logger.error("  [FAIL] MRI报告摄入失败")
            except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
                logger.info(f"  [ERROR] 处理失败: {e}")
                traceback.print_exc()
    if dicom_zips:
        logger.info(f"\n{'─' * 60}\n【DICOM压缩包处理】\n{'─' * 60}")
        for idx, zip_path in enumerate(dicom_zips, 1):
            logger.info(f"\n[{idx}/{len(dicom_zips)}] 处理: {zip_path.name}")
            try:
                parts = zip_path.stem.split("_")
                extracted_date = next((p for p in parts if "-" in p and len(p) == 10), None)
                final_date = report_date or extracted_date
                logger.info(f"  报告日期: {final_date or '未指定'}")
                from lab_analysis import ingest_data

                if ingest_data.ingest_mri_dicom(
                    zip_path=zip_path, patient_id=id_card, report_date=final_date
                ):
                    total_success += 1
                    logger.info("  [OK] DICOM压缩包摄入成功")
                else:
                    logger.error("  [FAIL] DICOM压缩包摄入失败")
            except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
                logger.info(f"  [ERROR] 处理失败: {e}")
                traceback.print_exc()
    if dcm_files:
        logger.info(f"\n{'─' * 60}\n【DICOM文件处理】\n{'─' * 60}")
        print(
            f"  [WARNING] 发现 {len(dcm_files)} 个DICOM文件在根目录\n  [INFO] 建议将DICOM文件组织到子目录或使用ZIP压缩包\n  [INFO] 跳过直接处理，请使用 --ingest-dicom-dir 手动指定"
        )
    total_files = len(lab_images) + len(mri_images) + len(dicom_zips)
    print(
        f"\n{'=' * 60}\n数据摄入完成: 共处理 {total_files} 个文件，成功 {total_success} 个\n{'=' * 60}\n"
    )
    return total_success > 0
