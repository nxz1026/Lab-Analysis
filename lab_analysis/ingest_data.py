#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ingest_data.py — 统一数据摄入脚本

支持的数据类型：
1. lab_image: 检验报告图片（JPG/PNG）
2. mri_dicom: MRI DICOM 序列（ZIP压缩包或目录）
3. mri_report: MRI 文字报告（PDF/TXT/JPG）

用法示例：
  # 检验报告图片
  python -m lab_analysis.ingest_data --type lab_image \
      --path "lab_2026-03-24.jpg" \
      --patient-id "513229198801040014" \
      --report-date "2026-03-24" \
      --report-type "outpatient"

  # MRI DICOM ZIP文件
  python -m lab_analysis.ingest_data --type mri_dicom \
      --zip-path "export_part1.zip" \
      --patient-id "513229198801040014" \
      --report-date "2026-04-11"

  # MRI DICOM 已解压目录
  python -m lab_analysis.ingest_data --type mri_dicom \
      --dicom-dir "dicom_temp/" \
      --patient-id "513229198801040014" \
      --report-date "2026-04-11"

  # MRI 文字报告
  python -m lab_analysis.ingest_data --type mri_report \
      --path "mri_report.pdf" \
      --patient-id "513229198801040014" \
      --report-date "2026-04-11"

