#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上腹部MRI报告印证分析 - DSPy 增强版

支持传统 API 调用和 DSPy 优化两种模式
用法: python qwen_vl_report_check_dspy.py --patient-id <ID> [--use-dspy]
"""

import base64
import json
import os
import requests
import sys
import time
from datetime import datetime
from pathlib import Path

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not DASHSCOPE_API_KEY:
    # 从项目根目录的 .env 文件加载
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in open(env_path, encoding='utf-8'):
            if line.startswith("DASHSCOPE_API_KEY=") and not line.startswith("#"):
                DASHSCOPE_API_KEY = line.strip().split("=", 1)[1].strip().strip("'\"")

if not DASHSCOPE_API_KEY:
    raise RuntimeError("DASHSCOPE_API_KEY 未设置")

API_BASE = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

REPORT_FINDINGS = """【纸质报告关键发现 - 2026-04-11，检查号Y00002207707】
1. 肝右后叶上段：长径约2.2cm异常信号影，T1稍低、T2及STIR稍高，增强少许点片状弱强化，考虑感染性病变，较前明显缩小
2. 胰腺：「胰管支架置入后」，胰腺实质萎缩，主胰管扩张程度较前明显，最宽约1.0cm，胰头稍大
3. 胆道：肝内胆管扩张，胆囊体积增大
4. 右肾：下份囊肿，长径约1.5cm
"""

# 6个代表性序列：seq_XX → (解剖部位描述, 选取逻辑, DICOM文件后缀关键词)
SEQ_SELECTIONS = [
    ("seq_01", "肝胆胰脾T2加权横断面",     "T2WI横断面，代表层面"),
    ("seq_02", "T2/扩散加权（DWI）",         "DWI序列，肝右后叶区域"),
    ("seq_06", "动脉期增强扫描",             "动脉期，胰头区域"),
    ("seq_09", "门脉期增强扫描",             "门脉期，肝内胆管/胆囊"),
    ("seq_12", "胰胆管薄层MRCP",            "MRCP，胰管+胆管"),
    ("seq_18", "延迟期/肾脏层面",            "延迟期，右肾区域"),
]

PROMPT_TEMPLATE = """你是一位资深放射科医生。请仔细分析这张上腹部MRI影像，并结合以下【纸质报告描述】进行印证分析。

【纸质报告描述】
{report_finding}

【本张影像信息】
- 序列: {seq_name}
- 扫描部位: 上腹部（肝胆胰脾）+ 胰胆管薄层
- 检查日期: 2026-04-11
- 患者: [脱敏]，男，38岁，检查编号Y00002207707
- 临床指征: 胰管支架置入后复查，腹痛待查

请完成以下分析：
1. 【解剖定位】这张图片大约在哪个层面（肝脏？胰腺？肾脏？其他？）
2. 【影像所见】详细描述可见的结构和信号特征
3. 【印证评价】对照纸质报告描述，判断该影像表现是否与报告一致？一致/不一致/补充
4. 【补充发现】纸质报告未提及但影像可见的异常

请用专业医学影像语言描述，结论明确。中文输出。"""


def load_dicom_image(path: Path) -> str:
    """将DICOM转换为JPEG并返回base64字符串。"""
    try:
        import pydicom
        from PIL import Image
        import io
        dcm = pydicom.dcmread(str(path))
        img = dcm.pixel_array
        # 归一化到0-255
        img = ((img - img.min()) / (img.max() - img.min()) * 255).astype('uint8')
        pil_img = Image.fromarray(img)
        buffer = io.BytesIO()
        pil_img.save(buffer, format="JPEG")
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"  [失败] DICOM读取失败: {e}")
        return None


def analyze_single_standard(image_b64: str, seq_name: str, seq_desc: str, finding: str) -> dict:
    """标准模式: 直接调用 Qwen-VL API"""
    payload = {
        "model": "qwen-vl-plus",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:image/jpeg;base64,{image_b64}"},
                        {"text": PROMPT_TEMPLATE.format(
                            report_finding=finding,
                            seq_name=f"{seq_name} — {seq_desc}",
                        )}
                    ]
                }
            ]
        }
    }
    resp = requests.post(API_BASE, headers={
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    content = data.get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", "")
    return {
        "status": "success", 
        "seq_name": seq_name, 
        "seq_desc": seq_desc, 
        "analysis": content,
        "mode": "standard"
    }


def analyze_single_dspy(image_b64: str, seq_name: str, seq_desc: str, finding: str) -> dict:
    """DSPy 模式: 使用优化的 MRI 分析模块"""
    try:
        from lab_analysis.dspy_modules import run_dspy_mri_analysis
        
        # 构建临床背景
        clinical_context = "男，38岁，胰管支架置入后复查，腹痛待查，检查编号Y00002207707"
        
        # 运行 DSPy 分析
        result = run_dspy_mri_analysis(
            image_desc=f"{seq_name} — {seq_desc}",
            report_findings=finding,
            clinical_context=clinical_context
        )
        
        # 格式化输出
        formatted_analysis = f"""【解剖定位】
{result['anatomical_localization']}

