#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整运行Pipeline - 处理所有原始数据（检验报告 + MRI影像）
"""
from pathlib import Path
import subprocess
import sys

WIKI_ROOT = Path.home() / "wiki"
ORIGIN_DATA = WIKI_ROOT / "raw" / "Origin_data"
PATIENT_ID = "513229198801040014"
DEID_ID = "846552421134373347"

def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"[执行] {description}")
    print(f"命令: {' '.join(cmd)}")
    print('='*60)
    
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"[警告] 命令返回码: {result.returncode}")
    return result.returncode == 0

def main():
    print("="*60)
    print("完整Pipeline执行流程")
    print("="*60)
    
    # 步骤1：创建结构化检验报告数据
    print("\n[步骤1] 创建结构化检验报告数据...")
    papers_dir = WIKI_ROOT / "raw" / f"patient_{DEID_ID}" / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    
    reports_data = [
        {
            "dir": "lab_report_20260324_outpatient",
            "date": "2026-03-24",
            "type": "outpatient",
            "department": "消化内科",
            "physician": "李薇",
            "diagnosis": "慢性胰腺炎",
            "metrics": {
                "WBC": 6.7, "RBC": 4.52, "HGB": 142, "HCT": 43, "PLT": 238,
                "PCT": 0.24, "MCV": 95.1, "MCH": 31.4, "MCHC": 330,
                "NEUT%": 59.5, "LYMPH%": 32.1, "MONO%": 6.9, "EO%": 1.2, "BASO%": 0.3,
                "NEUT#": 3.99, "LYMPH#": 2.15, "MONO#": 0.46, "EO#": 0.08, "BASO#": 0.02,
                "RDW-SD": 48.2, "RDW-CV": 13.8, "MPV": 10.1, "PDW": 10.9, "P-LCR": 25.3,
                "CRP": 10, "hs-CRP": 2.78
            }
        },
        {
            "dir": "lab_report_20260330_outpatient",
            "date": "2026-03-30",
            "type": "outpatient",
            "department": "消化内科",
            "physician": "李薇",
            "diagnosis": "慢性胰腺炎",
            "metrics": {
                "WBC": 5.66, "RBC": 4.59, "HGB": 141, "HCT": 43.1, "PLT": 154,
                "PCT": 0.16, "MCV": 93.9, "MCH": 30.7, "MCHC": 327,
                "NEUT%": 61.5, "LYMPH%": 30.2, "MONO%": 6.7, "EO%": 1.3, "BASO%": 0.3,
                "NEUT#": 3.49, "LYMPH#": 1.71, "MONO#": 0.38, "EO#": 0.07, "BASO#": 0.02,
                "RDW-SD": 46.9, "RDW-CV": 13.7, "MPV": 10.4, "PDW": 12.2, "P-LCR": 27.8,
                "CRP": 10, "hs-CRP": 1.41
            }
        },
        {
            "dir": "lab_report_20260408_inpatient",
            "date": "2026-04-08",
            "type": "inpatient",
            "department": "消化内科",
            "physician": "段靖方",
            "diagnosis": "发热待诊",
            "metrics": {
                "WBC": 3.04, "RBC": 4.31, "HGB": 131, "HCT": 40, "PLT": 153,
                "PCT": 0.17, "MCV": 92.8, "MCH": 30.4, "MCHC": 328,
                "NEUT%": 50.0, "LYMPH%": 31.6, "MONO%": 17.8, "EO%": 0.4, "BASO%": 0.2,
                "NEUT#": 1.52, "LYMPH#": 0.96, "MONO#": 0.54, "EO#": 0.01, "BASO#": 0.01,
                "RDW-SD": 50.6, "RDW-CV": 14.6, "MPV": 10.0, "PDW": 10.0, "P-LCR": 24.5,
                "CRP": 17.44, "hs-CRP": 10.0
            }
        },
        {
            "dir": "lab_report_20260414_inpatient",
            "date": "2026-04-14",
            "type": "inpatient",
            "department": "消化内科(住院)",
            "physician": "段婉方",
            "diagnosis": "发热待诊",
            "metrics": {
                "WBC": 6.26, "RBC": 4.78, "HGB": 144, "HCT": 45.3, "PLT": 336,
                "PCT": 0.33, "MCV": 94.8, "MCH": 30.1, "MCHC": 318,
                "NEUT%": 61.3, "LYMPH%": 29.1, "MONO%": 6.7, "EO%": 2.6, "BASO%": 0.3,
                "NEUT#": 3.84, "LYMPH#": 1.82, "MONO#": 0.42, "EO#": 0.16, "BASO#": 0.02,
                "RDW-SD": 52.5, "RDW-CV": 15.1, "MPV": 10.0, "PDW": 10.0, "P-LCR": 26.2,
                "CRP": 10, "hs-CRP": 1.82
            }
        }
    ]
    
    for report in reports_data:
        report_dir = papers_dir / report['dir']
        report_dir.mkdir(exist_ok=True)
        
        # 生成metadata.md
        metadata_content = f"""| 字段 | 值 |
