#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_vision_extract.py — 批量识别检验报告图片

用法：
  python -m lab_analysis.batch_vision_extract [--interactive]

流程：
  1. 扫描 Origin_data 目录下的所有 lab_*.jpg 文件
  2. 调用 vision_extractor 识别每张图
  3. 验证患者ID是否为有效身份证号
  4. 如果无效，提示用户手动输入或放弃（交互模式）
  5. 调用 ingest_data 存入正确的目录
  6. 生成汇总报告

环境变量：
  ORIGIN_DATA_DIR: 原始数据目录（默认: ~/wiki/raw/Origin_data）
  PROJECT_ROOT: 项目根目录（自动检测）
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from lab_analysis.utils import WORK_ROOT, validate_chinese_id


def get_origin_data_dir() -> Path:
    """获取原始数据目录"""
    return Path(os.environ.get("ORIGIN_DATA_DIR", WORK_ROOT / "raw" / "Origin_data"))


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).resolve().parent.parent


def get_venv_python() -> Path:
    """获取虚拟环境Python路径"""
    project_root = get_project_root()
    # 优先查找项目内的虚拟环境
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return venv_python
    venv_python = project_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    # 返回当前解释器
    return Path(sys.executable)


def run_vision_extractor(image_path: Path, interactive: bool = False) -> dict:
    """调用 vision_extractor 识别单张图片"""
    output_json = image_path.with_suffix(".extracted.json")
    project_root = get_project_root()
    venv_python = get_venv_python()
    
    cmd = [
        str(venv_python), "-m", "lab_analysis.vision_extractor",
        "--image", str(image_path),
        "--output", str(output_json)
    ]
    
    if interactive:
        cmd.append("--interactive")
    
    print(f"\n{'='*60}")
    print(f"🔍 正在识别: {image_path.name}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True)
    
    # 打印输出（包括交互式提示）
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    if result.returncode != 0:
        print(f"❌ 识别失败")
        return None
    
    # 读取输出JSON
    if output_json.exists():
        return json.loads(output_json.read_text(encoding="utf-8"))
    return None


def run_ingest_data(image_path: Path, patient_id: str, report_date: str, report_type: str):
    """调用 ingest_data 存入图片"""
    project_root = get_project_root()
    venv_python = get_venv_python()
    
    cmd = [
        str(venv_python), "-m", "lab_analysis.ingest_data",
        "--type", "lab_image",
        "--path", str(image_path),
        "--patient-id", patient_id,
        "--report-date", report_date,
        "--report-type", report_type
    ]
    
    print(f"\n💾 正在存入: {image_path.name}")
    print(f"   患者ID: {patient_id}")
    print(f"   日期: {report_date}")
    print(f"   类型: {report_type}")
    
    result = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ 存入成功")
        if result.stdout:
            print(result.stdout)
    else:
        print(f"❌ 存入失败")
        if result.stderr:
            print(result.stderr)


def main():
    parser = argparse.ArgumentParser(description="批量 Vision 识别 + 数据摄入")
    parser.add_argument("--interactive", action="store_true", help="交互式确认模式（当ID无效时提示用户输入）")
    args = parser.parse_args()
    
    origin_data_dir = get_origin_data_dir()
    
    print("=" * 60)
    print("🚀 批量 Vision 识别 + 数据摄入")
    print(f"📂 数据源: {origin_data_dir}")
    if args.interactive:
        print("📝 模式: 交互式（无效ID时将提示手动输入）")
    else:
        print("📝 模式: 自动（无效ID将自动跳过）")
    print("=" * 60)
    
    # 查找所有 lab_*.jpg 文件
    image_files = sorted(origin_data_dir.glob("lab_*.jpg"))
    
    if not image_files:
        print(f"\n⚠️  未找到 lab_*.jpg 文件")
        print(f"   请将检验报告图片放入: {origin_data_dir}")
        return 0
    
    print(f"\n📷 找到 {len(image_files)} 张检验报告图片")
    
    success_count = 0
    fail_count = 0
    skipped_count = 0
    results = []
    
    for idx, image_path in enumerate(image_files, 1):
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(image_files)}] 处理: {image_path.name}")
        print(f"{'='*60}")
        
        # 步骤1: 识别图片
        result = run_vision_extractor(image_path, args.interactive)
        if not result:
            print(f"❌ 识别失败，跳过")
            fail_count += 1
            results.append({"file": image_path.name, "status": "识别失败", "patient_id": None})
            continue
        
        patient_id = result.get("patient_id")
        report_date = result.get("report_date")
        report_type = result.get("report_type", "outpatient")
        
        # 步骤2: 验证患者ID
        if not patient_id or not validate_chinese_id(patient_id):
            if args.interactive:
                print(f"\n⚠️  识别的患者ID无效或为空")
                print(f"   识别结果: patient_id={patient_id}, report_date={report_date}")
                print("\n请选择:")
                print("  1. 手动输入正确的身份证号")
                print("  2. 跳过此图片")
                
                try:
                    choice = input("请输入选择 (1/2): ").strip()
                    if choice == "1":
                        patient_id = input("请输入患者身份证号: ").strip()
                        if not validate_chinese_id(patient_id):
                            print(f"❌ 输入的ID仍然无效，跳过")
                            skipped_count += 1
                            results.append({"file": image_path.name, "status": "ID无效，用户放弃", "patient_id": None})
                            continue
                    elif choice == "2":
                        print("⏭️  用户选择跳过")
                        skipped_count += 1
                        results.append({"file": image_path.name, "status": "用户跳过", "patient_id": None})
                        continue
                    else:
                        print("❌ 无效选择，跳过")
                        skipped_count += 1
                        results.append({"file": image_path.name, "status": "无效选择", "patient_id": None})
                        continue
                except (EOFError, KeyboardInterrupt):
                    print("\n⏭️  用户中断，跳过")
                    skipped_count += 1
                    results.append({"file": image_path.name, "status": "用户中断", "patient_id": None})
                    continue
            else:
                print(f"⏭️  ID无效，自动跳过")
                skipped_count += 1
                results.append({"file": image_path.name, "status": "ID无效，自动跳过", "patient_id": None})
                continue
        
        # 步骤3: 存入数据
        run_ingest_data(image_path, patient_id, report_date, report_type)
        success_count += 1
        results.append({"file": image_path.name, "status": "成功", "patient_id": patient_id, 
                       "report_date": report_date, "report_type": report_type})
    
    # 生成汇总报告
    print(f"\n{'='*60}")
    print("📊 批量处理完成")
    print(f"{'='*60}")
    print(f"✅ 成功: {success_count}")
    print(f"❌ 失败: {fail_count}")
    print(f"⏭️  跳过: {skipped_count}")
    
    # 保存汇总报告
    summary_file = origin_data_dir / "batch_extraction_summary.json"
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(image_files),
        "success": success_count,
        "fail": fail_count,
        "skipped": skipped_count,
        "results": results
    }
    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📝 汇总报告已保存: {summary_file}")
    
    return 0


if __name__ == "__main__":
    import os
    from datetime import datetime
    sys.exit(main())