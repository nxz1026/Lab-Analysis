"""lab_analysis.pipeline.cli — CLI 参数解析 + 仓库路径工具"""

from __future__ import annotations

import argparse
from pathlib import Path

from lab_analysis.patient_id import encode


def repo_root() -> Path:
    """本仓库根目录（含 pyproject.toml / lab_analysis 包）。"""
    return Path(__file__).resolve().parent.parent.parent


def get_deid(id_card: str) -> str:
    """身份证号 → 脱敏 ID（确定性 AES-GCM，见 patient_id.encode）。"""
    return encode(id_card)


def parse_args():
    parser = argparse.ArgumentParser(description="医学分析 Pipeline 统一入口")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 循证解读步骤")
    parser.add_argument("--skip-imaging", action="store_true", help="跳过影像分析步骤")
    parser.add_argument("--skip-ingest", action="store_true", help="跳过数据摄入步骤（使用已有数据）")
    parser.add_argument("--use-dspy", action="store_true", help="使用 DSPy 优化版本进行文献解读")
    parser.add_argument("--ingest-lab", type=str, nargs="*", help="检验报告图片路径列表")
    parser.add_argument("--ingest-dicom-zip", type=str, help="DICOM ZIP文件路径")
    parser.add_argument("--ingest-dicom-dir", type=str, help="DICOM已解压目录路径")
    parser.add_argument("--ingest-mri-report", type=str, help="MRI文字报告路径")
    parser.add_argument("--report-date", type=str, help="报告日期 YYYY-MM-DD（用于摄入）")
    parser.add_argument("--report-type", type=str, choices=["outpatient", "inpatient"],
                       help="报告类型 outpatient/inpatient（仅检验报告需要）")
    parser.add_argument("--no-interactive", action="store_true",
                       help="禁用于数据摄入的交互式 ID 确认（不一致时直接放弃该图片）")
    return parser.parse_args()
