"""pytest 全局配置 — 设置测试环境变量，避免模块加载时触发副作用"""

from __future__ import annotations

import base64
import os
import re
import secrets
from collections.abc import Iterator
from pathlib import Path

import pytest

# 预生成测试用脱敏密钥，避免测试中自动写入 .hermes/master.key
_TEST_KEY = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
os.environ.setdefault("LAB_DEID_KEY", _TEST_KEY)

# 设置 WORK_ROOT 指向仓库根，确保路径一致
os.environ.setdefault("WORK_ROOT", os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# 共享 fixture: 动态发现 data/<pid>/ 下真实存在的 run 目录
# ---------------------------------------------------------------------------
# 历史教训: 硬编码 20260620_175252 / 20260620_175730 在测试里, 每次 cleanup 后必 fail。
# 这里改成扫盘, 让测试跟随数据现状走, 而不是跟随某个 snapshot。
_TS_RE = re.compile(r"^\d{8}_\d{6}$")


def _is_dspy_run(data_dir: Path) -> bool:
    """与 lab_analysis.dspy_modules.multi_patient._is_dspy_run 保持一致。

    判定逻辑:
    - 04_reports/dspy_prompts/ 存在 → DSPy
    - 或 04_reports/final_integrated_report.json 存在但 .md 不存在 → DSPy (早期只有 json)
    """
    rep = data_dir / "04_reports"
    if (rep / "dspy_prompts").is_dir():
        return True
    js = rep / "final_integrated_report.json"
    md = rep / "final_integrated_report.md"
    return bool(js.exists() and not md.exists())


def _has_final_md(data_dir: Path) -> bool:
    return (data_dir / "04_reports" / "final_integrated_report.md").is_file()


def _scan_runs(work_root: Path, patient_id: str) -> dict[str, object]:
    """扫描 data/<patient_id>/ 下所有合法 ts 目录, 分类 latest / dspy / std。

    与 multi_patient 的判定口径一致:
    - dspy_ts: 最新一个有 dspy_prompts/ 的 run
    - std_ts: 最新一个非 dspy 且有 final_integrated_report.md 的 run
    """
    base = work_root / "data" / patient_id
    if not base.is_dir():
        return {
            "exists": False,
            "all": [],
            "latest": None,
            "dspy_ts": None,
            "std_ts": None,
        }
    runs = sorted(d.name for d in base.iterdir() if d.is_dir() and _TS_RE.match(d.name))
    if not runs:
        return {
            "exists": True,
            "all": [],
            "latest": None,
            "dspy_ts": None,
            "std_ts": None,
        }
    latest = runs[-1]
    dspy_ts = next(
        (r for r in reversed(runs) if _is_dspy_run(base / r)),
        None,
    )
    std_ts = next(
        (r for r in reversed(runs) if not _is_dspy_run(base / r) and _has_final_md(base / r)),
        None,
    )
    return {
        "exists": True,
        "all": runs,
        "latest": latest,
        "dspy_ts": dspy_ts,
        "std_ts": std_ts,
    }


@pytest.fixture(scope="session")
def live_patient_runs() -> dict[str, object]:
    """session 级 fixture, 扫 846552421134373347 的真实 run 目录。

    Returns:
        dict: {exists, all, latest, dspy_ts, std_ts}
        任一字段为 None 表示该类 run 不存在, 测试应 skip 而非 fail。
    """
    work_root = Path(os.environ["WORK_ROOT"])
    return _scan_runs(work_root, "846552421134373347")


@pytest.fixture
def tmp_patient_runs(tmp_path: Path) -> Iterator[dict[str, object]]:
    """function 级 fixture, 在 tmp_path 造一个空骨架, 用于隔离测试。

    Returns:
        dict: {exists=True, all=[], latest=None, dspy_ts=None, std_ts=None}
    """
    yield {
        "exists": True,
        "all": [],
        "latest": None,
        "dspy_ts": None,
        "std_ts": None,
    }
