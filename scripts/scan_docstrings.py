"""Scan docstring coverage for lab_analysis/.

Outputs a Markdown report to docs/DOCSTRING_BASELINE.md.

Usage:
    python scripts/scan_docstrings.py            # write report
    python scripts/scan_docstrings.py --stdout    # print only
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "lab_analysis"
REPORT = ROOT / "docs" / "DOCSTRING_BASELINE.md"


def _has_docstring(node: ast.AST) -> bool:
    """Return True if node has a non-empty docstring (as its first statement)."""
    return bool(ast.get_docstring(node))


def _classify(node: ast.AST) -> str:
    return type(node).__name__


def scan_file(path: Path) -> dict[str, list[tuple[str, int, bool]]]:
    """Walk a single file and bucket nodes into module/class/function/method."""
    buckets: dict[str, list[tuple[str, int, bool]]] = defaultdict(list)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print(f"[warn] syntax error in {path}: {exc}", file=sys.stderr)
        return buckets

    buckets["module"].append((path.name, 1, _has_docstring(tree)))

    # Collect all function-like nodes; methods are those nested in a ClassDef.
    class_methods: set[int] = set()
    for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        for member in cls.body:
            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_methods.add(id(member))

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            buckets["class"].append((node.name, node.lineno, _has_docstring(node)))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if id(node) in class_methods:
                # find owning class name (simple linear search is fine)
                owner = next(
                    (
                        c.name
                        for c in ast.walk(tree)
                        if isinstance(c, ast.ClassDef) and node in c.body
                    ),
                    "?",
                )
                buckets["method"].append(
                    (f"{owner}.{node.name}", node.lineno, _has_docstring(node))
                )
            else:
                buckets["function"].append((node.name, node.lineno, _has_docstring(node)))
    return buckets


def pct(numer: int, denom: int) -> str:
    if denom == 0:
        return "n/a"
    return f"{numer * 100 // denom}%"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stdout", action="store_true", help="print report to stdout instead of writing file"
    )
    args = parser.parse_args()

    files = sorted(p for p in TARGET.rglob("*.py") if "__pycache__" not in str(p))

    file_buckets: list[tuple[Path, dict[str, list[tuple[str, int, bool]]]]] = []
    for f in files:
        file_buckets.append((f, scan_file(f)))

    totals = defaultdict(lambda: [0, 0])  # kind -> [with, total]
    per_file_rows: list[tuple[str, int, int, int, int, int, int, int]] = []
    for f, b in file_buckets:
        mod = len(b["module"])
        mod_d = sum(1 for x in b["module"] if x[2])
        cls = len(b["class"])
        cls_d = sum(1 for x in b["class"] if x[2])
        fn = len(b["function"])
        fn_d = sum(1 for x in b["function"] if x[2])
        me = len(b["method"])
        me_d = sum(1 for x in b["method"] if x[2])
        per_file_rows.append((str(f.relative_to(ROOT)), mod, mod_d, cls, cls_d, fn, fn_d, me_d))
        totals["module"][0] += mod_d
        totals["module"][1] += mod
        totals["class"][0] += cls_d
        totals["class"][1] += cls
        totals["function"][0] += fn_d
        totals["function"][1] += fn
        totals["method"][0] += me_d
        totals["method"][1] += me

    # overall (function+method treated together as "callables")
    callable_with = totals["function"][0] + totals["method"][0]
    callable_tot = totals["function"][1] + totals["method"][1]

    lines: list[str] = []
    lines.append("# Docstring Coverage Baseline\n")
    lines.append(f"扫描目标: `{TARGET.relative_to(ROOT)}/`  ({len(files)} 个 .py 文件)\n")
    lines.append("## 总体统计\n")
    lines.append("| 类别 | 有 docstring | 总数 | 覆盖率 |")
    lines.append("|---|---:|---:|---:|")
    lines.append(
        f"| 模块 | {totals['module'][0]} | {totals['module'][1]} | "
        f"{pct(totals['module'][0], totals['module'][1])} |"
    )
    lines.append(
        f"| 类 | {totals['class'][0]} | {totals['class'][1]} | "
        f"{pct(totals['class'][0], totals['class'][1])} |"
    )
    lines.append(
        f"| 顶层函数 | {totals['function'][0]} | {totals['function'][1]} | "
        f"{pct(totals['function'][0], totals['function'][1])} |"
    )
    lines.append(
        f"| 方法 | {totals['method'][0]} | {totals['method'][1]} | "
        f"{pct(totals['method'][0], totals['method'][1])} |"
    )
    lines.append(
        f"| **可调用合计** | **{callable_with}** | **{callable_tot}** | "
        f"**{pct(callable_with, callable_tot)}** |"
    )
    lines.append("")

    lines.append("## 覆盖率最低的 15 个文件\n")
    # rebuild cleanly using totals per file
    file_missing = []
    for (f, b), _row in zip(file_buckets, per_file_rows, strict=True):
        mod_d = sum(1 for x in b["module"] if x[2])
        cls_d = sum(1 for x in b["class"] if x[2])
        fn_d = sum(1 for x in b["function"] if x[2])
        me_d = sum(1 for x in b["method"] if x[2])
        total = len(b["module"]) + len(b["class"]) + len(b["function"]) + len(b["method"])
        with_doc = mod_d + cls_d + fn_d + me_d
        missing = total - with_doc
        if missing > 0:
            file_missing.append((str(f.relative_to(ROOT)), total, with_doc, missing))
    file_missing.sort(key=lambda r: (-r[3], r[0]))
    lines.append("| 文件 | 总节点 | 有 docstring | 缺失 |")
    lines.append("|---|---:|---:|---:|")
    for name, total, with_doc, missing in file_missing[:15]:
        lines.append(f"| `{name}` | {total} | {with_doc} | {missing} |")
    lines.append("")

    lines.append("## 完整文件明细\n")
    lines.append("| 文件 | 模块 | 类 doc | 函数 doc | 方法 doc |")
    lines.append("|---|---:|---:|---:|---:|")
    for (f, b), _row in zip(file_buckets, per_file_rows, strict=True):
        name = str(f.relative_to(ROOT))
        mod_d = sum(1 for x in b["module"] if x[2])
        cls_d = sum(1 for x in b["class"] if x[2])
        fn_d = sum(1 for x in b["function"] if x[2])
        me_d = sum(1 for x in b["method"] if x[2])
        cls_t = len(b["class"])
        fn_t = len(b["function"])
        me_t = len(b["method"])
        lines.append(f"| `{name}` | {mod_d}/1 | {cls_d}/{cls_t} | {fn_d}/{fn_t} | {me_d}/{me_t} |")

    lines.append("")
    lines.append("## 建议\n")
    lines.append("- 短期：所有公共 API (`non-underscore` 函数/方法) 必须有 docstring。")
    lines.append("- 中期：把 `interrogate` 加入 dev extras，设置 `--fail-under=70` 作为 CI 门槛。")
    lines.append("- 长期：pre-commit 钩子拒绝新增未文档化的公共函数。")

    out = "\n".join(lines) + "\n"
    if args.stdout:
        sys.stdout.write(out)
    else:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(out, encoding="utf-8")
        print(f"wrote {REPORT.relative_to(ROOT)} ({len(lines)} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
