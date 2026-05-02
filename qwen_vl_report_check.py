#!/usr/bin/env python3
"""上腹部MRI报告印证分析 - Qwen-VL"""
import base64, json, time, argparse, requests
from pathlib import Path
from datetime import datetime

WIKI = Path.home() / "wiki"

KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not KEY:
    env = WIKI.parent / ".hermes" / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DASHSCOPE_API_KEY="): KEY = line.split("=", 1)[1].strip()
if not KEY: raise RuntimeError("❌ 未设置 DASHSCOPE_API_KEY")

REPORT = """【纸质报告 2026-04-11，检查号Y00002207707】
1. 肝右后叶上段：2.2cm异常信号影，考虑感染性病变，较前明显缩小
2. 胰腺：胰管支架置入后，胰腺萎缩，主胰管扩张（最宽1.0cm），胰头稍大
3. 胆道：肝内胆管扩张，胆囊体积增大
4. 右肾：下份囊肿（1.5cm）"""

SEQS = [
    ("seq_01", "肝胆胰脾T2加权横断面"),
    ("seq_02", "T2/扩散加权DWI"),
    ("seq_06", "动脉期增强扫描"),
    ("seq_09", "门脉期增强扫描"),
    ("seq_12", "胰胆管薄层MRCP"),
    ("seq_18", "延迟期/肾脏层面"),
]

PROMPT = """你是资深放射科医生。分析这张上腹部MRI影像，结合纸质报告进行印证分析。

【纸质报告】
{report}

【影像信息】序列: {seq_name} | 患者: 聂聃，男，38岁 | 检查日期: 2026-04-11

请完成：1.解剖定位 2.影像所见 3.印证评价（一致/不一致/补充） 4.补充发现
中文输出，专业医学语言。"""


def load_dicom(path):
    try:
        import pydicom
        from PIL import Image, io
        dcm = pydicom.dcmread(str(path))
        img = (dcm.pixel_array - dcm.pixel_array.min()) / (dcm.pixel_array.max() or 1) * 255
        buf = io.BytesIO()
        Image.fromarray(img.astype("uint8"), mode="L").save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        raise RuntimeError(f"DICOM读取失败: {e}")


def analyze(b64, seq_name):
    resp = requests.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        json={"model": "qwen-vl-plus",
              "input": {"messages": [{"role": "user", "content": [{"image": f"data:image/jpeg;base64,{b64}"},
                                                                  {"text": PROMPT.format(report=REPORT, seq_name=seq_name)}]}]}},
        timeout=120)
    return resp.json().get("output", {}).get("choices", [{}])[0].get("message", {}).get("content", "")


def main():
    p = argparse.ArgumentParser(); p.add_argument("--patient-id", required=True); args = p.parse_args()
    img_dir = WIKI / "raw" / f"patient_{args.patient_id}" / "imaging"
    out_dir = WIKI / "data" / args.patient_id; out_dir.mkdir(exist_ok=True)

    print(f"[{datetime.now().isoformat()}] MRI分析 | 病人: {args.patient_id} | 共{len(SEQS)}个序列\n")
    results = []
    for seq_dir, seq_desc in SEQS:
        seq_path = img_dir / seq_dir
        if not seq_path.exists(): print(f"⚠️ 跳过: {seq_dir}"); continue
        dcm_files = sorted(seq_path.glob("*.dcm"))
        if not dcm_files: print(f"⚠️ 跳过: {seq_dir} (无DICOM)"); continue
        mid = dcm_files[len(dcm_files)//2]
        print(f"📷 {seq_dir}/{mid.name} ({seq_desc})")
        try:
            b64 = load_dicom(mid)
            content = analyze(b64, f"{seq_dir} — {seq_desc}")
            results.append({"status": "success", "seq": seq_dir, "desc": seq_desc, "content": content})
            print(f"  ✅ 完成")
        except Exception as e:
            results.append({"status": "error", "seq": seq_dir, "error": str(e)})
            print(f"  ❌ {e}")
        time.sleep(1)

    out_path = out_dir / "mri_report_check_results.json"
    json.dump({"date": datetime.now().isoformat(), "model": "qwen-vl-plus", "report": REPORT, "results": results},
              open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n✅ 保存: {out_path}")


if __name__ == "__main__":
    import os
    main()