【影像所见】
{result['imaging_findings']}

【印证评价】
{result['consistency_evaluation']}

【补充发现】
{result['additional_findings']}

【置信度】{result['confidence_score']:.2f}"""
        
        return {
            "status": "success",
            "seq_name": seq_name,
            "seq_desc": seq_desc,
            "analysis": formatted_analysis,
            "mode": "dspy_optimized",
            "confidence": result['confidence_score']
        }
        
    except Exception as e:
        print(f"  [警告] DSPy 分析失败，回退到标准模式: {e}")
        # 回退到标准模式
        return analyze_single_standard(image_b64, seq_name, seq_desc, finding)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="上腹部MRI报告印证分析 - DSPy 增强版")
    parser.add_argument("--patient-id", required=True)
    parser.add_argument("--use-dspy", action="store_true", help="使用 DSPy 优化版本")
    args = parser.parse_args()

    # 使用 WORK_ROOT 而不是硬编码路径
    imaging_base = WORK_ROOT / "raw" / f"patient_{args.patient_id}" / "imaging"
    raw_ts = os.environ.get("ANALYSIS_TS", "")
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or args.patient_id)
    lit_dir = WORK_ROOT / "data" / args.patient_id / ts / "03_literature"
    lit_dir.mkdir(parents=True, exist_ok=True)

    # 前置检查：影像目录存在
    if not imaging_base.exists():
        print(f"[错误] 影像目录不存在: {imaging_base}")
        print(f"   预期路径: raw/patient_{{patient_id}}/imaging/seq_01~19/*.dcm")
        sys.exit(1)

    mode_label = "[DSPy]" if args.use_dspy else "[标准]"
    print(f"\n[{datetime.now().isoformat()}] {mode_label} 上腹部MRI报告印证分析")
    print(f"  病人: {args.patient_id}")
    print(f"  影像目录: {imaging_base}")
    print(f"  共分析 {len(SEQ_SELECTIONS)} 个序列\n")

    results = []

    for seq_id, seq_name, seq_desc in SEQ_SELECTIONS:
        seq_dir = imaging_base / seq_id
        if not seq_dir.exists():
            print(f"[警告] 目录不存在: {seq_id}，跳过")
            continue

        # 查找 DICOM 文件
        dcm_files = list(seq_dir.glob("*.dcm")) + list(seq_dir.glob("*.DCM"))
        if not dcm_files:
            print(f"[警告] 无 DICOM 文件: {seq_id}，跳过")
            continue

        # 选取中间帧作为代表
        mid_idx = len(dcm_files) // 2
        selected_file = sorted(dcm_files)[mid_idx]
        
        print(f"[图片] 选取: {seq_id}/{selected_file.name} ({seq_desc}) 第{mid_idx+1}/{len(dcm_files)}帧")

        # 加载图像
        image_b64 = load_dicom_image(selected_file)
        if not image_b64:
            continue

        # 执行分析
        start_time = time.time()
        try:
            if args.use_dspy:
                result = analyze_single_dspy(image_b64, seq_name, seq_desc, REPORT_FINDINGS)
            else:
                result = analyze_single_standard(image_b64, seq_name, seq_desc, REPORT_FINDINGS)
            
            elapsed = time.time() - start_time
            print(f"  [成功] 完成 (耗时: {elapsed:.1f}s)")
            results.append(result)
            
        except Exception as e:
            print(f"  [失败] 分析失败: {e}")
            results.append({
                "status": "error",
                "seq_name": seq_name,
                "seq_desc": seq_desc,
                "error": str(e)
            })

    # 保存结果
    output_path = lit_dir / "mri_analysis_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "patient_id": args.patient_id,
            "mode": "dspy_optimized" if args.use_dspy else "standard",
            "total_sequences": len(SEQ_SELECTIONS),
            "analyzed_count": len([r for r in results if r["status"] == "success"]),
            "results": results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[摘要] 分析摘要")
    print(f"  总序列数: {len(SEQ_SELECTIONS)}")
    print(f"  成功分析: {len([r for r in results if r['status'] == 'success'])}")
    print(f"  失败: {len([r for r in results if r['status'] == 'error'])}")
    
    if args.use_dspy:
        avg_confidence = sum(r.get('confidence', 0) for r in results if r['status'] == 'success') / max(len([r for r in results if r['status'] == 'success']), 1)
        print(f"  平均置信度: {avg_confidence:.2f}")

    print(f"\n[保存] 结果已保存: {output_path}")


if __name__ == "__main__":
    main()
