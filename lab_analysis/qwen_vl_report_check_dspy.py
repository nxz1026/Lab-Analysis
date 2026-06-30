"""
上腹部MRI报告印证分析 - DSPy 增强版

支持传统 API 调用和 DSPy 优化两种模式
用法: python qwen_vl_report_check_dspy.py --id-card <ID> [--use-dspy]
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
        img = ((img - img.min()) / (img.max() - img.min()) * 255).astype("uint8")
        pil_img = Image.fromarray(img)
        buffer = io.BytesIO()
        pil_img.save(buffer, format="JPEG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        logger.info(f"  [失败] DICOM读取失败: {e}")
        return None


def analyze_single_standard(image_b64: str, seq_name: str, seq_desc: str, finding: str) -> dict:
    """标准模式: 直接调用 Qwen-VL API"""
    prompt = PROMPT_TEMPLATE.format(report_finding=finding, seq_name=f"{seq_name} — {seq_desc}")
    content = call_dashscope_multimodal(image_b64=image_b64, text_prompt=prompt, timeout=120)
    return {
        "status": "success",
        "seq_name": seq_name,
        "seq_desc": seq_desc,
        "analysis": content,
        "mode": "standard",
        "prompt_length": len(prompt),
    }


def analyze_single_dspy(image_b64: str, seq_name: str, seq_desc: str, finding: str) -> dict:
    """DSPy 模式: 使用优化的 MRI 分析模块"""
    try:
        from lab_analysis.dspy_modules import run_dspy_mri_analysis

        clinical_context = "男，38岁，胰管支架置入后复查，腹痛待查，检查编号Y00002207707"
        model_path = str(
            Path(__file__).parent.parent / "models" / "dspy" / "mri_analyzer_compiled.json"
        )
        result = run_dspy_mri_analysis(
            image_desc=f"{seq_name} — {seq_desc}",
            report_findings=finding,
            clinical_context=clinical_context,
            model_path=model_path,
        )
        formatted_analysis = f"【解剖定位】\n{result['anatomical_localization']}\n\n【影像所见】\n{result['imaging_findings']}\n\n【印证评价】\n{result['consistency_evaluation']}\n\n【补充发现】\n{result['additional_findings']}\n\n【置信度】{result['confidence_score']:.2f}"
        return {
            "status": "success",
            "seq_name": seq_name,
            "seq_desc": seq_desc,
            "analysis": formatted_analysis,
            "mode": "dspy_optimized",
            "confidence": result["confidence_score"],
        }
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        logger.info(f"  [警告] DSPy 分析失败，回退到标准模式: {e}")
        return analyze_single_standard(image_b64, seq_name, seq_desc, finding)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="上腹部MRI报告印证分析 - DSPy 增强版")
    parser.add_argument("--id-card", required=True)
    parser.add_argument("--use-dspy", action="store_true", help="使用 DSPy 优化版本")
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
    mode_label = "[DSPy]" if args.use_dspy else "[标准]"
    logger.info(f"\n[{datetime.now().isoformat()}] {mode_label} 上腹部MRI报告印证分析")
    logger.info(f"  病人: {args.id_card}")
    logger.info(f"  影像目录: {imaging_base}")
    logger.info(f"  共分析 {len(SEQ_SELECTIONS)} 个序列\n")
    results = []
    for seq_id, seq_name, seq_desc in SEQ_SELECTIONS:
        seq_dir = imaging_base / seq_id
        if not seq_dir.exists():
            logger.info(f"[警告] 目录不存在: {seq_id}，跳过")
            continue
        dcm_files = list(seq_dir.glob("*.dcm")) + list(seq_dir.glob("*.DCM"))
        if not dcm_files:
            logger.info(f"[警告] 无 DICOM 文件: {seq_id}，跳过")
            continue
        mid_idx = len(dcm_files) // 2
        selected_file = sorted(dcm_files)[mid_idx]
        logger.info(
            f"[图片] 选取: {seq_id}/{selected_file.name} ({seq_desc}) 第{mid_idx + 1}/{len(dcm_files)}帧"
        )
        image_b64 = load_dicom_image(selected_file)
        if not image_b64:
            continue
        start_time = time.time()
        try:
            if args.use_dspy:
                result = analyze_single_dspy(image_b64, seq_name, seq_desc, REPORT_FINDINGS)
            else:
                result = analyze_single_standard(image_b64, seq_name, seq_desc, REPORT_FINDINGS)
            elapsed = time.time() - start_time
            logger.info(f"  [成功] 完成 (耗时: {elapsed:.1f}s)")
            results.append(result)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.info(f"  [失败] 分析失败: {e}")
            results.append(
                {"status": "error", "seq_name": seq_name, "seq_desc": seq_desc, "error": str(e)}
            )
    output_path = lit_dir / "mri_report_check_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "patient_id": args.id_card,
                "mode": "dspy_optimized" if args.use_dspy else "standard",
                "total_sequences": len(SEQ_SELECTIONS),
                "analyzed_count": len([r for r in results if r["status"] == "success"]),
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    prompts_dir = lit_dir / "dspy_prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    standard_prompt_path = prompts_dir / "mri_analyzer_standard_prompt.txt"
    with open(standard_prompt_path, "w", encoding="utf-8") as f:
        f.write(PROMPT_TEMPLATE)
    logger.info(f"[保存] 标准 prompt 已保存: {standard_prompt_path}")
    if args.use_dspy:
        logger.info("[保存] DSPy 优化 prompt 保存位置: data/mri_dspy_prompts/")
    logger.info("\n[摘要] 分析摘要")
    logger.info(f"  总序列数: {len(SEQ_SELECTIONS)}")
    logger.info(f"  成功分析: {len([r for r in results if r['status'] == 'success'])}")
    logger.info(f"  失败: {len([r for r in results if r['status'] == 'error'])}")
    if args.use_dspy:
        avg_confidence = sum(
            (r.get("confidence", 0) for r in results if r["status"] == "success")
        ) / max(len([r for r in results if r["status"] == "success"]), 1)
        logger.info(f"  平均置信度: {avg_confidence:.2f}")
    logger.info(f"\n[保存] 结果已保存: {output_path}")


if __name__ == "__main__":
    main()
