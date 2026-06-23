"""extract_lab_data — 从检验报告图片中提取完整检验指标并生成结构化文件。

用法：
  python -m lab_analysis.extract_lab_data --image /path/to/lab_report.jpg --id-card <身份证号>

功能：
  1. 使用 SCNet OCR + DeepSeek 从检验报告图片中提取所有检验指标
  2. 生成 metadata.md（报告元信息）
  3. 生成 metrics.md（检验指标数据，YAML 格式）
  4. 保存到 raw/patient_{ID}/papers/lab_report_{date}_{type}/ 目录
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from lab_analysis.patient_id import validate_id_card

from .. import _log
from .ocr import MAX_OCR_SIDE, call_scnet_ocr, encode_image_to_base64
from .parser import extract_lab_metrics
from .report import (
    WORK_ROOT,
    _sanitize_metrics,
    generate_metadata_md,
    generate_metrics_md,
    save_structured_report,
)

logger = _log.get_logger(__name__)

__all__ = [
    "extract_lab_metrics",
    "save_structured_report",
    "generate_metadata_md",
    "generate_metrics_md",
    "encode_image_to_base64",
    "call_scnet_ocr",
    "MAX_OCR_SIDE",
    "WORK_ROOT",
    "main_with_args",
]


def main_with_args(args) -> bool:
    """使用给定的参数执行提取流程（可被其他模块调用）。

    Args:
        args: argparse.Namespace 对象，包含 image, id_card, no_interactive

    Returns:
        是否成功
    """
    interactive = not args.no_interactive
    image_path = Path(args.image)
    id_card = getattr(args, "id_card", "") or ""

    if not image_path.exists():
        logger.info(f"[ERROR] 文件不存在: {image_path}")
        return False

    logger.info("=" * 60)
    logger.info("检验报告数据结构化提取工具")
    logger.info("=" * 60)
    logger.info(f"图片路径: {image_path.name}")
    logger.info(f"身份证号: {(id_card if id_card else '(未提供，将使用AI提取)')}")
    logger.info(f"交互模式: {('是' if interactive else '否（无效ID将直接放弃）')}")
    logger.info(f"工作区: {WORK_ROOT}")
    logger.info("=" * 60)

    try:
        logger.info("\n[步骤1] SCNet OCR + DeepSeek 提取检验指标...")
        data = extract_lab_metrics(image_path)
        if not data:
            logger.error("[ERROR] 数据提取失败")
            return False
        if "metrics" in data:
            data["metrics"] = _sanitize_metrics(data["metrics"])
            logger.info(f"[OK] 指标清洗完成: {len(data['metrics'])} 个有效指标")

        logger.info("\n[步骤2] 验证身份证号...")
        extracted_id = data.get("patient_id")
        validated_id = validate_id_card(id_card, extracted_id, interactive=interactive)
        if not validated_id:
            logger.error("[ERROR] 身份证号验证失败，终止处理")
            return False
        id_card = validated_id
        logger.info(f"[OK] 身份证号验证通过: {id_card}")

        logger.info("\n[步骤3] 生成结构化报告文件...")
        saved_dir = save_structured_report(data, id_card)
        logger.info("\n" + "=" * 60)
        logger.info("提取完成！")
        logger.info("=" * 60)
        logger.info(f"保存位置: {saved_dir}")
        logger.info(f"报告日期: {data.get('report_date')}")
        logger.info(f"报告类型: {data.get('report_type')}")
        logger.info(f"提取指标数: {len(data.get('metrics', {}))}")
        logger.info("\n主要指标:")
        for key in ["WBC", "RBC", "HGB", "PLT", "CRP", "hs-CRP"]:
            if key in data.get("metrics", {}):
                val = data["metrics"][key]
                logger.info(f"  {key}: {val}")
        logger.info("=" * 60)
        return True
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        logger.info(f"[ERROR] 处理失败: {e}")
        traceback.print_exc()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="从检验报告图片提取完整检验指标并生成结构化文件")
    parser.add_argument("--image", "-i", required=True, type=Path, help="检验报告图片路径")
    parser.add_argument(
        "--id-card",
        type=str,
        default="",
        help="患者身份证号(18位或15位，可选，不提供则使用AI提取的ID)",
    )
    parser.add_argument(
        "--no-interactive", action="store_true", help="禁用交互模式（当身份证号无效时直接放弃数据）"
    )
    args = parser.parse_args()
    ok = main_with_args(args)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
