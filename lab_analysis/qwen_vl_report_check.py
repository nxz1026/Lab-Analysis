"""
qwen_vl_report_check.py
上腹部MRI报告印证分析 — 每个部位选1-2张代表性DICOM图
用法: python qwen_vl_report_check.py --id-card <脱敏ID>
"""

import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path

from lab_analysis.llm_client import call_dashscope_multimodal, load_api_key

from . import _log
from .utils import WORK_ROOT

logger = _log.get_logger(__name__)
load_api_key("DASHSCOPE_API_KEY")
REPORT_FINDINGS = "【纸质报告关键发现 - 2026-04-11，检查号Y00002207707】\n1. 肝右后叶上段：长径约2.2cm异常信号影，T1稍低、T2及STIR稍高，增强少许点片状弱强化，考虑感染性病变，较前明显缩小\n2. 胰腺：「胰管支架置入后」，胰腺实质萎缩，主胰管扩张程度较前明显，最宽约1.0cm，胰头稍大\n3. 胆道：肝内胆管扩张，胆囊体积增大\n4. 右肾：下份囊肿，长径约1.5cm\n"
SEQ_SELECTIONS = [
    ("seq_01", "肝胆胰脾T2加权横断面", "T2WI横断面，代表层面"),
    ("seq_02", "T2/扩散加权（DWI）", "DWI序列，肝右后叶区域"),
    ("seq_06", "动脉期增强扫描", "动脉期，胰头区域"),
    ("seq_09", "门脉期增强扫描", "门脉期，肝内胆管/胆囊"),
    ("seq_12", "胰胆管薄层MRCP", "MRCP，胰管+胆管"),
    ("seq_18", "延迟期/肾脏层面", "延迟期，右肾区域"),
]
PROMPT_TEMPLATE = "你是一位资深放射科医生。请仔细分析这张上腹部MRI影像，并结合以下【纸质报告描述】进行印证分析。\n\n【纸质报告描述】\n{report_finding}\n\n【本张影像信息】\n- 序列: {seq_name}\n- 扫描部位: 上腹部（肝胆胰脾）+ 胰胆管薄层\n- 检查日期: 2026-04-11\n- 患者: [脱敏]，男，38岁，检查编号Y00002207707\n- 临床指征: 胰管支架置入后复查，腹痛待查\n\n请完成以下分析：\n1. 【解剖定位】这张图片大约在哪个层面（肝脏？胰腺？肾脏？其他？）\n2. 【影像所见】详细描述可见的结构和信号特征\n3. 【印证评价】对照纸质报告描述，判断该影像表现是否与报告一致？一致/不一致/补充\n4. 【补充发现】纸质报告未提及但影像可见的异常\n\n请用专业医学影像语言描述，结论明确。中文输出。"


def load_dicom_image(path: Path) -> str:
    """将DICOM转换为JPEG并返回base64字符串。"""
    try:
        import io

        import pydicom
        from PIL import Image

        dcm = pydicom.dcmread(str(path))
        img = dcm.pixel_array
        img = img - img.min()
        if img.max() > 0:
            img = img / img.max()
        img = (img * 255).astype("uint8")
        pil_img = Image.fromarray(img, mode="L") if len(img.shape) == 2 else Image.fromarray(img)
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        raise RuntimeError(f"DICOM读取失败: {e}") from e


def analyze_single(image_b64: str, seq_name: str, seq_desc: str, finding: str) -> dict:
    text_prompt = PROMPT_TEMPLATE.format(
        report_finding=finding, seq_name=f"{seq_name} — {seq_desc}"
    )
    content = call_dashscope_multimodal(image_b64=image_b64, text_prompt=text_prompt, timeout=120)
    return {"status": "success", "seq_name": seq_name, "seq_desc": seq_desc, "analysis": content}


