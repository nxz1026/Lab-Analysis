"""ingest_data.dicom — MRI DICOM 摄入 + 序列重命名。"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from lab_analysis.utils import print_progress

from ._log import WORK_ROOT, append_log, logger


def extract_dicom_from_zip(zip_path: Path, temp_dir: Path) -> Path:
    """从 ZIP 文件中提取 DICOM 数据到临时目录，返回最佳 DICOM 目录。"""
    logger.info(f"开始解压 ZIP 文件: {zip_path}")
    logger.info(f"[Ingest] 正在解压: {zip_path.name}")
    try:
        with ZipFile(zip_path, "r") as zip_ref:
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            logger.debug(f"ZIP 文件包含 {total_files} 个文件")
            zip_ref.extractall(temp_dir)
            logger.info(f"ZIP 文件解压完成: {temp_dir}")
    except PermissionError as e:
        logger.error(f"权限错误: {e}")
        raise PermissionError(
            f"无法写入临时目录 {temp_dir}。\n可能原因：\n"
            "  1. 在沙箱环境中运行，需要外部路径访问权限\n"
            "  2. 临时目录权限不足\n"
            "解决方案：\n"
            "  - 在沙箱外运行此命令（设置 required_permissions='all'）\n"
            "  - 或手动解压 ZIP 文件后使用 --dicom-dir 参数"
        ) from e

    dcm_files = list(temp_dir.rglob("*.dcm"))
    if not dcm_files:
        logger.error(f"ZIP 文件中未找到 .dcm 文件: {zip_path}")
        raise FileNotFoundError(
            f"ZIP 文件中未找到 .dcm 文件: {zip_path}\n请确认 ZIP 文件格式正确，包含 DICOM 序列数据"
        )
    logger.info(f"找到 {len(dcm_files)} 个 DICOM 文件")
    logger.info(f"[Ingest] 找到 {len(dcm_files)} 个 DICOM 文件")

    subdirs = [item for item in temp_dir.iterdir() if item.is_dir()]
    if subdirs:
        logger.info(f"发现 {len(subdirs)} 个子目录，将作为序列目录处理")
        logger.info(f"[Ingest] 发现 {len(subdirs)} 个子目录，将作为序列目录处理")
        return temp_dir

    dir_counts: dict[Path, int] = {}
    for dcm_file in dcm_files:
        parent = dcm_file.parent
        dir_counts[parent] = dir_counts.get(parent, 0) + 1
    best_dir = max(dir_counts, key=dir_counts.get)
    logger.info(f"最佳目录: {best_dir}")
    logger.info(f"[Ingest] 最佳目录: {best_dir}")
    return best_dir


def rename_dicom_sequences(source_dir: Path, target_dir: Path) -> int:
    """将 DICOM 序列目录重命名为 seq_01, seq_02, ...。返回成功数量。"""
    logger.info(f"开始处理 DICOM 序列: {source_dir}")
    if not target_dir.exists():
        logger.info(f"创建目标目录: {target_dir}")
        target_dir.mkdir(parents=True, exist_ok=True)

    seq_dirs: list[tuple[Path, int]] = []
    for item in source_dir.iterdir():
        if item.is_dir():
            dcm_count = len(list(item.glob("*.dcm")))
            if dcm_count > 0:
                seq_dirs.append((item, dcm_count))
    seq_dirs.sort(key=lambda x: x[0].name)
    total = len(seq_dirs)
    logger.info(f"找到 {total} 个 DICOM 序列")

    count = 0
    skipped = 0
    for idx, (seq_dir, dcm_count) in enumerate(seq_dirs, 1):
        seq_name = f"seq_{idx:02d}"
        dest_seq_dir = target_dir / seq_name
        print_progress(
            idx, total, prefix="处理序列:", suffix=f"{seq_dir.name} ({dcm_count} frames)"
        )
        if dest_seq_dir.exists():
            logger.debug(f"跳过已存在的序列: {seq_name}")
            skipped += 1
            continue
        try:
            shutil.copytree(seq_dir, dest_seq_dir)
            logger.debug(f"成功复制: {seq_dir.name} -> {seq_name} ({dcm_count} frames)")
            count += 1
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.error(f"复制失败 {seq_dir.name}: {e}")
            logger.info(f"\n[ERROR] 复制失败: {seq_dir.name} - {e}")

    logger.info(f"DICOM 序列处理完成: 成功 {count} 个, 跳过 {skipped} 个")
    return count


def ingest_mri_dicom(
    zip_path: Path | None = None,
    dicom_dir: Path | None = None,
    patient_id: str | None = None,
    report_date: str | None = None,
) -> dict:
    """摄入 MRI DICOM 数据。"""
    from lab_analysis.pipeline.cli import get_deid

    patient_id_obf = get_deid(patient_id)
    imaging_dir = WORK_ROOT / "raw" / f"patient_{patient_id_obf}" / "imaging"
    imaging_dir.mkdir(parents=True, exist_ok=True)

    if zip_path:
        temp_dir = Path(tempfile.mkdtemp(prefix="dicom_extract_"))
        try:
            source_dir = extract_dicom_from_zip(zip_path, temp_dir)
            seq_count = rename_dicom_sequences(source_dir, imaging_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    elif dicom_dir:
        seq_count = rename_dicom_sequences(dicom_dir, imaging_dir)
    else:
        raise ValueError("必须提供 --zip-path 或 --dicom-dir")

    record = {
        "timestamp": datetime.now().isoformat(),
        "type": "mri_dicom",
        "source_path": str(zip_path or dicom_dir),
        "saved_dir": str(imaging_dir.relative_to(WORK_ROOT)),
        "patient_id_obf": patient_id_obf,
        "report_date": report_date,
        "sequence_count": seq_count,
    }
    append_log(record)
    return record
