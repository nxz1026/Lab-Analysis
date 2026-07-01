"""extract_lab_data.report — 元数据/指标 Markdown 生成 + 保存。"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from .. import _log
from ..utils import WORK_ROOT

logger = _log.get_logger(__name__)


def generate_metadata_md(data: dict, validated_patient_id: str) -> str:
    """生成 metadata.md 文件内容。

    Args:
        data: AI 提取的数据
        validated_patient_id: 用户验证过的患者 ID（优先使用）
    """
    patient_id = validated_patient_id if validated_patient_id else data.get("patient_id", "")
    return (
        f"| 字段 | 值 |\n"
        f"|------|-----|\n"
        f"| 身份证号 | {patient_id} |\n"
        f"| 报告日期 | {data.get('report_date', '')} |\n"
        f"| 报告类型 | {data.get('report_type', '')} |\n"
        f"| 科室 | {data.get('department', '')} |\n"
        f"| 医生 | {data.get('physician', '')} |\n"
        f"| 诊断 | {data.get('diagnosis', '')} |\n"
    )


def _sanitize_metrics(metrics: dict) -> dict:
    """清洗指标值，将 <X / >X 等非数字格式转为纯数字。

    处理规则：
    - "<10" → 10.0（取检测限值）
    - ">3.0" → 3.0（取检测限值）
    - "—" / "-" / "" → 删除该指标
    - 已为正确保留不变
    """
    cleaned: dict = {}
    for key, val in metrics.items():
        if isinstance(val, (int, float)):
            cleaned[key] = float(val)
        elif isinstance(val, str):
            s = val.strip()
            if not s or s in ("—", "–", "-"):
                continue
            num_match = re.search(r"([0-9]+\.?\d*)", s)
            if num_match:
                cleaned[key] = float(num_match.group(1))
        elif isinstance(val, dict):
            inner = _sanitize_metrics(val)
            if inner:
                cleaned[key] = inner
    return cleaned


def generate_metrics_md(data: dict) -> str:
    """生成 metrics.md 文件内容（YAML 格式）。"""
    metrics = data.get("metrics", {})
    yaml_lines = []
    for key, val in metrics.items():
        if isinstance(val, (int, float)):
            yaml_lines.append(f"{key}: {val}")
        elif isinstance(val, dict):
            v = val.get("value")
            if v is not None:
                yaml_lines.append(f"{key}: {v}")
    return "\n".join(yaml_lines) + "\n"


def save_structured_report(data: dict, patient_id: str) -> str:
    """保存结构化报告到 papers/lab_report_{date}_{type}/ 目录。

    返回：保存的目录路径
    """
    from lab_analysis.pipeline.cli import get_deid

    patient_id_obf = get_deid(patient_id)
    report_date = data.get("report_date", "").replace("-", "")
    report_type = data.get("report_type", "unknown")
    report_dir = (
        WORK_ROOT
        / "raw"
        / f"patient_{patient_id_obf}"
        / "papers"
        / f"lab_report_{report_date}_{report_type}"
    )
    report_dir.mkdir(parents=True, exist_ok=True)

    metadata_md = generate_metadata_md(data, patient_id)
    metadata_path = report_dir / "metadata.md"
    metadata_path.write_text(metadata_md, encoding="utf-8")
    logger.info(f"[OK] 已生成: {metadata_path.relative_to(WORK_ROOT)}")

    metrics_md = generate_metrics_md(data)
    metrics_path = report_dir / "metrics.md"
    metrics_path.write_text(metrics_md, encoding="utf-8")
    logger.info(f"[OK] 已生成: {metrics_path.relative_to(WORK_ROOT)}")

    original_image = report_dir / "original_image.jpg"
    if not original_image.exists():
        lab_dir = WORK_ROOT / "raw" / f"patient_{patient_id_obf}" / "lab"
        if lab_dir.exists() and report_date:
            for img_file in lab_dir.glob(f"*{report_date}*"):
                if img_file.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                    shutil.copy2(img_file, original_image)
                    logger.info(f"[OK] 已复制原始图片: {original_image.relative_to(WORK_ROOT)}")
                    break
    return str(report_dir.relative_to(WORK_ROOT))
