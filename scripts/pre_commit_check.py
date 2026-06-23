#!/usr/bin/env python3
"""pre_commit_check.py — git pre-commit 钩子 (不依赖 pre-commit 框架)。

执行以下检查，失败则阻止 commit:
1. ruff check (fix 自动)
2. ruff format check
3. pytest 快速 smoke test (排除 e2e/scnet markers)

通过 .git/hooks/pre-commit 链接调用:
    cp scripts/pre_commit_check.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

或者手动跑:
    python scripts/pre_commit_check.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path | None = None) -> int:
    """执行命令并实时输出，退出码透传。"""
    print(f"\n>>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=cwd or REPO)


def main() -> int:
    print("=" * 60)
    print("Lab-Analysis pre-commit 检查")
    print("=" * 60)

    # 1. ruff check --fix
    rc = run(
        [sys.executable, "-m", "ruff", "check", "--fix", "lab_analysis/", "tests/", "scripts/"]
    )
    if rc != 0:
        print(f"\n[FAIL] ruff check 退出码 {rc}")
        return rc

    # 2. ruff format check (不自动 format，避免改 staged 内容)
    rc = run(
        [sys.executable, "-m", "ruff", "format", "--check", "lab_analysis/", "tests/", "scripts/"]
    )
    if rc != 0:
        print(f"\n[FAIL] ruff format --check 退出码 {rc}")
        print("       请先跑 `ruff format` 再 commit")
        return rc

    # 3. pytest 快速 smoke
    if shutil.which("pytest") is not None or True:  # 用 python -m pytest
        rc = run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-m",
                "not e2e and not scnet",
                "--no-header",
                "--no-cov",
                "-x",  # 首次失败即停
            ]
        )
        if rc != 0:
            print(f"\n[FAIL] pytest 退出码 {rc}")
            return rc

    print("\n" + "=" * 60)
    print("[OK] pre-commit 检查全部通过")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
