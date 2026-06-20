"""lab_analysis.pipeline.steps — Pipeline 子步骤（检查/启动子进程等）"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from lab_analysis.error_logger import log_error, log_pipeline_error
from lab_analysis.pipeline.cli import get_deid
from lab_analysis.utils import WORK_ROOT


def extract_patient_id_from_reports() -> str | None:
    """从已摄入的检验报告 metadata.md 中提取身份证号。"""
    raw_dir = WORK_ROOT / "raw"
    if not raw_dir.exists():
        return None

    for patient_dir in raw_dir.iterdir():
        if not (patient_dir.is_dir() and patient_dir.name.startswith("patient_")):
            continue
        papers_dir = patient_dir / "papers"
        if not papers_dir.exists():
            continue

        for report_dir in sorted(papers_dir.glob("lab_report_*")):
            if not report_dir.is_dir():
                continue
            meta_path = report_dir / "metadata.md"
            if not meta_path.exists():
                continue

            for line in meta_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("|") and ("身份证号" in line or "患者ID" in line):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 3 and parts[2]:
                        id_card = parts[2]
                        print(f"[INFO] 从检验报告中提取到身份证号（已脱敏）: {get_deid(id_card)}")
                        return id_card
    return None


def check_patient_data(deid: str) -> bool:
    """检查病人原始数据目录是否存在且有内容。"""
    raw_dir = WORK_ROOT / "raw" / f"patient_{deid}"
    lab_dir = raw_dir / "lab"
    imaging_dir = raw_dir / "imaging"
    papers_dir = raw_dir / "papers"

    errors, warnings = [], []
    if not raw_dir.exists():
        errors.append(f"  [ERROR] 病人目录不存在: {raw_dir}")
    else:
        has_lab = lab_dir.exists() and any(lab_dir.iterdir())
        has_papers = papers_dir.exists() and any(papers_dir.iterdir())
        has_imaging = imaging_dir.exists() and any(imaging_dir.iterdir())
        if not has_lab and not has_papers:
            errors.append(f"  [ERROR] 未找到检验报告: {lab_dir} 或 {papers_dir}")
        if not has_imaging:
            warnings.append(f"  [WARNING] 未找到影像数据: {imaging_dir}（将跳过影像分析）")

    if errors:
        print("\n".join(errors))
        if warnings:
            print("\n".join(warnings))
        print(f"\n当前 {WORK_ROOT / 'raw'} 下的病人目录：")
        raw_parent = WORK_ROOT / "raw"
        if raw_parent.exists():
            for d in sorted(raw_parent.iterdir()):
                if d.is_dir():
                    print(f"  - {d.name}")
        else:
            print("  （raw 目录为空或不存在）")
        return False
    if warnings:
        print("\n".join(warnings))
    return True


def pick_python_exe() -> str:
    """优先使用项目 .venv 中的 Python；否则当前解释器。"""
    win_venv = WORK_ROOT / ".venv" / "Scripts" / "python.exe"
    unix_venv = WORK_ROOT / ".venv" / "bin" / "python"
    if win_venv.is_file():
        return str(win_venv)
    if unix_venv.is_file():
        return str(unix_venv)
    return sys.executable


def run_step(name: str, module: str, extra_args: list[str] | None = None,
             env: dict | None = None) -> int:
    """以 python -m lab_analysis.<module> 运行单步。"""
    root = Path(__file__).resolve().parent.parent.parent
    python = pick_python_exe()
    cmd = [python, "-m", f"lab_analysis.{module}"]
    if extra_args:
        cmd.extend(extra_args)
    print(f"\n{'='*60}\n[STEP] {name}\n命令: {' '.join(cmd)}\n{'='*60}")

    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    pp = str(root)
    full_env["PYTHONPATH"] = pp + os.pathsep + full_env.get("PYTHONPATH", "")

    try:
        result = subprocess.run(
            cmd, cwd=str(root), env=full_env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            log_error(
                message=f"Pipeline 步骤 '{name}' 执行失败",
                exc_info=None,
                context={
                    "module": module, "command": " ".join(cmd),
                    "returncode": result.returncode,
                    "error": (result.stderr or "Unknown error")[:500],
                },
                module="pipeline",
            )
        return result.returncode
    except Exception as e:
        log_pipeline_error(
            step_name=name,
            patient_id=env.get("ANALYSIS_TS", "unknown") if env else "unknown",
            exc_info=e,
            additional_context={"module": module},
        )
        return 1
