#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""autofix_f541.py — 一键去除无占位符的 f-string 前缀

F541 (f-string-without-any-placeholder): 纯噪音，Py3.12+ DeprecationWarning, 运行无影响。
扫描范围: lab_analysis/ + tests/
策略：
- 字符级扫描，单行 f-string（多行 f-string 风险较高，跳过）
- 找形如 f"..." 或 f'...' 且内部不含 { 或 }
- 排除 raw f-string (rf/fr/RF/fR)
- dry-run 报告，仅 --apply 时落盘
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def scan_line(line: str) -> list[tuple[int, int, str, str]]:
    """返回该行所有 F541 f-string 范围 (start, end, prefix, quote)。

    字符级扫描，处理转义。
    """
    n = len(line)
    out = []
    i = 0
    while i < n:
        c = line[i]
        if c in ('f', 'F'):
            # 前一字符检查: 不能是字母数字下划线或点 (即 f 必须是字符串前缀开头)
            if i > 0 and (line[i - 1].isalnum() or line[i - 1] == '_' or line[i - 1] == '.'):
                i += 1
                continue
            # 下一字符必须是 " 或 '
            if i + 1 >= n or line[i + 1] not in ('"', "'"):
                i += 1
                continue
            quote = line[i + 1]
            # 三引号跨行 f-string (f\"\"\" / f''') — 跳过, 防止误判
            if i + 2 < n and line[i + 2] == quote:
                # 找到本行的结束三引号位置(若有); 若本行未结束, 跳到行末
                j = i + 3
                while j < n - 1:
                    if line[j] == quote and line[j + 1] == quote and line[j + 2] == quote:
                        j += 3
                        break
                    j += 1
                else:
                    j = n  # 跨行, 跳到行末
                i = j
                continue
            # 找配对的关闭引号, 处理 \"
            j = i + 2
            content_chars = []
            while j < n:
                ch = line[j]
                if ch == '\\' and j + 1 < n:
                    content_chars.append(ch)
                    content_chars.append(line[j + 1])
                    j += 2
                    continue
                if ch == quote:
                    break
                content_chars.append(ch)
                j += 1
            if j >= n:
                # 字符串未闭合, 跳过
                i += 1
                continue
            content = ''.join(content_chars)
            # 含占位符就不是 F541
            if '{' not in content and '}' not in content:
                # start..j (含关闭引号) 是整段
                out.append((i, j + 1, c, quote))
            i = j + 1
            continue
        i += 1
    return out


def fix_file(path: Path) -> tuple[int, str]:
    """返回 (修复行数, 修改后内容)。"""
    original = path.read_text(encoding='utf-8')
    lines = original.splitlines(keepends=True)
    fixed_count = 0
    new_lines = []
    for line in lines:
        # 跳过纯注释行
        stripped = line.lstrip()
        if stripped.startswith('#'):
            new_lines.append(line)
            continue
        spans = scan_line(line)
        if not spans:
            new_lines.append(line)
            continue
        # 从后往前替换, 避免索引错位
        new_line = line
        for start, end, prefix, quote in reversed(spans):
            match_str = new_line[start:end]
            # match_str 形如 f"..." 或 f'...', 去 f 前缀
            inner = match_str[1:]
            new_line = new_line[:start] + inner + new_line[end:]
        fixed_count += 1
        new_lines.append(new_line)
    if fixed_count == 0:
        return 0, original
    return fixed_count, ''.join(new_lines)


def main():
    ap = argparse.ArgumentParser(description='Auto-fix F541 (f-string without placeholders)')
    ap.add_argument('--root', default='lab_analysis', help='扫描根目录')
    ap.add_argument('--apply', action='store_true', help='落盘, 默认只 dry-run')
    ap.add_argument('--also', nargs='*', default=['tests'], help='额外扫描目录')
    ap.add_argument('--sample', type=int, default=8, help='每文件最多打印多少样本')
    args = ap.parse_args()

    roots = [Path(args.root)] + [Path(p) for p in args.also]
    total_files = 0
    total_lines = 0
    sample_printed = 0
    for root in roots:
        if not root.exists():
            print(f'[SKIP] {root} not found', file=sys.stderr)
            continue
        for py in sorted(root.rglob('*.py')):
            spans = []
            text = py.read_text(encoding='utf-8')
            for ln_no, line in enumerate(text.splitlines(), 1):
                s = scan_line(line)
                if s and not line.lstrip().startswith('#'):
                    spans.append((ln_no, line.strip()))
            if not spans:
                continue
            n_fixed, new_content = fix_file(py)
            total_files += 1
            total_lines += n_fixed
            mode = 'FIXED' if args.apply else 'DRY-RUN'
            print(f'[{mode}] {py}  ({n_fixed} lines)')
            for ln_no, content in spans[:args.sample]:
                if sample_printed < args.sample * 4:
                    print(f'    L{ln_no}: {content[:90]}')
                    sample_printed += 1
            if args.apply:
                py.write_text(new_content, encoding='utf-8')

    print('---')
    print(f'Total: {total_files} files, {total_lines} lines')
    if not args.apply:
        print('(dry-run, no file changed; rerun with --apply to commit)')


if __name__ == '__main__':
    main()