"""检查 README.md 中的测试计数与 pytest 实际收集数是否一致。

动机:
    README badge / 表格里手写的 438 用例会过期, 需要 CI 兜底。
    类似 scripts/quant_eval_gate.py 风格, 失败时 exit 1 阻断 PR。

用法:
    python scripts/check_test_count.py
    # 或带 README 路径: --readme README.md
    # 或带 pytest 参数: --pytest-args "-q"

退出码:
    0 = README 数字与实际一致
    1 = 不一致 (输出 diff)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 兼容相对路径: scripts/ 在仓库根
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# README 里出现的所有 "测试计数" 模式。
# 顺序无关, 只要发现任一处与 actual 不一致, 就报错。
README_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"Tests-(\d+)_"),  # badge URL: Tests-NNN_✔
    re.compile(r"pytest[（(]\s*(\d+)\s*用例[）)]"),  # 表格: pytest（NNN 用例）
    re.compile(r"全量\s*(\d+)\s*用例"),  # 命令注释: 全量 NNN 用例
)


def actual_test_count(pytest_args: list[str]) -> int:
    """跑 `pytest --collect-only -q` 解析最后一行的 collected 数。"""
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", *pytest_args]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    m = re.search(r"(\d+)\s+tests?\s+collected", output)
    if not m:
        print("ERROR: 无法解析 pytest --collect-only 输出", file=sys.stderr)
        print(output, file=sys.stderr)
        raise SystemExit(2)
    return int(m.group(1))


def find_readme_numbers(readme: Path) -> list[tuple[int, int, str]]:
    """扫 README, 返回 (line_no, number, line) 列表。"""
    hits: list[tuple[int, int, str]] = []
    if not readme.is_file():
        print(f"ERROR: {readme} 不存在", file=sys.stderr)
        raise SystemExit(2)
    for i, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
        for pat in README_PATTERNS:
            for m in pat.finditer(line):
                hits.append((i, int(m.group(1)), line.strip()))
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--readme",
        type=Path,
        default=REPO_ROOT / "README.md",
        help="README 路径 (默认: 仓库根 README.md)",
    )
    parser.add_argument(
        "--pytest-args",
        nargs=argparse.REMAINDER,
        default=[],
        help="传给 pytest --collect-only 的额外参数 (放在 -- 之后)",
    )
    args = parser.parse_args()

    actual = actual_test_count(args.pytest_args)
    print(f"pytest 实际收集: {actual} tests")

    hits = find_readme_numbers(args.readme)
    if not hits:
        print(f"ERROR: 在 {args.readme} 中未发现任何测试计数", file=sys.stderr)
        return 1

    print(f"README 命中 {len(hits)} 处:")
    bad: list[tuple[int, int, int, str]] = []
    for line_no, number, line in hits:
        marker = "OK " if number == actual else "BAD"
        print(f"  [{marker}] L{line_no:>4d}  {number:>4d}  {line[:100]}")
        if number != actual:
            bad.append((line_no, number, actual, line))

    if bad:
        print(
            f"\nFAIL: {len(bad)} 处不一致 (actual={actual})",
            file=sys.stderr,
        )
        print("修法: 更新 README 或用下面命令一次性替换:", file=sys.stderr)
        for _line_no, number, actual_val, _ in bad:
            print(
                f"  sed -i 's/{number}/{actual_val}/g' {args.readme}",
                file=sys.stderr,
            )
        return 1

    print(f"\nPASS: README 所有 {len(hits)} 处测试计数均与实际一致 ({actual})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