|------|-----|
| 患者ID | {PATIENT_ID} |
| 报告日期 | {report['date']} |
| 报告类型 | {report['type']} |
| 科室 | {report['department']} |
| 医生 | {report['physician']} |
| 诊断 | {report['diagnosis']} |
"""
        (report_dir / "metadata.md").write_text(metadata_content, encoding='utf-8')
        
        # 生成metrics.md
        metrics_lines = [f"{k}: {v}" for k, v in sorted(report['metrics'].items())]
        (report_dir / "metrics.md").write_text("\n".join(metrics_lines) + "\n", encoding='utf-8')
        
        print(f"  ✓ {report['dir']}")
    
    print(f"\n✅ 已创建 {len(reports_data)} 份结构化检验报告")
    
    # 步骤2：准备MRI影像数据
    print("\n[步骤2] 准备MRI影像数据...")
    imaging_dir = WIKI_ROOT / "raw" / f"patient_{DEID_ID}" / "imaging" / "seq_01"
    
    # 检查是否已有DICOM数据
    if imaging_dir.exists() and len(list(imaging_dir.glob("*.dcm"))) > 0:
        dcm_count = len(list(imaging_dir.glob("*.dcm")))
        print(f"  ✓ DICOM数据已存在: {dcm_count} 个文件")
    else:
        # 解压DICOM文件
        dicom_zip = ORIGIN_DATA / "export_part1_20260501172611350.zip"
        if dicom_zip.exists():
            print(f"  正在解压DICOM文件: {dicom_zip.name}")
            import zipfile
            import tempfile
            
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                print(f"  解压到临时目录...")
                with zipfile.ZipFile(dicom_zip, 'r') as z:
                    z.extractall(tmpdir_path)
                
                # 找到包含.dcm文件的子目录
                dcm_dirs = list(tmpdir_path.glob("*/*.dcm"))
                if dcm_dirs:
                    source_dir = dcm_dirs[0].parent.parent
                    print(f"  复制DICOM文件到: {imaging_dir}")
                    imaging_dir.mkdir(parents=True, exist_ok=True)
                    
                    import shutil
                    for dcm_file in source_dir.rglob("*.dcm"):
                        shutil.copy2(dcm_file, imaging_dir)
                    
                    dcm_count = len(list(imaging_dir.glob("*.dcm")))
                    print(f"  ✓ 已复制 {dcm_count} 个DICOM文件")
                else:
                    print(f"  ⚠️ 未找到DICOM文件")
        else:
            print(f"  ⚠️ DICOM ZIP文件不存在: {dicom_zip}")
    
    # 步骤3：运行完整Pipeline
    print("\n[步骤3] 运行完整Pipeline（不跳过任何步骤）...")
    print("="*60)
    
    cmd = [
        sys.executable, "-m", "lab_analysis.pipeline",
        "--patient-id", PATIENT_ID
    ]
    
    success = run_command(cmd, "完整Pipeline执行")
    
    if success:
        print("\n" + "="*60)
        print("✅ Pipeline执行完成！")
        print("="*60)
        
        # 显示输出文件
        output_dir = WIKI_ROOT / "data" / DEID_ID
        if output_dir.exists():
            latest_run = max(output_dir.iterdir(), key=lambda x: x.stat().st_mtime)
            print(f"\n输出目录: {latest_run}")
            print("\n生成的文件:")
            for f in sorted(latest_run.iterdir()):
                size_kb = f.stat().st_size / 1024
                print(f"  - {f.name} ({size_kb:.1f} KB)")
    else:
        print("\n❌ Pipeline执行失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