强制要求：
- 所有数据必须提供有效的患者身份证号（18位或15位数字）
- 如果无法识别患者ID → 交互式输入
- 如果ID不是身份证号格式 → 交互式输入或放弃
"""
import argparse
import json
import logging
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

from lab_analysis.patient_id import encode

WIKI_ROOT = Path(os.environ.get("WIKI_ROOT", "/root/wiki"))
INGEST_LOG = WIKI_ROOT / ".ingest_log.json"
LOG_FILE = WIKI_ROOT / ".ingest_debug.log"

# 配置日志记录器
logger = logging.getLogger("ingest_data")
logger.setLevel(logging.DEBUG)

# 文件处理器（详细日志）
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
file_handler.setFormatter(file_format)
logger.addHandler(file_handler)

# 控制台处理器（简洁输出）
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter("%(message)s")
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)


def is_valid_id_card(patient_id: str) -> bool:
    """验证是否为有效的身份证号格式（18位或15位数字，最后一位可能是X）"""
    pattern = r'^\d{17}[\dXx]$|^\d{15}$'
    return bool(re.match(pattern, patient_id))


def print_progress(current: int, total: int, prefix: str = "", suffix: str = "", bar_length: int = 30):
    """打印进度条"""
    if total == 0:
        return
    fraction = current / total
    filled = int(bar_length * fraction)
    bar = "=" * filled + "-" * (bar_length - filled)
    percent = f"{fraction * 100:.1f}%"
    print(f"\r{prefix} |{bar}| {percent} {suffix}", end="", flush=True)
    if current >= total:
        print()  # 完成后换行


def process_batch(items: list, process_func: callable, batch_mode: bool, item_name: str = "项") -> tuple:
    """
    通用批量处理函数
    
    Args:
        items: 要处理的项目列表
        process_func: 处理单个项目的函数，接收一个项目作为参数
        batch_mode: 是否批量模式
        item_name: 项目名称（用于显示）
    
    Returns:
        (success_count, fail_count) 元组
    """
    total = len(items)
    success_count = 0
    fail_count = 0
    
    for idx, item in enumerate(items, 1):
        if batch_mode:
            # 如果是元组，提取第一个元素（通常是Path对象）
            display_item = item[0] if isinstance(item, tuple) else item
            print(f"\n{'='*60}")
            print(f"[{idx}/{total}] 处理: {display_item.name if hasattr(display_item, 'name') else display_item}")
            print(f"{'='*60}")
        
        try:
            result = process_func(item)
            if result:
                append_log(result)
                success_count += 1
                if not batch_mode:
                    print(f"[OK] {item_name}摄入成功")
            else:
                fail_count += 1
                if not batch_mode:
                    return success_count, fail_count
        except Exception as e:
            logger.error(f"摄入失败 {item}: {e}")
            print(f"[ERROR] 摄入失败: {e}")
            fail_count += 1
            if not batch_mode:
                raise
    
    return success_count, fail_count


def validate_patient_id(patient_id: str, interactive: bool = True) -> str:
    """
    验证患者ID，如果不是身份证号则要求用户输入或放弃
    
    Returns:
        有效的患者ID，或者用户选择放弃时返回 None
    """
    if not patient_id:
        print("[ERROR] 未提供患者ID")
        if not interactive:
            return None
        patient_id = input("请输入患者身份证号（18位或15位）: ").strip()
    
    if not is_valid_id_card(patient_id):
        print(f"[WARNING] 患者ID '{patient_id}' 不是有效的身份证号格式")
        if not interactive:
            print("[ERROR] 非交互模式下必须提供有效的身份证号")
            return None
        
        print("\n请选择:")
        print("  1. 重新输入正确的身份证号")
        print("  2. 放弃此数据")
        choice = input("请输入选择 (1/2): ").strip()
        
        if choice == "1":
            patient_id = input("请输入患者身份证号: ").strip()
            if not is_valid_id_card(patient_id):
                print(f"[ERROR] 输入的ID '{patient_id}' 仍然无效，放弃此数据")
                return None
        elif choice == "2":
            print("[INFO] 用户选择放弃此数据")
            return None
        else:
            print("[ERROR] 无效的选择，默认放弃此数据")
            return None
    
    return patient_id


def save_image(image_path: Path, patient_id_obf: str, report_date: str, 
               report_type: str, data_type: str = "lab") -> str:
    """保存图片到 raw/patient_{脱敏ID}/{data_type}/"""
    target_dir = WIKI_ROOT / "raw" / f"patient_{patient_id_obf}" / data_type
    target_dir.mkdir(parents=True, exist_ok=True)
    
    dest_name = image_path.name
    dest_path = target_dir / dest_name
    
    if dest_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        stem = image_path.stem
        suffix = image_path.suffix
        dest_path = target_dir / f"{stem}_{ts}{suffix}"
    
    shutil.copy2(image_path, dest_path)
    return str(dest_path.relative_to(WIKI_ROOT))


def ingest_lab_image(image_path: Path, patient_id: str, report_date: str, 
                     report_type: str) -> dict:
    """摄入检验报告图片"""
    patient_id_obf = encode(patient_id)
    saved_path = save_image(image_path, patient_id_obf, report_date, report_type, "lab")
    
    record = {
        "timestamp": datetime.now().isoformat(),
        "type": "lab_image",
        "source_path": str(image_path),
        "saved_path": saved_path,
        "patient_id_raw": patient_id,
        "patient_id_obf": patient_id_obf,
        "report_date": report_date,
        "report_type": report_type,
    }
    return record


def extract_dicom_from_zip(zip_path: Path, temp_dir: Path) -> Path:
    """从ZIP文件中提取DICOM数据到临时目录"""
    logger.info(f"开始解压ZIP文件: {zip_path}")
    print(f"[Ingest] 正在解压: {zip_path.name}")
    
    try:
        with ZipFile(zip_path, 'r') as zip_ref:
            file_list = zip_ref.namelist()
            total_files = len(file_list)
            logger.debug(f"ZIP文件包含 {total_files} 个文件")
            
            # 解压所有文件
            zip_ref.extractall(temp_dir)
            logger.info(f"ZIP文件解压完成: {temp_dir}")
    except PermissionError as e:
        logger.error(f"权限错误: {e}")
        raise PermissionError(
            f"无法写入临时目录 {temp_dir}。\n"
            f"可能原因：\n"
            f"  1. 在沙箱环境中运行，需要外部路径访问权限\n"
            f"  2. 临时目录权限不足\n"
            f"解决方案：\n"
            f"  - 在沙箱外运行此命令（设置 required_permissions='all'）\n"
            f"  - 或手动解压ZIP文件后使用 --dicom-dir 参数"
        ) from e
    
    # 查找所有.dcm文件
    dcm_files = list(temp_dir.rglob("*.dcm"))
    if not dcm_files:
        logger.error(f"ZIP文件中未找到.dcm文件: {zip_path}")
        raise FileNotFoundError(
            f"ZIP文件中未找到.dcm文件: {zip_path}\n"
            f"请确认ZIP文件格式正确，包含DICOM序列数据"
        )
    
    logger.info(f"找到 {len(dcm_files)} 个DICOM文件")
    print(f"[Ingest] 找到 {len(dcm_files)} 个DICOM文件")
    
    # 检查根目录下是否有子目录（序列目录）
    subdirs = [item for item in temp_dir.iterdir() if item.is_dir()]
    if subdirs:
        # 如果有子目录，返回根目录（让rename_dicom_sequences处理）
        logger.info(f"发现 {len(subdirs)} 个子目录，将作为序列目录处理")
        print(f"[Ingest] 发现 {len(subdirs)} 个子目录，将作为序列目录处理")
        return temp_dir
    else:
        # 如果没有子目录，查找包含最多.dcm文件的父目录
        dir_counts = {}
        for dcm_file in dcm_files:
            parent = dcm_file.parent
            dir_counts[parent] = dir_counts.get(parent, 0) + 1
        
        best_dir = max(dir_counts, key=dir_counts.get)
        logger.info(f"最佳目录: {best_dir}")
        print(f"[Ingest] 最佳目录: {best_dir}")
        return best_dir


def rename_dicom_sequences(source_dir: Path, target_dir: Path) -> int:
    """将DICOM序列目录重命名为 seq_01, seq_02, ..."""
    logger.info(f"开始处理DICOM序列: {source_dir}")
    
    # 查找所有包含.dcm文件的子目录（直接子目录）
    seq_dirs = []
    for item in source_dir.iterdir():
        if item.is_dir():
            dcm_count = len(list(item.glob("*.dcm")))
            if dcm_count > 0:
                seq_dirs.append((item, dcm_count))
    
    # 按文件名排序
    seq_dirs.sort(key=lambda x: x[0].name)
    total = len(seq_dirs)
    logger.info(f"找到 {total} 个DICOM序列")
    
    count = 0
    skipped = 0
    for idx, (seq_dir, dcm_count) in enumerate(seq_dirs, 1):
        seq_name = f"seq_{idx:02d}"
        dest_seq_dir = target_dir / seq_name
        
        # 显示进度条
        print_progress(idx, total, prefix="处理序列:", suffix=f"{seq_dir.name} ({dcm_count} frames)")
        
        if dest_seq_dir.exists():
            logger.debug(f"跳过已存在的序列: {seq_name}")
            skipped += 1
            continue
        
        try:
            shutil.copytree(seq_dir, dest_seq_dir)
            logger.debug(f"成功复制: {seq_dir.name} -> {seq_name} ({dcm_count} frames)")
            count += 1
        except Exception as e:
            logger.error(f"复制失败 {seq_dir.name}: {e}")
            print(f"\n[ERROR] 复制失败: {seq_dir.name} - {e}")
    
    logger.info(f"DICOM序列处理完成: 成功 {count} 个, 跳过 {skipped} 个")
    return count


def ingest_mri_dicom(zip_path: Path = None, dicom_dir: Path = None,
                     patient_id: str = None, report_date: str = None) -> dict:
    """摄入MRI DICOM数据"""
    patient_id_obf = encode(patient_id)
    imaging_dir = WIKI_ROOT / "raw" / f"patient_{patient_id_obf}" / "imaging"
    imaging_dir.mkdir(parents=True, exist_ok=True)
    
    # 确定DICOM源目录
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
        "saved_dir": str(imaging_dir.relative_to(WIKI_ROOT)),
        "patient_id_raw": patient_id,
        "patient_id_obf": patient_id_obf,
        "report_date": report_date,
        "sequence_count": seq_count,
    }
    return record


def ingest_mri_report(report_path: Path, patient_id: str, report_date: str) -> dict:
    """摄入MRI文字报告"""
    patient_id_obf = encode(patient_id)
    saved_path = save_image(report_path, patient_id_obf, report_date, "report", "papers")
    
    record = {
        "timestamp": datetime.now().isoformat(),
        "type": "mri_report",
        "source_path": str(report_path),
        "saved_path": saved_path,
        "patient_id_raw": patient_id,
        "patient_id_obf": patient_id_obf,
        "report_date": report_date,
    }
    return record


def append_log(record: dict):
    """追加摄入记录到日志"""
    if INGEST_LOG.exists():
        log = json.loads(INGEST_LOG.read_text(encoding="utf-8"))
    else:
        log = {"ingested": []}
    
    log["ingested"].append(record)
    log["last_updated"] = datetime.now().isoformat()
    INGEST_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def print_batch_summary(success_count: int, fail_count: int, extra_info: str = ""):
    """打印批量处理汇总信息"""
    print(f"\n{'='*60}")
    print(f"批量处理完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    if extra_info:
        print(extra_info)
    print(f"{'='*60}")
    log = json.loads(INGEST_LOG.read_text(encoding="utf-8"))
    print(f"总记录数: {len(log['ingested'])} 条")


def main():
    parser = argparse.ArgumentParser(description="统一数据摄入脚本")
    parser.add_argument("--type", "-t", required=True, 
                       choices=["lab_image", "mri_dicom", "mri_report"],
                       help="数据类型")
    parser.add_argument("--path", "-p", type=Path, nargs="*", help="文件路径列表（lab_image/mri_report，支持多个）")
    parser.add_argument("--zip-path", type=Path, nargs="*", help="DICOM ZIP文件路径列表（mri_dicom，支持多个）")
    parser.add_argument("--dicom-dir", type=Path, nargs="*", help="DICOM已解压目录路径列表（mri_dicom，支持多个）")
    parser.add_argument("--patient-id", type=str, default=None, help="患者身份证号")
    parser.add_argument("--report-date", type=str, help="报告日期 YYYY-MM-DD")
    parser.add_argument("--report-type", type=str, choices=["outpatient", "inpatient"],
                       help="报告类型（仅lab_image需要）")
    parser.add_argument("--batch", action="store_true", help="批量处理模式（自动跳过失败项）")
    args = parser.parse_args()
    
    # 验证患者ID
    patient_id = validate_patient_id(args.patient_id, interactive=True)
    if patient_id is None:
        return 1
    
    logger.info(f"开始数据摄入: type={args.type}, patient_id={patient_id}")
    
    print(f"\n[Ingest] 数据类型: {args.type}")
    print(f"[Ingest] 患者ID: {patient_id} -> {encode(patient_id)}")
    if args.report_date:
        print(f"[Ingest] 报告日期: {args.report_date}")
    print(f"[Ingest] 日志文件: {LOG_FILE}")
    
    # 批量处理模式
    batch_mode = args.batch
    
    try:
        if args.type == "lab_image":
            if not args.path or not args.report_type:
                print("\n[ERROR] 参数缺失")
                print("  lab_image 类型需要以下参数:")
                print("    --path <图片路径列表>")
                print("    --report-type <outpatient|inpatient>")
                print("\n示例:")
                print('  # 单个文件')
                print('  python -m lab_analysis.ingest_data --type lab_image \\')
                print('      --path "lab_2026-03-24.jpg" \\')
                print('      --patient-id "513229198801040014" \\')
                print('      --report-date "2026-03-24" \\')
                print('      --report-type "outpatient"')
                print()
                print('  # 批量处理多个文件')
                print('  python -m lab_analysis.ingest_data --type lab_image \\')
                print('      --path "lab1.jpg" "lab2.jpg" "lab3.jpg" \\')
                print('      --patient-id "513229198801040014" \\')
                print('      --report-date "2026-03-24" \\')
                print('      --report-type "outpatient" \\')
                print('      --batch')
                return 1
            
            # 批量处理检验报告
            paths = args.path if isinstance(args.path, list) else [args.path]
            
            def process_lab_image(image_path):
                if not image_path.exists():
                    print(f"\n[ERROR] 文件不存在: {image_path}")
                    return None
                record = ingest_lab_image(image_path, patient_id, args.report_date, args.report_type)
                print(f"[OK] 检验报告摄入成功: {record['saved_path']}")
                return record
            
            success_count, fail_count = process_batch(paths, process_lab_image, batch_mode, "检验报告")
            
            if batch_mode:
                print_batch_summary(success_count, fail_count)
                return 0 if fail_count == 0 else 1
            else:
                # 非批量模式，显示最终统计
                logger.info(f"摄入成功: lab_image, patient_id={patient_id}")
                print(f"\n[OK] 摄入记录已保存")
                log = json.loads(INGEST_LOG.read_text(encoding="utf-8"))
                print(f"  总记录数: {len(log['ingested'])} 条")
                print(f"  详细日志: {LOG_FILE}")
                return 0
        
        elif args.type == "mri_dicom":
            if not args.zip_path and not args.dicom_dir:
                print("\n[ERROR] 参数缺失")
                print("  mri_dicom 类型需要以下参数之一:")
                print("    --zip-path <ZIP文件路径列表>  （推荐，自动解压）")
                print("    --dicom-dir <已解压目录列表>  （如果已手动解压）")
                print("\n示例:")
                print('  # 方式1: 单个ZIP文件')
                print('  python -m lab_analysis.ingest_data --type mri_dicom \\')
                print('      --zip-path "export_part1.zip" \\')
                print('      --patient-id "513229198801040014" \\')
                print('      --report-date "2026-04-11"')
                print()
                print('  # 方式2: 批量处理多个ZIP文件')
                print('  python -m lab_analysis.ingest_data --type mri_dicom \\')
                print('      --zip-path "export1.zip" "export2.zip" \\')
                print('      --patient-id "513229198801040014" \\')
                print('      --report-date "2026-04-11" \\')
                print('      --batch')
                print()
                print('  # 方式3: 使用已解压目录')
                print('  python -m lab_analysis.ingest_data --type mri_dicom \\')
                print('      --dicom-dir "dicom_temp/" \\')
                print('      --patient-id "513229198801040014" \\')
                print('      --report-date "2026-04-11"')
                return 1
            
            # 批量处理DICOM
            zip_paths = args.zip_path if args.zip_path else []
            dicom_dirs = args.dicom_dir if args.dicom_dir else []
            all_sources = [(p, 'zip') for p in zip_paths] + [(d, 'dir') for d in dicom_dirs]
            total_sequences = 0
            
            def process_dicom_source(source_item):
                nonlocal total_sequences
                source_path, source_type = source_item
                if not source_path.exists():
                    print(f"\n[ERROR] {'ZIP文件' if source_type == 'zip' else 'DICOM目录'}不存在: {source_path}")
                    return None
                
                if source_type == 'zip':
                    record = ingest_mri_dicom(zip_path=source_path, patient_id=patient_id, report_date=args.report_date)
                else:
                    record = ingest_mri_dicom(dicom_dir=source_path, patient_id=patient_id, report_date=args.report_date)
                
                seq_count = record['sequence_count']
                total_sequences += seq_count
                
                if not batch_mode:
                    if seq_count == 0:
                        print(f"\n[WARNING] 没有新序列被摄入")
                        print("  可能原因: 所有序列已存在，或被跳过")
                    else:
                        print(f"\n[OK] DICOM摄入成功")
                        print(f"  序列数量: {seq_count} 个")
                        print(f"  保存位置: {record['saved_dir']}")
                else:
                    print(f"[OK] 摄入成功: {seq_count} 个序列")
                
                return record
            
            success_count, fail_count = process_batch(all_sources, process_dicom_source, batch_mode, "DICOM数据")
            
            if batch_mode:
                print_batch_summary(success_count, fail_count, f"总序列数: {total_sequences} 个")
                return 0 if fail_count == 0 else 1
            else:
                # 非批量模式，显示最终统计
                logger.info(f"摄入成功: mri_dicom, patient_id={patient_id}")
                print(f"\n[OK] 摄入记录已保存")
                log = json.loads(INGEST_LOG.read_text(encoding="utf-8"))
                print(f"  总记录数: {len(log['ingested'])} 条")
                print(f"  详细日志: {LOG_FILE}")
                return 0
        
        elif args.type == "mri_report":
            if not args.path:
                print("\n[ERROR] 参数缺失")
                print("  mri_report 类型需要以下参数:")
                print("    --path <报告文件路径列表>")
                print("\n示例:")
                print('  # 单个文件')
                print('  python -m lab_analysis.ingest_data --type mri_report \\')
                print('      --path "mri_report.pdf" \\')
                print('      --patient-id "513229198801040014" \\')
                print('      --report-date "2026-04-11"')
                print()
                print('  # 批量处理多个文件')
                print('  python -m lab_analysis.ingest_data --type mri_report \\')
                print('      --path "mri1.pdf" "mri2.pdf" \\')
                print('      --patient-id "513229198801040014" \\')
                print('      --report-date "2026-04-11" \\')
                print('      --batch')
                return 1
            
            # 批量处理MRI报告
            paths = args.path if isinstance(args.path, list) else [args.path]
            
            def process_mri_report(report_path):
                if not report_path.exists():
                    print(f"\n[ERROR] 文件不存在: {report_path}")
                    return None
                record = ingest_mri_report(report_path, patient_id, args.report_date)
                print(f"[OK] MRI报告摄入成功: {record['saved_path']}")
                return record
            
            success_count, fail_count = process_batch(paths, process_mri_report, batch_mode, "MRI报告")
            
            if batch_mode:
                print_batch_summary(success_count, fail_count)
                return 0 if fail_count == 0 else 1
            else:
                # 非批量模式，显示最终统计
                logger.info(f"摄入成功: mri_report, patient_id={patient_id}")
                print(f"\n[OK] 摄入记录已保存")
                log = json.loads(INGEST_LOG.read_text(encoding="utf-8"))
                print(f"  总记录数: {len(log['ingested'])} 条")
                print(f"  详细日志: {LOG_FILE}")
                return 0
        
        else:
            print(f"\n[ERROR] 不支持的数据类型: {args.type}")
            print("  支持的类型: lab_image, mri_dicom, mri_report")
            return 1
    
    except PermissionError as e:
        print(f"\n[ERROR] 权限错误: {e}")
        print("\n建议操作:")
        print("  1. 在沙箱外运行此命令（设置 required_permissions='all'）")
        print("  2. 检查目标目录的写入权限")
        print("  3. 对于DICOM ZIP文件，可以先手动解压，然后使用 --dicom-dir 参数")
        return 1
    
    except FileNotFoundError as e:
        print(f"\n[ERROR] 文件未找到: {e}")
        print("\n建议操作:")
        print("  1. 检查文件路径是否正确")
        print("  2. 使用绝对路径而非相对路径")
        print("  3. 确认文件确实存在")
        return 1
    
    except Exception as e:
        print(f"\n[ERROR] 摄入失败: {type(e).__name__}: {e}")
        print("\n详细错误信息:")
        import traceback
        traceback.print_exc()
        print("\n建议操作:")
        print("  1. 检查输入参数是否正确")
        print("  2. 确认文件/目录存在且有读取权限")
        print("  3. 查看上方详细错误信息进行排查")
        return 1


if __name__ == "__main__":
    sys.exit(main())
