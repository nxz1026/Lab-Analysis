#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qwen_vl_report_check.py
上腹部MRI报告印证分析 — 每个部位选1-2张代表性DICOM图
用法: python qwen_vl_report_check.py --patient-id 513229198801040014
"""
import base64, json, os, sys, time
from pathlib import Path

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not DASHSCOPE_API_KEY:
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        for line in open(env_path):
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
# 从19个序列中选出最相关的6个
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
- 患者: 聂聃，男，38岁，检查编号Y00002207707
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
        img = img - img.min()
        if img.max() > 0:
            img = img / img.max()
        img = (img * 255).astype("uint8")
        # 伪彩色（pydicom原始数据可能是单通道）
        if len(img.shape) == 2:
            pil_img = Image.fromarray(img, mode="L")
        else:
            pil_img = Image.fromarray(img)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        raise RuntimeError(f"DICOM读取失败: {e}")


def analyze_single(image_b64: str, seq_name: str, seq_desc: str, finding: str) -> dict:
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
    return {"status": "success", "seq_name": seq_name, "seq_desc": seq_desc, "analysis": content}


def main():
    import argparse, requests
    parser = argparse.ArgumentParser(description="上腹部MRI报告印证分析")
    parser.add_argument("--patient-id", required=True)
    args = parser.parse_args()

    wiki_root = Path.home() / "wiki"
    imaging_base = wiki_root / "raw" / f"patient_{args.patient_id}" / "imaging"
    import os
    ts = os.environ.get("ANALYSIS_TS", args.patient_id)
    data_dir = wiki_root / "data" / ts
    data_dir.mkdir(exist_ok=True)

    # 前置检查：影像目录存在
    if not imaging_base.exists():
        print(f"❌ 影像目录不存在: {imaging_base}")
        print(f"   预期路径: raw/patient_{{patient_id}}/imaging/seq_01~19/*.dcm")
        sys.exit(1)

    print(f"\n[{datetime.now().isoformat()}] 上腹部MRI报告印证分析")
    print(f"  病人: {args.patient_id}")
    print(f"  影像目录: {imaging_base}")
    print(f"  共分析 {len(SEQ_SELECTIONS)} 个序列\n")

    results = []

    for seq_dir_name, seq_desc, analysis_focus in SEQ_SELECTIONS:
        seq_path = imaging_base / seq_dir_name
        if not seq_path.exists():
            print(f"⚠️  目录不存在: {seq_dir_name}，跳过")
            continue

        # 选中间帧
        dcm_files = sorted(seq_path.glob("*.dcm"))
        if not dcm_files:
            print(f"⚠️  {seq_dir_name} 无DICOM文件，跳过")
            continue

        mid = len(dcm_files) // 2
        img_path = dcm_files[mid]
        print(f"📷 选取: {seq_dir_name}/{img_path.name} ({seq_desc}) 第{mid+1}/{len(dcm_files)}帧")

        try:
            b64 = load_dicom_image(img_path)
        except Exception as e:
            print(f"  ❌ DICOM读取失败: {e}")
            continue

        finding_text = f"【分析重点】{analysis_focus}。{REPORT_FINDINGS}"

        try:
            r = analyze_single(b64, seq_dir_name, seq_desc, finding_text)
            results.append(r)
            print(f"  ✅ 完成")
        except Exception as e:
            results.append({"status": "error", "seq_name": seq_dir_name, "seq_desc": seq_desc, "error": str(e)})
            print(f"  ❌ 失败: {e}")

        time.sleep(1)

    # 保存
    output_path = data_dir / "mri_report_check_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_date": datetime.now().isoformat(),
            "model": "qwen-vl-plus",
            "report_findings": REPORT_FINDINGS,
            "results": results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n💾 结果已保存: {output_path}")
    print("\n" + "="*60)
    print("📊 分析摘要")
    print("="*60)
    for r in results:
        if r["status"] == "success":
            print(f"\n✅ {r['seq_name']} ({r['seq_desc']})")
            print(f"   {r['analysis'][:300]}...")
        else:
            print(f"\n❌ {r['seq_name']}: {r.get('error', '')}")


if __name__ == "__main__":
    import requests
    from datetime import datetime
    main()
