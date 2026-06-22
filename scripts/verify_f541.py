#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 autofix_f541.py 没有占位符误判 — 抽查所有行"""

import re
import subprocess
import sys

# 跑脚本输出 dry-run
result = subprocess.run(
    [
        sys.executable,
        "scripts/autofix_f541.py",
        "--root",
        "lab_analysis",
        "--also",
        "tests",
        "--sample",
        "9999",
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",
)
out = result.stdout

# 抽所有 L\d+ 行
sample_lines = []
for line in out.split("\n"):
    m = re.match(r"\s+L\d+:\s*(.*)$", line)
    if m:
        sample_lines.append(m.group(1))

print(f"Total sample lines: {len(sample_lines)}")

# 验证：每个样本行中, f-string 的内容是否有 {
leak_count = 0
for line in sample_lines:
    # 找 f"..." 或 f'...'
    for m in re.finditer(r"""f(['"])((?:\\.|(?!\1).)*?)\1""", line):
        content = m.group(2)
        if "{" in content or "}" in content:
            leak_count += 1
            print(f"LEAK: {line[:120]}")

print(f"Placeholder leak count: {leak_count}")
print("---")
if leak_count == 0:
    print("PASS: 所有 dry-run 标记的 F541 都是真无占位符")
else:
    print("FAIL: 有占位符误判, 需要修")
