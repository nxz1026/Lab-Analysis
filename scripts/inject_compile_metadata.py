"""为已存在的 DSPy compiled JSON 注入 metadata (compiled_at / source_commit)。

背景:
    DSPy 的 ``compiled.save()`` 不会自动写编译时间戳,审计只能靠文件系统 mtime,
    在 git checkout / 复制时会被改写。本工具为 JSON 注入真实的 metadata,
    使审计能稳定判 STALE。

用法:
    # 注入所有 4 个 JSON
    python scripts/inject_compile_metadata.py --all

    # 注入单个
    python scripts/inject_compile_metadata.py --path models/dspy/mri_analyzer_compiled.json

    # dry-run (只看不写)
    python scripts/inject_compile_metadata.py --all --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models" / "dspy"
SRC_DIR = ROOT / "lab_analysis" / "dspy_modules"


def get_git_head() -> str:
    """获取当前 HEAD commit SHA (短 hash 7 位),失败返回 'unknown'."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
        return out.decode("utf-8").strip() or "unknown"
    except Exception:
        return "unknown"


def get_latest_src_mtime() -> float:
    """dspy_modules/ 下所有 .py 的最大 mtime (秒)."""
    latest = 0.0
    for p in SRC_DIR.glob("*.py"):
        latest = max(latest, p.stat().st_mtime)
    return latest


def inject_metadata(json_path: Path, *, dry_run: bool = False) -> dict:
    """为单个 compiled JSON 注入 metadata。

    写入字段:
        metadata.compiled_at:        ISO 时间 (取自 JSON 文件 mtime,这是最准确的 compile 时间估计)
        metadata.source_commit:      git HEAD short SHA
        metadata.latest_src_mtime:   dspy_modules/ 最新 mtime (ISO)
        metadata.injected_at:        本次注入时间 (ISO)
        metadata.injector_version:   工具版本

    Returns:
        注入结果 dict (含 before/after/stale 判断)
    """
    if not json_path.exists():
        return {"path": str(json_path), "error": "file not found"}

    # 备份 (非 dry-run)
    if not dry_run:
        bak = json_path.with_suffix(json_path.suffix + ".bak")
        if not bak.exists():
            shutil.copy2(json_path, bak)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    before = dict(data.get("metadata", {}))

    json_mtime = json_path.stat().st_mtime
    compiled_at_iso = datetime.fromtimestamp(json_mtime).isoformat(timespec="seconds")
    src_mtime = get_latest_src_mtime()
    src_mtime_iso = datetime.fromtimestamp(src_mtime).isoformat(timespec="seconds")
    head = get_git_head()
    now_iso = datetime.now().isoformat(timespec="seconds")

    new_meta = dict(before)  # 保留 DSPy 原有 metadata (dependency_versions 等)
    new_meta.update(
        {
            "compiled_at": compiled_at_iso,
            "source_commit": head,
            "latest_src_mtime": src_mtime_iso,
            "injected_at": now_iso,
            "injector_version": "1.0.0",
        }
    )
    data["metadata"] = new_meta

    # 判定: compiled_at 早于 latest_src_mtime 即 STALE
    is_stale = json_mtime < src_mtime

    if not dry_run:
        json_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {
        "path": str(json_path),
        "name": json_path.name,
        "before_metadata": before,
        "after_metadata": new_meta,
        "compiled_at": compiled_at_iso,
        "source_commit": head,
        "is_stale": is_stale,
        "dry_run": dry_run,
    }


def main():
    parser = argparse.ArgumentParser(description="为 DSPy compiled JSON 注入 metadata")
    parser.add_argument("--all", action="store_true", help="注入 models/dspy/ 下所有 JSON")
    parser.add_argument("--path", type=Path, help="注入单个 JSON")
    parser.add_argument("--dry-run", action="store_true", help="只显示不写")
    args = parser.parse_args()

    if not args.all and not args.path:
        parser.error("必须传 --all 或 --path")

    targets: list[Path] = []
    if args.all:
        targets = sorted(MODELS_DIR.glob("*_compiled.json"))
    if args.path:
        targets.append(args.path)

    if not targets:
        print("[错误] 没有找到目标 JSON")
        sys.exit(1)

    print("=" * 70)
    print(f"  注入 metadata @ {datetime.now():%Y-%m-%d %H:%M:%S}")
    print(f"  source_commit: {get_git_head()}")
    print(
        f"  dspy_modules/ 最新 mtime: {datetime.fromtimestamp(get_latest_src_mtime()):%Y-%m-%d %H:%M:%S}"
    )
    print("=" * 70)

    n_stale = 0
    n_ok = 0
    for p in targets:
        r = inject_metadata(p, dry_run=args.dry_run)
        if "error" in r:
            print(f"\n  [ERR] {r['path']}: {r['error']}")
            continue
        flag = "STALE" if r["is_stale"] else "OK"
        if r["is_stale"]:
            n_stale += 1
        else:
            n_ok += 1
        print(f"\n  [{flag:5s}] {r['name']}")
        print(f"    compiled_at:   {r['compiled_at']}")
        print(f"    source_commit: {r['source_commit']}")
        if args.dry_run:
            print("    (dry-run: 未写)")

    print("\n" + "=" * 70)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"  [完成] {len(targets)} JSON, STALE={n_stale}, OK={n_ok}{suffix}")
    print("=" * 70)


if __name__ == "__main__":
    main()
