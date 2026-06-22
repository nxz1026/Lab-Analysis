#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_analyzer.py — 统计分析入口（薄 shim，代理到 lab_analysis.analysis 子包）

用法：python -m lab_analysis.data_analyzer --id-card <脱敏ID>

自 2026-06 重构后，核心逻辑已迁至 ``lab_analysis/analysis/`` 子包。
此文件保留为向后兼容的入口。
"""

from lab_analysis.analysis.run import run

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="统计分析：生成分析结果 + 7 张图表")
    parser.add_argument("--id-card", required=True, help="脱敏ID(由 pipeline 传入)")
    args = parser.parse_args()
    run(args.id_card)
