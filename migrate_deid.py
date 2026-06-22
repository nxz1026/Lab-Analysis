#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_deid.py — 一次性脱敏算法迁移脚本（默认 dry-run，需显式 --apply 才执行）

背景
====
旧的脱敏算法是简陋的数字偏移 (d+3)%10：身份证号 513229198801040014 → deid 846552421134373347。
新算法是确定性 AES-256-GCM（见 lab_analysis/patient_id.py）。
切换后，同一身份证号会产出完全不同的 deid，导致旧目录：

    raw/patient_846552421134373347/   ← 检验图片 / DICOM / 报告
    data/846552421134373347/           ← 历次分析产物

会变成「孤儿目录」（新运行会落到新 deid 目录下）。

本脚本的作用
============
读取旧的明文映射文件 .hermes/patient_mapping.json（格式 {旧deid: 原始身份证号}），
对每个原始身份证号用新算法 encode() 计算新 deid，把孤儿目录重命名为新 deid 目录。

用法
====
    # 1) 先 dry-run 预览（默认行为，安全，不改动任何文件）
    python migrate_deid.py

    # 2) 确认无误后执行重命名
    python migrate_deid.py --apply

    # 3) 自定义 WORK_ROOT（默认读取环境变量或当前目录）
    python migrate_deid.py --apply --work-root E:/2026Workplace/Code/Lab-Analysis

迁移完成后会询问是否删除旧明文映射文件（含 PHI，建议删除）。

注意
====
- 必须先安装新依赖 cryptography（已加入 pyproject.toml）
- 必须存在 .hermes/master.key（首次运行新 pipeline 时自动生成），否则无法计算新 deid
- 强烈建议先 git 提交当前状态 + 备份 raw/ 和 data/ 后再执行 --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def migrate(work_root: Path, apply: bool) -> int:
    mapping_file = work_root / ".hermes" / "patient_mapping.json"
    if not mapping_file.is_file():
        print(f"[INFO] 未找到旧映射文件: {mapping_file}")
        print("       无需迁移（可能已经迁移过，或没有旧数据）。")
        return 0

    print(f"[INFO] 读取旧明文映射: {mapping_file}")
    mapping = json.loads(mapping_file.read_text(encoding="utf-8"))
    if not isinstance(mapping, dict) or not mapping:
        print("[ERROR] 映射文件格式不正确（应为 {{旧deid: 原始身份证号}}）")
        return 1

    # 延迟导入，避免在 dry-run 阶段就要求生成 master.key
    from lab_analysis.patient_id import encode

    mode = "APPLY（执行重命名）" if apply else "DRY-RUN（仅预览，不改动）"
    print(f"\n[MODE] {mode}\n")
    print(f"{'旧 deid':<28} {'原始身份证号':<22} {'新 deid':<48} {'待迁移目录'}")
    print("-" * 130)

    migrated = 0
    skipped = 0
    pending_deletes: list[Path] = []

    for old_deid, id_card in mapping.items():
        if not id_card:
            print(f"[WARN] 映射项 {old_deid!r} 缺少原始身份证号，跳过")
            skipped += 1
            continue
        new_deid = encode(id_card)
        same = "（同）" if new_deid == old_deid else ""

        # 扫描 raw/patient_{old} 和 data/{old}
        targets: list[tuple[Path, Path]] = []
        for base in (work_root / "raw", work_root / "data"):
            if not base.is_dir():
                continue
            if base.name == "raw":
                old_dir = base / f"patient_{old_deid}"
                new_dir = base / f"patient_{new_deid}"
            else:
                old_dir = base / old_deid
                new_dir = base / new_deid
            if old_dir.exists():
                targets.append((old_dir, new_dir))

        targets_str = ", ".join(str(t[0].relative_to(work_root)) for t in targets) or "（无）"
        print(f"{old_deid:<28} {id_card:<22} {new_deid:<48} {targets_str} {same}")

        if new_deid == old_deid:
            skipped += 1
            continue

        for old_dir, new_dir in targets:
            if new_dir.exists():
                print(f"  [WARN] 目标已存在，跳过: {new_dir}（请人工合并）")
                skipped += 1
                continue
            if apply:
                try:
                    old_dir.rename(new_dir)
                    print(f"  [OK] {old_dir.name} -> {new_dir.name}")
                    migrated += 1
                except OSError as e:
                    print(f"  [FAIL] 重命名失败 {old_dir}: {e}")
                    return 1
        pending_deletes.append(mapping_file)

    print("\n" + "=" * 60)
    print(f"迁移完成: {migrated} 个目录重命名, {skipped} 个跳过")
    if not apply:
        print("\n[提示] 这是 dry-run。确认无误后执行: python migrate_deid.py --apply")
    else:
        print("\n[提示] 重命名已完成。")
        # 提示删除明文映射文件（含 PHI）
        if mapping_file in pending_deletes:
            try:
                ans = (
                    input(
                        "\n是否删除旧明文映射文件 .hermes/patient_mapping.json？(含 PHI, 推荐 y) [y/N]: "
                    )
                    .strip()
                    .lower()
                )
            except (EOFError, KeyboardInterrupt):
                ans = ""
            if ans == "y":
                mapping_file.unlink()
                print(f"[OK] 已删除: {mapping_file}")
            else:
                print(f"[INFO] 保留旧映射文件: {mapping_file}（建议尽快手动删除）")
    print("=" * 60)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="脱敏算法迁移：旧 deid 目录 → 新 AES-GCM deid 目录"
    )
    parser.add_argument("--apply", action="store_true", help="实际执行重命名（默认 dry-run）")
    parser.add_argument(
        "--work-root",
        type=Path,
        default=None,
        help="项目根目录（默认读取环境变量 WORK_ROOT 或当前目录）",
    )
    args = parser.parse_args()

    work_root = args.work_root or Path(__import__("os").environ.get("WORK_ROOT", Path.cwd()))
    if not (work_root / "pyproject.toml").is_file():
        print(f"[ERROR] {work_root} 不是项目根目录（未找到 pyproject.toml）")
        return 1
    return migrate(work_root, apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
