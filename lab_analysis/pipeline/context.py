"""lab_analysis.pipeline.context — Pipeline 上下文对象"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lab_analysis.utils import WORK_ROOT


@dataclass(frozen=True)
class PipelineContext:
    """Pipeline 运行上下文，替代环境变量传递。

    Attributes:
        deid: 脱敏患者 ID
        timestamp: 时间戳（如 20260620_150000）
        patient_dir: 原始数据目录 raw/patient_{deid}/
        data_dir: 输出目录 data/{deid}/{timestamp}/
    """

    deid: str
    timestamp: str

    @property
    def patient_dir(self) -> Path:
        return WORK_ROOT / "raw" / f"patient_{self.deid}"

    @property
    def data_dir(self) -> Path:
        return WORK_ROOT / "data" / self.deid / self.timestamp

    @property
    def analyzed_dir(self) -> Path:
        return self.data_dir / "02_analyzed"

    @property
    def literature_dir(self) -> Path:
        return self.data_dir / "03_literature"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "04_reports"

    @property
    def figures_dir(self) -> Path:
        return self.analyzed_dir / "figures"

    @property
    def raw_papers(self) -> Path:
        return self.patient_dir / "papers"

    @property
    def raw_lab(self) -> Path:
        return self.patient_dir / "lab"

    @property
    def raw_imaging(self) -> Path:
        return self.patient_dir / "imaging"

    def env_dict(self) -> dict[str, str]:
        """返回兼容旧环境变量的 dict（用于子进程）。"""
        return {
            "ANALYSIS_TS": f"{self.deid}/{self.timestamp}",
            "WORK_ROOT": str(WORK_ROOT),
        }
