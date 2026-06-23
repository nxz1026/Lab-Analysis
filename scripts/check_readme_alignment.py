#!/usr/bin/env python3
"""check_readme_alignment.py — 检查 README.md (中) 与 README_en.md (英) 章节对齐。

输出:
- 中英各自章节列表
- 缺失章节清单 (英文缺哪些 / 中文缺哪些)
- 关键指标 (行数、字数)

用法:
    python scripts/check_readme_alignment.py
    python scripts/check_readme_alignment.py --check   # CI 模式：缺失即 exit 1
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CN = REPO / "README.md"
EN = REPO / "README_en.md"


def _extract_sections(path: Path) -> list[tuple[int, str]]:
    """提取所有 ## / ### 章节,返回 [(行号, 标题)]。"""
    sections: list[tuple[int, str]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if m:
            sections.append((i, m.group(2).strip()))
    return sections


def _normalize(title: str) -> str:
    """粗略归一化用于去重/匹配（去标点、空格、转小写）。"""
    s = re.sub(r"[^\w\s\u4e00-\u9fff]+", "", title)
    return s.lower().strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="README 中英章节对齐检查")
    parser.add_argument("--check", action="store_true", help="存在缺失时 exit 1")
    args = parser.parse_args()

    cn_sections = _extract_sections(CN)
    en_sections = _extract_sections(EN)
    cn_norm = {_normalize(t): t for _, t in cn_sections}
    en_norm = {_normalize(t): t for _, t in en_sections}

    print("\n=== README 对齐检查 ===")
    print(f"中文: {CN.name}  {len(cn_sections)} 章节  {(CN.stat().st_size / 1024):.1f} KB")
    print(f"英文: {EN.name}  {len(en_sections)} 章节  {(EN.stat().st_size / 1024):.1f} KB\n")

    print("=== 中文 README 章节 ===")
    for ln, t in cn_sections:
        marker = "  [缺英文]" if _normalize(t) not in en_norm else ""
        print(f"  {ln:4d}  {t}{marker}")

    print("\n=== 英文 README 章节 ===")
    for ln, t in en_sections:
        marker = "  [缺中文]" if _normalize(t) not in cn_norm else ""
        print(f"  {ln:4d}  {t}{marker}")

    missing_en = [t for _, t in cn_sections if _normalize(t) not in en_norm]
    missing_cn = [t for _, t in en_sections if _normalize(t) not in cn_norm]

    print("\n=== 对齐缺口 ===")
    if missing_en:
        print(f"\n[英文版需补充] ({len(missing_en)} 项):")
        for t in missing_en:
            print(f"  - {t}")
    if missing_cn:
        print(f"\n[中文版需补充] ({len(missing_cn)} 项):")
        for t in missing_cn:
            print(f"  - {t}")
    if not missing_en and not missing_cn:
        print("\n[OK] 中英章节完全对齐")

    if args.check and (missing_en or missing_cn):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
