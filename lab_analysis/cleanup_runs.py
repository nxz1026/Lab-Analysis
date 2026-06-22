"""cleanup_runs.py — Pipeline 产物清理工具

删除 ``data/<deid>/<ts>/`` 下超出保留数量的旧运行批次，释放磁盘空间。

用法:
    # 清理所有患者，保留最近 3 次运行
    python -m lab_analysis.cleanup_runs --keep-last 3

    # 只查看不动手
    python -m lab_analysis.cleanup_runs --keep-last 5 --dry-run

    # 只清理指定患者
    python -m lab_analysis.cleanup_runs --keep-last 2 --id-card <deid>
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
from pathlib import Path

from lab_analysis.utils import WORK_ROOT

_DATA_DIR = WORK_ROOT / "data"


def _get_dir_size(path: Path) -> int:
    """递归计算目录占用字节数。"""
    total = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            with contextlib.suppress(OSError):
                total += entry.stat().st_size
    return total


def _format_size(bytes_: int) -> str:
    """可读的文件大小字符串。"""
    if bytes_ < 1024:
        return f"{bytes_} B"
    elif bytes_ < 1024**2:
        return f"{bytes_ / 1024:.1f} KB"
    elif bytes_ < 1024**3:
        return f"{bytes_ / 1024**2:.1f} MB"
    return f"{bytes_ / 1024**3:.2f} GB"


def cleanup_patient(
    deid: str,
    keep_last: int = 3,
    dry_run: bool = False,
) -> dict:
    """清理单个患者目录下的旧运行产物。

    Args:
        deid: 脱敏患者 ID（对应 ``data/<deid>/``）。
        keep_last: 保留最近 N 次运行，默认 3。
        dry_run: True 时只打印不删除。

    Returns:
        ``{"deid": str, "kept": [str], "deleted": [{"ts": str, "size": int}], "freed_bytes": int}``
    """
    patient_dir = _DATA_DIR / deid
    result: dict = {
        "deid": deid,
        "kept": [],
        "deleted": [],
        "freed_bytes": 0,
    }

    if not patient_dir.is_dir():
        return result

    # 列出所有时间戳子目录，按名称降序排列（新 -> 旧）
    ts_dirs: list[Path] = sorted(
        [d for d in patient_dir.iterdir() if d.is_dir() and d.name[:8].isdigit()],
        key=lambda d: d.name,
        reverse=True,
    )

    if len(ts_dirs) <= keep_last:
        result["kept"] = [d.name for d in ts_dirs]
        return result

    keep_dirs = ts_dirs[:keep_last]
    delete_dirs = ts_dirs[keep_last:]

    result["kept"] = [d.name for d in keep_dirs]

    for d in delete_dirs:
        size = _get_dir_size(d)
        result["deleted"].append({"ts": d.name, "size": size})
        result["freed_bytes"] += size
        if dry_run:
            print(f"  [DRY-RUN] 将删除: {d.name} ({_format_size(size)})")
        else:
            try:
                shutil.rmtree(d)
                print(f"  [DELETE] {d.name} ({_format_size(size)})")
            except OSError as e:
                print(f"  [ERROR] 删除失败 {d.name}: {e}")

    return result


def cleanup_all(
    keep_last: int = 3, dry_run: bool = False, id_card: str | None = None
) -> list[dict]:
    """清理所有（或指定）患者的旧运行产物。

    Args:
        keep_last: 保留最近 N 次。
        dry_run: 只显示不删除。
        id_card: 可选，只清理该患者。

    Returns:
        每个患者的清理结果列表。
    """
    if not _DATA_DIR.is_dir():
        print(f"[WARNING] 数据目录不存在: {_DATA_DIR}")
        return []

    patient_dirs = [_DATA_DIR / id_card] if id_card else sorted(_DATA_DIR.iterdir())

    results = []
    for p in patient_dirs:
        if not p.is_dir():
            continue
        deid = p.name
        r = cleanup_patient(deid, keep_last=keep_last, dry_run=dry_run)
        if r["kept"] or r["deleted"]:
            results.append(r)

    return results


def print_summary(results: list[dict]):
    """打印清理摘要到控制台。"""
    if not results:
        print("\n  [OK] 无需要清理的旧产物")
        return

    total_freed = 0
    total_deleted = 0
    print("\n" + "=" * 60)
    print("  产物清理报告")
    print("=" * 60)
    for r in results:
        print(f"\n  患者 {r['deid']}:")
        print(f"    保留: {', '.join(r['kept'][:3])}{' ...' if len(r['kept']) > 3 else ''}")
        for d in r["deleted"]:
            print(f"    删除: {d['ts']} ({_format_size(d['size'])})")
        total_freed += r["freed_bytes"]
        total_deleted += len(r["deleted"])
        if r["freed_bytes"] > 0:
            print(f"    → 释放 {_format_size(r['freed_bytes'])}")
    print(f"\n  总计: 清理 {total_deleted} 个旧批次，释放 {_format_size(total_freed)}\n")


def _cli():
    parser = argparse.ArgumentParser(description="Pipeline 产物清理工具")
    parser.add_argument("--keep-last", type=int, default=3, help="保留最近 N 次运行（默认 3）")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不删除")
    parser.add_argument("--id-card", default=None, help="仅清理指定患者（不指定则清理全部）")
    parser.add_argument("--json", default=None, help="将清理结果保存为 JSON（可选）")
    args = parser.parse_args()

    results = cleanup_all(
        keep_last=args.keep_last,
        dry_run=args.dry_run,
        id_card=args.id_card,
    )
    print_summary(results)

    if args.json:
        Path(args.json).write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[OK] 清理报告已保存: {args.json}")


if __name__ == "__main__":
    _cli()
