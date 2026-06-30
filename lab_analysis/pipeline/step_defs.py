"""step_defs.py — Pipeline 步骤定义表。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StepDef:
    name: str
    module: str
    fatal: bool = True


CORE_STEPS = [
    StepDef("③ 数据加载", "data_loader"),
    StepDef("④ 数据分析", "data_analyzer"),
    StepDef("⑤ 文献检索", "literature_searcher"),
]
