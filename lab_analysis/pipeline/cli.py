"""lab_analysis.pipeline.cli — CLI 参数解析 + 仓库路径工具"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lab_analysis.patient_id import encode
from lab_analysis.utils import WORK_ROOT


def repo_root() -> Path:
    """本仓库根目录（含 pyproject.toml / lab_analysis 包）。"""
    return Path(__file__).resolve().parent.parent.parent


def _load_patient_mapping() -> dict[str, str]:
    """加载 .hermes/patient_mapping.json 映射表。
    格式：{ "<deid>": "<original_id_card>", ... }
    用于兼容 raw 目录已用历史 deid 命名的情况。
    """
    mapping_path = WORK_ROOT / ".hermes" / "patient_mapping.json"
    if not mapping_path.is_file():
        return {}
    try:
        data = json.loads(mapping_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return {}


def get_deid(id_card: str) -> str:
    """身份证号 → 脱敏 ID。

    优先级：
    1. .hermes/patient_mapping.json 中已映射的 value==id_card → 返回 key（历史 deid）
    2. 调用 encode(id_card) 生成新 deid（确定性 AES-GCM，见 patient_id.encode）

    此机制让现有 raw/patient_<existing_deid>/ 目录能复用，无需重跑数据摄入。
    """
    mapping = _load_patient_mapping()
    for deid, original in mapping.items():
        if original == id_card:
            return deid
    return encode(id_card)


def parse_args():
    parser = argparse.ArgumentParser(description="医学分析 Pipeline 统一入口")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 循证解读步骤")
    parser.add_argument("--skip-imaging", action="store_true", help="跳过影像分析步骤")
    parser.add_argument("--skip-ingest", action="store_true", help="跳过数据摄入步骤（使用已有数据）")
    parser.add_argument("--use-dspy", action="store_true", help="使用 DSPy 优化版本进行文献解读")
    parser.add_argument("--skip-lit-filter", action="store_true",
                        help="跳过文献二次筛选（步骤⑤b，evidence-grading）")
    parser.add_argument("--lit-filter-scenario", default="differential_diagnosis",
                        choices=["early_diagnosis", "differential_diagnosis", "prognosis"],
                        help="文献筛选场景权重")
    parser.add_argument("--lit-filter-top-k", type=int, default=8,
                        help="文献筛选保留前 k 篇（默认 8）")
    parser.add_argument("--ingest-lab", type=str, nargs="*", help="检验报告图片路径列表")
    parser.add_argument("--ingest-dicom-zip", type=str, help="DICOM ZIP文件路径")
    parser.add_argument("--ingest-dicom-dir", type=str, help="DICOM已解压目录路径")
    parser.add_argument("--ingest-mri-report", type=str, help="MRI文字报告路径")
    parser.add_argument("--report-date", type=str, help="报告日期 YYYY-MM-DD（用于摄入）")
    parser.add_argument("--report-type", type=str, choices=["outpatient", "inpatient"],
                       help="报告类型 outpatient/inpatient（仅检验报告需要）")
    parser.add_argument("--no-interactive", action="store_true",
                       help="禁用于数据摄入的交互式 ID 确认（不一致时直接放弃该图片）")
    parser.add_argument("--compare-report-modes", action="store_true",
                        help="步骤⑧同时跑 Standard + DSPy 双模式并输出对比报告")
    parser.add_argument("--auto-queries", action="store_true",
                        help="步骤⑤根据异常指标自动生成 PubMed 搜索词")
    parser.add_argument("--skip-pdf", action="store_true",
                        help="跳过步骤⑨b PDF 报告生成")
    parser.add_argument("--skip-scoring", action="store_true",
                        help="跳过步骤⑧b 评分卡 & 决策支持")
    parser.add_argument("--skip-cleanup", action="store_true",
                        help="跳过步骤⑩ 旧产物清理")
    parser.add_argument("--keep-last", type=int, default=3,
                        help="产物清理保留最近 N 次运行（默认 3）")
    return parser.parse_args()
