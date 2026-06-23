"""批量 print() → logger 替换(整行单 print 严格模式)。

策略:
- AST 安全解析,只动"整行只有一个 print(...)"的情况
- 跨行 print(ast.Call.end_lineno > lineno)→ 跳过
- 该行有除 print 外的其他内容(同一行多语句)→ 跳过
- 替换后立刻 ast.parse 校验,语法坏掉回滚
- 已有 `logger` 变量 → 复用
- 没 `logger` → 在 import 区后插入 `from . import _log` + `logger = _log.get_logger(__name__)`
- 顶层 print() → logger.info()
- 消息含 "error/fail/❌" → logger.error
- 消息含 "warn/skipped/⚠" → logger.warning

使用:
    python scripts/print_to_logger.py --dry-run lab_analysis/
    python scripts/print_to_logger.py lab_analysis/
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re

ERROR_KEYWORDS = (
    "error",
    "fail",
    "exception",
    "traceback",
    "critical",
    "fatal",
    "❌",
    "错误",
    "失败",
)
WARN_KEYWORDS = ("warn", "warning", "skipped", "skip", "deprecated", "⚠", "警告", "跳过", "缺失")


def _msg_level(msg: str) -> str:
    low = msg.lower()
    if any(k.lower() in low for k in ERROR_KEYWORDS):
        return "error"
    if any(k.lower() in low for k in WARN_KEYWORDS):
        return "warning"
    return "info"


def _set_pos(node: ast.AST, lineno: int = 1, col: int = 0) -> ast.AST:
    node.lineno = lineno
    node.col_offset = col
    for child in ast.iter_child_nodes(node):
        _set_pos(child, lineno, col)
    return node


def _has_logger_alias(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "logger":
                    return True
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "logger"
        ):
            return True
    return False


def _make_logger_setup(level: int) -> list[ast.stmt]:
    # ImportFrom 的 module="" + level=N 表示 from ..[N-1 dots].. import
    import_node = ast.ImportFrom(
        module="", names=[ast.alias(name="_log", asname=None)], level=level
    )
    assign_node = ast.Assign(
        targets=[ast.Name(id="logger", ctx=ast.Store())],
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="_log", ctx=ast.Load()), attr="get_logger", ctx=ast.Load()
            ),
            args=[ast.Name(id="__name__", ctx=ast.Load())],
            keywords=[],
        ),
    )
    return [_set_pos(import_node), _set_pos(assign_node)]


def _rel_import_level(path: pathlib.Path, package_root: str = "lab_analysis") -> int:
    """计算 from . import 的 level。

    - lab_analysis/foo.py                 -> level=1 (从 lab_analysis package)
    - lab_analysis/dspy_modules/foo.py    -> level=2 (从 lab_analysis.dspy_modules)
    """
    parts = path.parts
    try:
        idx = parts.index(package_root)
    except ValueError:
        return 1
    return len(parts) - idx - 1


def _literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _build_logger_call(call_node: ast.Call) -> str:
    """把 print(...) 转 logger.xxx(...)。Call 必须在单行。"""
    positional = call_node.args
    kwargs = {kw.arg: kw.value for kw in call_node.keywords if kw.arg in {"sep", "end"}}
    msg_text: str | None = None
    extra: list[ast.expr] = []
    if positional:
        first = positional[0]
        msg_text = _literal_str(first)
        if msg_text is None:
            extra.append(first)
        extra.extend(positional[1:])
    level = _msg_level(msg_text or "")

    parts: list[str] = []
    if msg_text is not None:
        parts.append(repr(msg_text))
    for a in extra:
        parts.append(ast.unparse(a))
    if "sep" in kwargs:
        parts.append(f"sep={ast.unparse(kwargs['sep'])}")
    if "end" in kwargs:
        parts.append(f"end={ast.unparse(kwargs['end'])}")

    return f"logger.{level}({', '.join(parts)})"


def transform_file(path: pathlib.Path, dry_run: bool) -> tuple[int, int, str]:
    """返回(替换数, 跳过数, 状态)。"""
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return 0, 0, f"PARSE-ERROR: {e}"

    # 收集整行单 print Call
    candidates: list[tuple[int, ast.Call]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ):
            continue
        # 必须单行
        if getattr(node, "end_lineno", node.lineno) != node.lineno:
            continue
        candidates.append((node.lineno, node))

    if not candidates:
        return 0, 0, "NO-PRINT"

    lines = src.splitlines(keepends=True)
    changed = 0
    skipped = 0
    # 从下到上替换,避免 lineno 偏移
    for lineno, call_node in sorted(candidates, key=lambda x: -x[0]):
        idx = lineno - 1
        raw = lines[idx]
        # 整行必须是 print(...),允许前导缩进
        # 去掉行尾换行做匹配
        body = raw.rstrip("\n").rstrip("\r")
        m = re.match(r"^(\s*)print\((.*)\)(\s*(?:#.*)?)$", body)
        if not m:
            skipped += 1
            continue
        indent, _inner, _trail = m.group(1), m.group(2), m.group(3)
        # 用 ast.unparse 重新生成整个 call,避免解析源码出错
        try:
            inner_src = _build_logger_call(call_node)
        except Exception:
            skipped += 1
            continue
        # 行尾加回换行
        lines[idx] = indent + inner_src + "\n"
        changed += 1

    if changed == 0:
        return 0, skipped, "ALL-SKIPPED"

    # 补 logger 变量(如果没有)
    if not _has_logger_alias(ast.parse("".join(lines))):
        # 找最后一个 import
        tree2 = ast.parse("".join(lines))
        last_import = 0
        for node in tree2.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                last_import = max(last_import, getattr(node, "end_lineno", node.lineno))
        setup = _make_logger_setup(_rel_import_level(path))
        setup_lines = [ast.unparse(s) + "\n" for s in setup]
        if last_import == 0:
            lines = setup_lines + lines
        else:
            lines = lines[:last_import] + setup_lines + lines[last_import:]

    new_src = "".join(lines)
    # 语法回环验证
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        return 0, skipped, f"VERIFY-FAIL: {e}"

    if not dry_run:
        path.write_text(new_src, encoding="utf-8")
    return changed, skipped, "OK"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    targets: list[pathlib.Path] = []
    for p in args.paths:
        pp = pathlib.Path(p)
        if pp.is_dir():
            targets.extend(
                q for q in pp.rglob("*.py") if "__pycache__" not in str(q) and q.name != "_log.py"
            )
        elif pp.suffix == ".py":
            targets.append(pp)

    total_changed = 0
    total_skipped = 0
    problems: list[str] = []
    for f in sorted(targets):
        try:
            ch, sk, status = transform_file(f, args.dry_run)
        except Exception as e:
            problems.append(f"{f}: {e}")
            continue
        if status not in ("OK", "NO-PRINT", "ALL-SKIPPED"):
            problems.append(f"{f}: {status}")
            continue
        if ch > 0 or sk > 0:
            tag = "WOULD-CHANGE" if args.dry_run else "CHANGED"
            print(f"  {tag:13s} chg={ch:3d} skip={sk:3d}  {f}")
            total_changed += ch
            total_skipped += sk

    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(f"\n{mode}: replaced={total_changed} skipped={total_skipped} across {len(targets)} files")
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print(f"  {p}")


if __name__ == "__main__":
    main()
