"""
上腹部MRI报告印证分析 - DSPy 增强版

支持传统 API 调用和 DSPy 优化两种模式
用法: python qwen_vl_report_check_dspy.py --id-card <ID> [--use-dspy] [--report-text <报告文本>]

⚠️ 纸质报告文本与患者信息必须由调用方提供 (--report-text / --exam-* / --patient-desc)。
本模块**不内置任何示例病例数据**: 历史版本把某位真实患者的检查结论与人口学信息
写死为常量, 会注入到每一位患者的分析中。
"""

import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path

from lab_analysis.llm_client import call_dashscope_multimodal, load_api_key

from . import _log
from ._phi_filter import strip_phi
from .utils import WORK_ROOT

logger = _log.get_logger(__name__)
SEQ_SELECTIONS = [
    ("seq_01", "肝胆胰脾T2加权横断面", "T2WI横断面，代表层面"),
    ("seq_02", "T2/扩散加权（DWI）", "DWI序列，肝右后叶区域"),
    ("seq_06", "动脉期增强扫描", "动脉期，胰头区域"),
    ("seq_09", "门脉期增强扫描", "门脉期，肝内胆管/胆囊"),
    ("seq_12", "胰胆管薄层MRCP", "MRCP，胰管+胆管"),
    ("seq_18", "延迟期/肾脏层面", "延迟期，右肾区域"),
]
_PATIENT_INFO_BLOCK = """【本张影像信息】
- 序列: {seq_name}
- 扫描部位: 上腹部（肝胆胰脾）+ 胰胆管薄层
- 检查日期: {exam_date}
- 患者: {patient_desc}
- 检查编号: {exam_id}
- 临床指征: {indication}"""

# 有纸质报告: 做「印证」
PROMPT_TEMPLATE = (
    "你是一位资深放射科医生。请仔细分析这张上腹部MRI影像，并结合以下【纸质报告描述】"
    "进行印证分析。\n\n【纸质报告描述】\n{report_finding}\n\n"
    + _PATIENT_INFO_BLOCK
    + """

请完成以下分析：
1. 【解剖定位】这张图片大约在哪个层面（肝脏？胰腺？肾脏？其他？）
2. 【影像所见】详细描述可见的结构和信号特征
3. 【印证评价】对照纸质报告描述，判断该影像表现是否与报告一致？一致/不一致/补充
4. 【补充发现】纸质报告未提及但影像可见的异常

请用专业医学影像语言描述，结论明确。中文输出。"""
)

# 无纸质报告: 只做影像描述, 明确禁止模型编造「与报告一致」的对照结论
PROMPT_TEMPLATE_NO_REPORT = (
    "你是一位资深放射科医生。请仔细分析这张上腹部MRI影像。\n\n"
    + _PATIENT_INFO_BLOCK
    + """

请完成以下分析：
1. 【解剖定位】这张图片大约在哪个层面（肝脏？胰腺？肾脏？其他？）
2. 【影像所见】详细描述可见的结构和信号特征
3. 【补充发现】影像可见的异常表现

注意: 本次未提供纸质报告文本, 请只依据影像本身描述, 不要推断或编造与报告的对照结论。
请用专业医学影像语言描述，结论明确。中文输出。"""
)


def load_report_findings(report_text: str | None) -> str:
    """载入**该患者自己**的纸质 MRI 报告文本; 未提供/读取失败时返回空串。

    ⚠️ 这里**不允许**任何内置兜底示例数据 —— 历史版本写死的 REPORT_FINDINGS 常量
    会把某位真实患者的病灶描述注入每一位患者的报告。
    """
    if not report_text:
        return ""
    path = Path(report_text)
    if not path.is_file():
        logger.info(f"  [警告] 纸质报告文本不存在: {path} — 跳过印证环节")
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as e:
        logger.info(f"  [警告] 纸质报告文本读取失败: {e} — 跳过印证环节")
        return ""
    if not text:
        logger.info("  [警告] 纸质报告文本为空 — 跳过印证环节")
    return text


