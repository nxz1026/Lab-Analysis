#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多 patient 数据集支持（DSPy 训练数据收集框架）

设计目标:
1. 当前项目仅 1 个 patient (846552421134373347)，未来扩容时无需重写采集逻辑
2. 提供统一的样本迭代器，compile_all / quant_eval / 任何脚本都能复用
3. 单 patient 时行为与旧 collect_samples_from_runs() 完全一致

接口:
- list_patients() -> list[str]                  所有 patient_id
- list_timestamps(patient_id) -> list[str]      单个 patient 的所有时间戳
- iter_all_samples() -> Iterator[Sample]        跨所有 patient + timestamp 的样本
- find_pairs(patient_id) -> list[(std_ts, dspy_ts)]
                                                同 patient 内的 std / dspy 双跑配对
                                                供 dual_mode_pipeline / quant_eval 使用

兼容性:
- 旧 collect_samples_from_runs() 调用者: 直接改调 iter_all_samples() 即可
- 当前 compile 脚本仍只取第一个 patient（保留原行为，框架已就绪待用）
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from ..utils import get_project_root


@dataclass
class Sample:
    """单次 pipeline 运行的样本元数据

    Attributes:
        patient_id: 脱敏身份证号 (如 846552421134373347)
        timestamp: pipeline 运行时间戳 (如 20260620_175252)
        data_dir: 该次运行的根目录 (data/{patient_id}/{timestamp}/)
        is_dspy: 是否为 DSPy 模式产物 (含 dspy_prompts/ 目录)
        has_final_md: 是否存在 final_integrated_report.md
    """

    patient_id: str
    timestamp: str
    data_dir: Path
    is_dspy: bool = False
    has_final_md: bool = False


def get_data_root() -> Path:
    """data/ 根目录（项目根下的 data/）"""
    return get_project_root() / "data"


def list_patients() -> list[str]:
    """列出 data/ 下所有 patient 目录名（去重，按字母序）"""
    root = get_data_root()
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def list_timestamps(patient_id: str) -> list[str]:
    """列出某 patient 下所有 timestamp 目录（按时间序）"""
    pdir = get_data_root() / patient_id
    if not pdir.exists():
        return []
    return sorted(t.name for t in pdir.iterdir() if t.is_dir())


def _is_dspy_run(data_dir: Path) -> bool:
    """判断该次运行是否走 DSPy 模式

    判定逻辑（与 dual_mode_pipeline._auto_pick_runs 一致）:
    - 04_reports/dspy_prompts/ 子目录存在 → DSPy 模式
    - 或 04_reports/final_integrated_report.json 存在但 .md 不存在 → DSPy 模式
      （早期 DSPy 跑可能只产 .json 不产 .md）
    """
    rep = data_dir / "04_reports"
    if (rep / "dspy_prompts").is_dir():
        return True
    js = rep / "final_integrated_report.json"
    md = rep / "final_integrated_report.md"
    return bool(js.exists() and not md.exists())


def _build_sample(patient_id: str, ts: str) -> Sample:
    """从 patient_id + timestamp 构造 Sample"""
    data_dir = get_data_root() / patient_id / ts
    return Sample(
        patient_id=patient_id,
        timestamp=ts,
        data_dir=data_dir,
        is_dspy=_is_dspy_run(data_dir),
        has_final_md=(data_dir / "04_reports" / "final_integrated_report.md").exists(),
    )


def iter_all_samples(patient_ids: list[str] | None = None) -> Iterator[Sample]:
    """跨所有 patient + timestamp 迭代样本

    Args:
        patient_ids: 限定 patient 列表；None 表示全部 patient

    Yields:
        Sample 对象
    """
    pids = patient_ids or list_patients()
    for pid in pids:
        for ts in list_timestamps(pid):
            yield _build_sample(pid, ts)


def find_pairs(patient_id: str) -> list[tuple[str, str]]:
    """找到同 patient 内的 std / dspy 配对 (按时间最近配对)

    配对规则:
    - 同一 patient 下，按时间升序
    - 找到 is_dspy=False 的 run 作为 std，is_dspy=True 的 run 作为 dspy
    - 每个 dspy 找它之前最近的 std；找不到配对的孤立 run 跳过

    Returns:
        [(std_ts, dspy_ts), ...] 列表，按 dspy_ts 升序
    """
    timestamps = list_timestamps(patient_id)
    if not timestamps:
        return []
    samples = [_build_sample(patient_id, ts) for ts in timestamps]
    pairs: list[tuple[str, str]] = []
    for i, s in enumerate(samples):
        if not s.is_dspy:
            continue
        # 找 i 之前最近的 std
        for j in range(i - 1, -1, -1):
            if not samples[j].is_dspy and samples[j].has_final_md:
                pairs.append((samples[j].timestamp, s.timestamp))
                break
    return pairs


def load_summary_artifact(sample: Sample) -> dict | None:
    """加载某次运行的 summary 文件（analysis_results.json 或 final_integrated_report.md）"""
    js = sample.data_dir / "02_analyzed" / "analysis_results.json"
    if js.exists():
        try:
            return json.loads(js.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
    return None


def stats() -> dict:
    """统计所有 patient 的样本量

    Returns:
        {
          "n_patients": int,
          "n_total_samples": int,
          "n_dspy_samples": int,
          "n_std_samples": int,
          "per_patient": {patient_id: {"total": n, "dspy": n, "std": n}}
        }
    """
    per_patient: dict[str, dict[str, int]] = {}
    n_dspy = 0
    n_std = 0
    for s in iter_all_samples():
        d = per_patient.setdefault(s.patient_id, {"total": 0, "dspy": 0, "std": 0})
        d["total"] += 1
        if s.is_dspy:
            d["dspy"] += 1
            n_dspy += 1
        else:
            d["std"] += 1
            n_std += 1
    return {
        "n_patients": len(per_patient),
        "n_total_samples": n_dspy + n_std,
        "n_dspy_samples": n_dspy,
        "n_std_samples": n_std,
        "per_patient": per_patient,
    }


if __name__ == "__main__":
    import sys

    s = stats()
    print(json.dumps(s, ensure_ascii=False, indent=2))
    if "--pairs" in sys.argv:
        for pid in list_patients():
            pairs = find_pairs(pid)
            if pairs:
                print(f"\n[{pid}] {len(pairs)} pair(s):")
                for std_ts, dspy_ts in pairs:
                    print(f"  std={std_ts}  <->  dspy={dspy_ts}")
