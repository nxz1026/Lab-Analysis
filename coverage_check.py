import re
import subprocess
import sys

out = subprocess.run(
    [sys.executable, "-m", "coverage", "report"], capture_output=True, text=True
).stdout
rows = []
for line in out.splitlines():
    m = re.match(r"(lab_analysis\S+)\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)%", line)
    if m:
        rows.append((int(m.group(2)), line.strip()))
print(f"TOTAL rows: {len(rows)}")
print("\n=== 0% 覆盖率模块 ===")
zeros = [r for r in rows if r[0] == 0]
for _, ln in zeros:
    print(f"  {ln}")
print("\n=== Top 5 最低覆盖率 (含非 0%) ===")
for pct, ln in sorted(rows)[:5]:
    print(f"  {pct:3d}%  {ln}")
print("\n=== 全局汇总 ===")
total = re.search(r"TOTAL\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)%", out)
if total:
    print(f"  总覆盖率: {total.group(1)}%")
