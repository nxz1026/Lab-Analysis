#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_vision_extract.py — 批量识别 Origin_data 目录下的所有检验报告图片

用法：
  python batch_vision_extract.py [--interactive]

流程：
  1. 扫描 C:\\Users\\ND\\wiki\\raw\\Origin_data\\ 下的所有 lab_*.jpg 文件
  2. 调用 vision_extractor 识别每张图
  3. 验证患者ID是否为有效身份证号
  4. 如果无效，提示用户手动输入或放弃
  5. 调用 ingest_image.py 存入正确的目录
  6. 生成汇总报告
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


ORIGIN_DATA_DIR = Path(r"C:/Users/ND/wiki/raw/Origin_data")
VENV_PYTHON = Path(r"e:/2026Workplace/Code/nxz1026/Lab-Analysis/.venv/Scripts/python.exe")
PROJECT_ROOT = Path(r"e:/2026Workplace/Code/nxz1026/Lab-Analysis")


def run_vision_extractor(image_path: Path, interactive: bool = False) -> dict:
    """调用 vision_extractor 识别单张图片"""
    output_json = image_path.with_suffix(".extracted.json")
    
    cmd = [
        str(VENV_PYTHON), "-m", "lab_analysis.vision_extractor",
        "--image", str(image_path),
        "--output", str(output_json)
    ]
    
    if interactive:
        cmd.append("--interactive")
    
    print(f"\n{'='*60}")
    print(f"🔍 正在识别: {image_path.name}")
    print(f"{'='*60}")
    
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    
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


def run_ingest_image(image_path: Path, patient_id: str, report_date: str, report_type: str):
    """调用 ingest_image.py 存入图片"""
    cmd = [
        str(VENV_PYTHON), "-m", "lab_analysis.ingest_image",
        "--path", str(image_path),
        "--patient-id", patient_id,
        "--report-date", report_date,
        "--report-type", report_type
    ]
    
    print(f"\n💾 正在存入: {image_path.name}")
    print(f"   患者ID: {patient_id}")
    print(f"   日期: {report_date}")
    print(f"   类型: {report_type}")
    
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f"✅ 存入成功")
        print(result.stdout)
    else:
        print(f"❌ 存入失败: {result.stderr}")


def main():
    parser = argparse.ArgumentParser(description="批量 Vision 识别 + 数据摄入")
    parser.add_argument("--interactive", action="store_true", help="交互式确认模式（当ID无效时提示用户输入）")
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 批量 Vision 识别 + 数据摄入")
    if args.interactive:
        print("📝 模式: 交互式（无效ID时将提示手动输入）")
    else:
        print("📝 模式: 自动（无效ID将自动跳过）")
    print("=" * 60)
    
    if not ORIGIN_DATA_DIR.exists():
        print(f"❌ 目录不存在: {ORIGIN_DATA_DIR}")
        return 1
    
    # 查找所有检验报告图片
    lab_images = sorted(ORIGIN_DATA_DIR.glob("lab_*.jpg"))
    
    if not lab_images:
        print("⚠️  未找到任何检验报告图片 (lab_*.jpg)")
        return 1
    
    print(f"\n📊 找到 {len(lab_images)} 张检验报告图片:")
    for img in lab_images:
        print(f"   - {img.name}")
    
    results = []
    
    # 逐个处理
    for image_path in lab_images:
        # Step 1: Vision 识别（带交互式验证）
        info = run_vision_extractor(image_path, interactive=args.interactive)
        
        if not info or not info.get("patient_id"):
            error_msg = info.get('error', '未知错误') if info else '识别失败'
            print(f"\n⚠️  跳过 {image_path.name}（原因: {error_msg}）")
            continue
        
        results.append({
            "image": image_path.name,
            "info": info
        })
        
        # Step 2: 存入数据
        # 如果 report_type 为 None，默认为 outpatient
        report_type = info.get("report_type") or "outpatient"
        
        run_ingest_image(
            image_path,
            info["patient_id"],
            info["report_date"],
            report_type
        )
    
    # 生成汇总报告
    summary_file = ORIGIN_DATA_DIR / "batch_extraction_summary.json"
    summary_file.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    
    print("\n" + "=" * 60)
    print("📋 批量处理完成！")
    print("=" * 60)
    print(f"✅ 成功处理: {len(results)} 张图片")
    print(f"📄 汇总报告: {summary_file}")
    
    # 显示所有患者ID
    patient_ids = set(r["info"]["patient_id"] for r in results)
    print(f"\n👤 识别到的患者ID:")
    for pid in sorted(patient_ids):
        count = sum(1 for r in results if r["info"]["patient_id"] == pid)
        print(f"   - {pid} ({count} 份报告)")
    
    print("\n💡 下一步:")
    print(f"   运行完整 Pipeline:")
    print(f"   cd {PROJECT_ROOT}")
    print(f"   .\\.venv\\Scripts\\python.exe -m lab_analysis.pipeline --patient-id <患者ID>")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