def main():
    import argparse

    parser = argparse.ArgumentParser(description="上腹部MRI报告印证分析")
    parser.add_argument("--id-card", required=True)
    args = parser.parse_args()
    imaging_base = WORK_ROOT / "raw" / f"patient_{args.id_card}" / "imaging"
    raw_ts = os.environ.get("ANALYSIS_TS", "")
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts or args.id_card
    lit_dir = WORK_ROOT / "data" / args.id_card / ts / "03_literature"
    lit_dir.mkdir(parents=True, exist_ok=True)
    if not imaging_base.exists():
        logger.info(f"[错误] 影像目录不存在: {imaging_base}")
        logger.info("   预期路径: raw/patient_{patient_id}/imaging/seq_01~19/*.dcm")
        raise SystemExit(1)
    logger.info(f"\n[{datetime.now().isoformat()}] 上腹部MRI报告印证分析")
    logger.info(f"  病人: {args.id_card}")
    logger.info(f"  影像目录: {imaging_base}")
    logger.info(f"  共分析 {len(SEQ_SELECTIONS)} 个序列\n")
    results = []
    for seq_dir_name, seq_desc, analysis_focus in SEQ_SELECTIONS:
        seq_path = imaging_base / seq_dir_name
        if not seq_path.exists():
            logger.info(f"[警告] 目录不存在: {seq_dir_name}，跳过")
            continue
        dcm_files = sorted(seq_path.glob("*.dcm"))
        if not dcm_files:
            logger.info(f"[警告] {seq_dir_name} 无DICOM文件，跳过")
            continue
        import random

        idx = random.randint(0, len(dcm_files) - 1)  # noqa: S311
        img_path = dcm_files[idx]
        print(
            f"[图片] 选取: {seq_dir_name}/{img_path.name} ({seq_desc}) 第{idx + 1}/{len(dcm_files)}帧"
        )
        try:
            b64 = load_dicom_image(img_path)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.info(f"  [失败] DICOM读取失败: {e}")
            continue
        finding_text = f"【分析重点】{analysis_focus}。{REPORT_FINDINGS}"
        try:
            r = analyze_single(b64, seq_dir_name, seq_desc, finding_text)
            results.append(r)
            logger.info("  [成功] 完成")
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            results.append(
                {"status": "error", "seq_name": seq_dir_name, "seq_desc": seq_desc, "error": str(e)}
            )
            logger.info(f"  [失败] 失败: {e}")
        time.sleep(1)
    output_path = lit_dir / "mri_report_check_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "test_date": datetime.now().isoformat(),
                "model": "qwen-vl-plus",
                "report_findings": REPORT_FINDINGS,
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"\n[保存] 结果已保存: {output_path}")
    md_path = lit_dir / "mri_report_check_results.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# MRI 报告印证分析\n\n")
        f.write("**检查日期**: 2026-04-11  **检查编号**: Y00002207707\n\n")
        f.write(f"## 纸质报告关键发现\n\n{REPORT_FINDINGS}\n\n---\n\n")
        for r in results:
            if r["status"] == "success":
                f.write(f"## {r['seq_name']} — {r['seq_desc']}\n\n")
                f.write(f"**帧位置**: {r.get('frame_idx', 'N/A')}\n\n")
                analysis_text = r.get("analysis", "")
                if isinstance(analysis_text, list):
                    analysis_text = analysis_text[0].get("text", "") if analysis_text else ""
                f.write(analysis_text)
                f.write("\n\n---\n\n")
            else:
                f.write(f"## {r['seq_name']} — [失败] 失败: {r.get('error', '')}\n\n")
    logger.info(f"[报告] Markdown 已保存: {md_path}")
    logger.info("\n" + "=" * 60)
    logger.info("[摘要] 分析摘要")
    logger.info("=" * 60)
    for r in results:
        if r["status"] == "success":
            logger.info(f"\n[成功] {r['seq_name']} ({r['seq_desc']})")
            logger.info(f"   {r['analysis'][:300]}...")
        else:
            logger.info(f"\n[失败] {r['seq_name']}: {r.get('error', '')}")


if __name__ == "__main__":
    main()
