import os
import shutil
import sys
import time
from pathlib import Path

ROOT = r"e:\2026Workplace\Code\Lab-Analysis\local_upload\2026-06-20"

t0 = time.perf_counter()

# --- 1. 删除前快照:列出将删除的全部文件 + 计算总大小 ---
files_to_delete = []
total_bytes = 0
for r, _, fs in os.walk(ROOT):
    for f in fs:
        # f 来自 os.walk 的 filenames, 保证是纯文件名 (无分隔符/无 ..), 可安全用 Path
        p = str(Path(r) / f)
        sz = Path(p).stat().st_size
        total_bytes += sz
        files_to_delete.append((p, sz))

print(f"[1] PRE-SNAPSHOT: {len(files_to_delete)} files, {total_bytes:,} bytes total")
print("    sample (first 5):")
for p, sz in files_to_delete[:5]:
    print(f"      {sz:>10} {p}")
print(f"    ... and {len(files_to_delete) - 5} more")

# --- 2. 删除前再确认 data/ 那边真源完整(防误删) ---
GUARD = [
    r"e:\2026Workplace\Code\Lab-Analysis\data\SYNTH-PATIENT-0001\20260620_175730\03_literature",
    r"e:\2026Workplace\Code\Lab-Analysis\data\SYNTH-PATIENT-0001\20260620_175730\04_reports",
    r"e:\2026Workplace\Code\Lab-Analysis\data\SYNTH-PATIENT-0001\20260620_175730\02_analyzed",
    r"e:\2026Workplace\Code\Lab-Analysis\data\mri_dspy_prompts",
]
guard_ok = all(Path(g).is_dir() for g in GUARD)
print(f"[2] GUARD check: data/ 真源目录完整 = {guard_ok}")
# 不用 assert: python -O / PYTHONOPTIMIZE 会把 assert 整条剥掉, 守卫随之失效
if not guard_ok:
    print("[中止] data/ 真源缺失,中止删除!", file=sys.stderr)
    sys.exit(1)

# --- 3. 执行删除 ---
shutil.rmtree(ROOT)
print(f"[3] rmtree done: {ROOT}")

# --- 4. 验证 ---
exists = Path(ROOT).exists()
# ROOT 为含分隔符的绝对目录路径, 故 dirname 非空, 与 str(Path(ROOT).parent) 等价 (不会退化成 ".")
parent = str(Path(ROOT).parent)
remaining = sorted(e.name for e in Path(parent).iterdir()) if Path(parent).exists() else []
print(f"[4] POST-VERIFY: {ROOT} exists = {exists}")
print(f"    local_upload/ remaining siblings: {remaining}")

# --- 5. data/ 真源未受影响 ---
data_root = r"e:\2026Workplace\Code\Lab-Analysis\data"
data_size = sum(Path(r, f).stat().st_size for r, _, fs in os.walk(data_root) for f in fs)
print(f"[5] data/ 仍完好,总大小 {data_size:,} bytes")

t1 = time.perf_counter()
print(f"[6] cleanup wall-time: {t1 - t0:.3f}s")
