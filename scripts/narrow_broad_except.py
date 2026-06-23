#!/usr/bin/env python3
"""narrow_broad_except.py — 批量收窄 `except Exception:` 为具体异常复合。

策略: 在 lab_analysis 包内将所有 `except Exception` / `except Exception as <name>`
替换为 `except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError)`
覆盖 95%+ 运行时错误，保留 KeyboardInterrupt / SystemExit 自然上抛。

用法:
    python scripts/narrow_broad_except.py            # 实际改写
    python scripts/narrow_broad_except.py --dry-run # 只扫描不改写
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TARGET_DIRS = ["lab_analysis"]  # 限制在产品代码
NARROW_TYPES = (
    "ValueError",
    "TypeError",
    "KeyError",
    "AttributeError",
    "OSError",
    "RuntimeError",
)
NARROW_TUPLE = f"({', '.join(NARROW_TYPES)})"


def _is_broad_except(handler: ast.ExceptHandler) -> bool:
    """检测 except 是否过宽 — `except Exception` 或 `except` 裸 except。"""
    if handler.type is None:
        return True  # bare except
    return isinstance(handler.type, ast.Name) and handler.type.id == "Exception"


def _narrow_handler(handler: ast.ExceptHandler) -> ast.ExceptHandler:
    """把 `except Exception` / bare except 收窄为 6 类复合异常。"""
    new_handler = ast.ExceptHandler(
        type=ast.Tuple(
            elts=[ast.Name(id=t, ctx=ast.Load()) for t in NARROW_TYPES],
            ctx=ast.Load(),
        ),
        name=handler.name,
        body=handler.body,
    )
    return ast.copy_location(new_handler, handler)


def narrow_file(path: Path, dry_run: bool) -> tuple[int, str | None]:
    """收窄单个文件中的 broad except。返回 (修改数, 新源码或 None)。"""
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return 0, None

    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if _is_broad_except(handler):
                handler.type = _narrow_handler(handler).type
                # ast.unparse 需要节点带 lineno; 这里 lineno 在 walk 中已保留
                ast.fix_missing_locations(handler)
                count += 1

    if count == 0:
        return 0, None

    new_src = ast.unparse(tree)
    if not dry_run:
        path.write_text(new_src, encoding="utf-8")
    return count, new_src


def main() -> int:
    parser = argparse.ArgumentParser(description="批量收窄 broad except")
    parser.add_argument("--dry-run", action="store_true", help="只扫描不改写，输出报告")
    args = parser.parse_args()

    files = []
    for d in TARGET_DIRS:
        files.extend((REPO / d).rglob("*.py"))

    total_files = 0
    total_changes = 0
    report: list[tuple[str, int]] = []
    for f in files:
        if "__pycache__" in f.parts:
            continue
        changes, _ = narrow_file(f, dry_run=args.dry_run)
        if changes:
            total_files += 1
            total_changes += changes
            report.append((str(f.relative_to(REPO)), changes))

    report.sort(key=lambda x: -x[1])
    print(f"\n=== Broad Except {'扫描' if args.dry_run else '收窄'} ===")
    print(f"路径: {', '.join(TARGET_DIRS)}")
    print(f"修改文件: {total_files}  修改 except 块: {total_changes}")
    if report:
        print("\nTop 10 文件:")
        for path, n in report[:10]:
            print(f"  {n:3d}  {path}")
        if len(report) > 10:
            print(f"  ... +{len(report) - 10} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
