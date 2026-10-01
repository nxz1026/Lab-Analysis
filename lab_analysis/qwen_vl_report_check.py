"""
qwen_vl_report_check.py
上腹部MRI报告印证分析 — 每个部位选1-2张代表性DICOM图
用法: python qwen_vl_report_check.py --id-card <脱敏ID> [--report-text <纸质报告文本文件>]

⚠️ 纸质报告文本必须由调用方提供 (--report-text)。本模块**不内置任何示例病例数据**:
历史版本曾把某位真实患者的检查结论写死为 REPORT_FINDINGS 常量, 导致每位患者的报告
都被注入他人的病灶描述。未提供 --report-text 时只做纯影像分析, 跳过「印证」环节。
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
    """载入**该患者自己**的纸质 MRI 报告文本。

    Args:
        report_text: 文本文件路径 (--report-text), None 表示未提供。

    Returns:
        报告文本; 未提供或读取失败时返回空串, 调用方据此跳过「印证」环节。

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


def analyze_single(
    image_b64: str,
    seq_name: str,
    seq_desc: str,
    finding: str,
    patient_ctx: dict | None = None,
) -> dict:
    ctx = patient_ctx or {}
    fields = {
        "seq_name": f"{seq_name} — {seq_desc}",
        "exam_date": ctx.get("exam_date", "未提供"),
        "patient_desc": ctx.get("patient_desc", "[脱敏]"),
        "exam_id": ctx.get("exam_id", "未提供"),
        "indication": ctx.get("indication", "未提供"),
    }
    if finding:
        text_prompt = PROMPT_TEMPLATE.format(report_finding=finding, **fields)
    else:
        text_prompt = PROMPT_TEMPLATE_NO_REPORT.format(**fields)
    content = call_dashscope_multimodal(image_b64=image_b64, text_prompt=text_prompt, timeout=120)
    return {
        "status": "success",
        "seq_name": seq_name,
        "seq_desc": seq_desc,
        # 归一成 [{"text": ...}]: call_dashscope_multimodal 原样透传 message.content,
        # 可能是 content 块列表也可能是纯字符串, 而消费端 gen_final_report.py 固定
        # 按 [0]["text"] 解析 —— 透传 str 会让影像证据退化成「(影像数据解析失败)」
        "analysis": _normalize_analysis(content),
    }


def _normalize_analysis(content: object) -> list[dict]:
    """把 multimodal 返回归一成 ``[{"text": ...}]``。

    DashScope 的 ``message.content`` 形态不固定 (见 tests/test_llm_client_extra.py
    两种断言); 本模块自身的 Markdown 渲染与下游 gen_final_report 都按 list 解析。
    """
    if isinstance(content, list):
        return [c if isinstance(c, dict) else {"text": str(c)} for c in content] or [{"text": ""}]
    if isinstance(content, dict):
        return [content]
    return [{"text": "" if content is None else str(content)}]


def main():
    import argparse

    parser = argparse.ArgumentParser(description="上腹部MRI报告印证分析")
    parser.add_argument("--id-card", required=True)
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
    logger.info(f"\n[{datetime.now().isoformat()}] 上腹部MRI报告印证分析")
    logger.info(f"  病人: {args.id_card}")
    logger.info(f"  影像目录: {imaging_base}")
    logger.info(f"  共分析 {len(SEQ_SELECTIONS)} 个序列")
    logger.info(
        f"  纸质报告文本: {'已载入' if report_findings else '未提供 — 仅做影像描述, 跳过印证'}"
    )
    logger.info("")
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
        logger.info(
            f"[图片] 选取: {seq_dir_name}/{img_path.name} ({seq_desc}) 第{idx + 1}/{len(dcm_files)}帧"
        )
        try:
            b64 = load_dicom_image(img_path)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.info(f"  [失败] DICOM读取失败: {e}")
            continue
        finding_text = f"【分析重点】{analysis_focus}。{report_findings}" if report_findings else ""
        try:
            r = analyze_single(b64, seq_dir_name, seq_desc, finding_text, patient_ctx)
            results.append(r)
            logger.info("  [成功] 完成")
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            results.append(
                {"status": "error", "seq_name": seq_dir_name, "seq_desc": seq_desc, "error": str(e)}
            )
            logger.info(f"  [失败] 失败: {e}")
        time.sleep(1)
    output_path = lit_dir / "mri_report_check_results.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "test_date": datetime.now().isoformat(),
                "model": "qwen-vl-plus",
                "report_findings": report_findings,
                "cross_checked": bool(report_findings),
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    logger.info(f"\n[保存] 结果已保存: {output_path}")
    md_path = lit_dir / "mri_report_check_results.md"
    with md_path.open("w", encoding="utf-8") as f:
        f.write("# MRI 报告印证分析\n\n")
        f.write(
            f"**检查日期**: {patient_ctx['exam_date']}  **检查编号**: {patient_ctx['exam_id']}\n\n"
        )
        if report_findings:
            f.write(f"## 纸质报告关键发现\n\n{report_findings}\n\n---\n\n")
        else:
            f.write("> 本次未提供纸质报告文本，以下为纯影像描述，未做报告印证。\n\n---\n\n")
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
