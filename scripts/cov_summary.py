"""从 coverage.xml 生成按覆盖率分组的摘要。

用法: python scripts/cov_summary.py [coverage.xml 路径]
默认取仓库根目录下的 coverage.xml (由 pytest --cov-report=xml 生成)。
"""

import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

# S314: 解析的是本仓库 pytest-cov 自己生成的 coverage.xml, 不是外部/不可信输入。
# 换 defusedxml 需要新增依赖, 对一个本地摘要脚本不划算。
_REPO_ROOT = Path(__file__).resolve().parent.parent
xml_path = sys.argv[1] if len(sys.argv) > 1 else str(_REPO_ROOT / "coverage.xml")

if not Path(xml_path).is_file():
    print(f"[错误] 找不到 coverage.xml: {xml_path}")
    print("       先跑: python -m pytest --cov=lab_analysis --cov-report=xml:coverage.xml")
    raise SystemExit(1)

tree = ET.parse(xml_path)  # noqa: S314
root = tree.getroot()

buckets = defaultdict(list)
total_stmts = total_miss = 0

for cls in root.findall(".//class"):
    name = cls.get("filename").replace("/", "\\")
    rate = float(cls.get("line-rate", 0))
    # 用 line 元素精确统计
    miss = 0
    hits = 0
    for line in cls.findall("lines/line"):
        h = int(line.get("hits", 0))
        if h > 0:
            hits += 1
        else:
            miss += 1
    total = hits + miss
    total_stmts += total
    total_miss += miss
    cov_pct = 100.0 if total == 0 else 100.0 * hits / total
    short = name.split("\\")[-1] if "\\" in name else name
    if cov_pct >= 70:
        bucket = "high"
    elif cov_pct >= 30:
        bucket = "mid"
    elif cov_pct > 0:
        bucket = "low"
    else:
        bucket = "zero"
    buckets[bucket].append((cov_pct, short, hits, miss))

overall = 100.0 * (total_stmts - total_miss) / total_stmts if total_stmts else 0
print(f"=== Coverage summary: {total_stmts - total_miss}/{total_stmts} = {overall:.1f}% ===\n")

for label in ("high", "mid", "low", "zero"):
    if not buckets[label]:
        continue
    print(f"[{label.upper()}]  ({len(buckets[label])} modules)")
    for pct, name, h, m in sorted(buckets[label]):
        print(f"  {pct:>5.1f}%   {h:>4}/{h + m:<4}  {name}")
    print()
