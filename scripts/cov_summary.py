"""从 coverage.xml 生成按覆盖率分组的摘要。"""
import xml.etree.ElementTree as ET
from collections import defaultdict

xml_path = r'e:\2026Workplace\Code\Lab-Analysis\coverage.xml'
tree = ET.parse(xml_path)
root = tree.getroot()

buckets = defaultdict(list)
total_stmts = total_miss = 0

for cls in root.findall('.//class'):
    name = cls.get('filename').replace('/', '\\')
    rate = float(cls.get('line-rate', 0))
    stmts = int(cls.get('lines', {}).get('valid', 0)) if False else 0
    # 用 line 元素精确统计
    miss = 0
    hits = 0
    for line in cls.findall('lines/line'):
        h = int(line.get('hits', 0))
        if h > 0:
            hits += 1
        else:
            miss += 1
    total = hits + miss
    total_stmts += total
    total_miss += miss
    cov_pct = 100.0 if total == 0 else 100.0 * hits / total
    short = name.split('\\')[-1] if '\\' in name else name
    if cov_pct >= 70:
        bucket = 'high'
    elif cov_pct >= 30:
        bucket = 'mid'
    elif cov_pct > 0:
        bucket = 'low'
    else:
        bucket = 'zero'
    buckets[bucket].append((cov_pct, short, hits, miss))

overall = 100.0 * (total_stmts - total_miss) / total_stmts if total_stmts else 0
print(f'=== Coverage summary: {total_stmts - total_miss}/{total_stmts} = {overall:.1f}% ===\n')

for label in ('high', 'mid', 'low', 'zero'):
    if not buckets[label]:
        continue
    print(f'[{label.upper()}]  ({len(buckets[label])} modules)')
    for pct, name, h, m in sorted(buckets[label]):
        print(f'  {pct:>5.1f}%   {h:>4}/{h+m:<4}  {name}')
    print()