def load_dicom_image(path: Path) -> str:
    """将DICOM转换为JPEG并返回base64字符串。"""
    try:
        import io

        import pydicom
        from PIL import Image

        dcm = pydicom.dcmread(str(path))
        img = dcm.pixel_array
        # 常量像素 (max == min) 会除零 → NaN → astype 静默变全黑图, 必须显式守卫
        img = img - img.min()
        if img.max() > 0:
            img = img / img.max()
        img = (img * 255).astype("uint8")
        pil_img = Image.fromarray(img)
        buffer = io.BytesIO()
        pil_img.save(buffer, format="JPEG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        logger.info(f"  [失败] DICOM读取失败: {e}")
        return None


def _normalize_analysis(content: object) -> list[dict]:
    """把 multimodal 返回归一成 ``[{"text": ...}]``。

    DashScope 的 ``message.content`` 形态不固定: 可能是 content 块列表, 也可能是
    纯字符串 (见 tests/test_llm_client_extra.py 两种断言)。下游
    ``gen_final_report.py`` 固定按 ``[0]["text"]`` 解析, 所以这里必须归一。
    """
    if isinstance(content, list):
        return [c if isinstance(c, dict) else {"text": str(c)} for c in content] or [{"text": ""}]
    if isinstance(content, dict):
        return [content]
    return [{"text": "" if content is None else str(content)}]


def _prompt_fields(seq_name: str, seq_desc: str, patient_ctx: dict | None) -> dict:
    ctx = patient_ctx or {}
    return {
        "seq_name": f"{seq_name} — {seq_desc}",
        "exam_date": ctx.get("exam_date", "未提供"),
        "patient_desc": ctx.get("patient_desc", "[脱敏]"),
        "exam_id": ctx.get("exam_id", "未提供"),
        "indication": ctx.get("indication", "未提供"),
    }


def analyze_single_standard(
    image_b64: str,
    seq_name: str,
    seq_desc: str,
    finding: str,
    patient_ctx: dict | None = None,
) -> dict:
    """标准模式: 直接调用 Qwen-VL API"""
    fields = _prompt_fields(seq_name, seq_desc, patient_ctx)
    if finding:
        prompt = PROMPT_TEMPLATE.format(report_finding=finding, **fields)
    else:
        prompt = PROMPT_TEMPLATE_NO_REPORT.format(**fields)
    content = call_dashscope_multimodal(image_b64=image_b64, text_prompt=prompt, timeout=120)
    return {
        "status": "success",
        "seq_name": seq_name,
        "seq_desc": seq_desc,
        # 归一: call_dashscope_multimodal 原样透传 message.content, 可能是
        # [{"text": ...}] 也可能是纯字符串。消费端 gen_final_report.py 统一按
        # list 解析, 这里若透传 str 会让所有影像证据退化成「(影像数据解析失败)」。
        "analysis": _normalize_analysis(content),
        "mode": "standard",
        "prompt_length": len(prompt),
    }


def analyze_single_dspy(
    image_b64: str,
    seq_name: str,
    seq_desc: str,
    finding: str,
    patient_ctx: dict | None = None,
) -> dict:
    """DSPy 模式: 使用优化的 MRI 分析模块"""
    try:
        from lab_analysis.dspy_modules import run_dspy_mri_analysis

        ctx = patient_ctx or {}
        # 临床背景必须来自本患者的实参, 绝不使用写死的示例人口学信息
        clinical_context = (
            "，".join(
                x
                for x in (
                    ctx.get("patient_desc", ""),
                    ctx.get("indication", ""),
                    f"检查编号{ctx.get('exam_id', '')}" if ctx.get("exam_id") else "",
                )
                if x
            )
            or "未提供"
        )
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
            # 必须与标准模式同构: 消费端 gen_final_report.py 统一按 [{"text": ...}] 解析,
            # 这里若写 str 会让所有影像证据被替换成「(影像数据解析失败)」
            "analysis": [{"text": formatted_analysis}],
            "mode": "dspy_optimized",
            "confidence": result["confidence_score"],
        }
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        NameError,
        OSError,
        RuntimeError,
    ) as e:
        logger.info(f"  [警告] DSPy 分析失败，回退到标准模式: {e}")
        return analyze_single_standard(image_b64, seq_name, seq_desc, finding, patient_ctx)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="上腹部MRI报告印证分析 - DSPy 增强版")
    parser.add_argument("--id-card", required=True)
    parser.add_argument("--use-dspy", action="store_true", help="使用 DSPy 优化版本")
    parser.add_argument(
        "--report-text",
        default=None,
        help="该患者纸质MRI报告的文本文件路径; 不提供则只做纯影像分析(跳过印证)",
    )
    parser.add_argument("--exam-id", default="", help="检查编号 (写入报告表头)")
    parser.add_argument("--exam-date", default="", help="检查日期 (写入报告表头)")
    parser.add_argument("--indication", default="", help="临床指征")
    parser.add_argument("--patient-desc", default="", help="患者描述, 如 '男, 58岁'")
    args = parser.parse_args()
    load_api_key("DASHSCOPE_API_KEY")  # 导入期不校验, 真正调用前才检查
    report_findings = load_report_findings(args.report_text)
    patient_ctx = {
        "exam_id": args.exam_id or "未提供",
        "exam_date": args.exam_date or "未提供",
        "indication": args.indication or "未提供",
        "patient_desc": args.patient_desc or "[脱敏]",
    }
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
    logger.info(f"  共分析 {len(SEQ_SELECTIONS)} 个序列")
    logger.info(
        f"  纸质报告文本: {'已载入' if report_findings else '未提供 — 仅做影像描述, 跳过印证'}"
    )
    logger.info("")
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
                result = analyze_single_dspy(
                    image_b64, seq_name, seq_desc, report_findings, patient_ctx
                )
            else:
                result = analyze_single_standard(
                    image_b64, seq_name, seq_desc, report_findings, patient_ctx
                )
            elapsed = time.time() - start_time
            logger.info(f"  [成功] 完成 (耗时: {elapsed:.1f}s)")
            results.append(result)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.info(f"  [失败] 分析失败: {e}")
            results.append(
                {"status": "error", "seq_name": seq_name, "seq_desc": seq_desc, "error": str(e)}
            )
    output_path = lit_dir / "mri_report_check_results.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "patient_id": args.id_card,
                "mode": "dspy_optimized" if args.use_dspy else "standard",
                "total_sequences": len(SEQ_SELECTIONS),
                "analyzed_count": len([r for r in results if r["status"] == "success"]),
                "report_findings": report_findings,
                "cross_checked": bool(report_findings),
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    prompts_dir = lit_dir / "dspy_prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    standard_prompt_path = prompts_dir / "mri_analyzer_standard_prompt.txt"
    # 落盘的是「实际发给模型的提示词」, 且必须过 PHI 过滤 —— 见 prompt_inspector 的
    # "# P0: 落盘前过滤 PHI" 要求, 标准模式此前漏了这一步
    rendered_prompt = (
        PROMPT_TEMPLATE.format(
            report_finding=report_findings, **_prompt_fields("", "", patient_ctx)
        )
        if report_findings
        else PROMPT_TEMPLATE_NO_REPORT.format(**_prompt_fields("", "", patient_ctx))
    )
    with standard_prompt_path.open("w", encoding="utf-8") as f:
        f.write(strip_phi(rendered_prompt))
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
