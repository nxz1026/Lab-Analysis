#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地文件组织脚本 — Pipeline 最终步骤

在本地按照飞书云盘的结构创建文件夹并复制分析结果

本地文件结构（模拟飞书云盘）：
{WORK_ROOT}/local_upload/
└── {今天日期}/          ← 当天年月日文件夹
    ├── 原始数据/          ← 检验+影像原始数据
    ├── 文献参考/          ← 文献检索结果
    ├── 中间结果/          ← 循证解读
    ├── 统计结果/          ← 统计分析图表
    └── final_integrated_report.md    ← 最终综合报告（根目录）
"""

import os
import argparse
import shutil
from pathlib import Path
from datetime import date

# ============ 配置 ============
from dotenv import load_dotenv
load_dotenv()

TODAY = date.today().strftime("%Y-%m-%d")
WORK_ROOT = Path(os.environ.get("WORK_ROOT", str(Path(__file__).parent.parent)))
LOCAL_UPLOAD_ROOT = WORK_ROOT / "local_upload"  # 本地上传根目录


def build_paths(patient_id: str):
    """根据 patient_id 和 ANALYSIS_TS 环境变量构建路径字典。

    路径结构：data/{patient_id}/{ANALYSIS_TS}/
    - patient_id: de-identified ID（如 846552421134373347）
    - ANALYSIS_TS: 仅时间戳（如 20260503_030142），无 de-id 前缀
    """
    raw_ts = os.environ.get("ANALYSIS_TS", patient_id)
    # ANALYSIS_TS 可能是纯时间戳（run_analysis.py 传入），也可能是 "deid/ts"（直接传参）
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts  # fallback 为 patient_id
    data_dir = WORK_ROOT / "data" / patient_id / ts
    return {
        "data": data_dir,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="本地文件组织 - Pipeline最终步骤")
    parser.add_argument("--id-card", required=True, help="脱敏ID(由 pipeline 传入)")
    return parser.parse_args()


# 四个子文件夹名称（按此顺序创建）
SUBFOLDER_NAMES = ["原始数据", "文献参考", "中间结果", "统计结果"]


def create_local_folder(folder_path: Path) -> bool:
    """在本地创建文件夹"""
    try:
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"  [成功] 创建文件夹: {folder_path}")
        return True
    except Exception as e:
        print(f"  [失败] 创建文件夹失败: {folder_path} - {e}")
        return False


def copy_file_to_folder(local_path: Path, target_folder: Path, rename: str = None) -> bool:
    """复制文件到目标文件夹"""
    if not local_path.exists():
        print(f"  [警告] 文件不存在，跳过: {local_path}")
        return False
    
    target_name = rename or local_path.name
    target_path = target_folder / target_name
    
    try:
        shutil.copy2(local_path, target_path)
        size = target_path.stat().st_size
        print(f"  [成功] {target_name} → {size} bytes")
        return True
    except Exception as e:
        print(f"  [失败] 复制失败: {local_path} - {e}")
        return False


def main():
    args = parse_args()
    patient_id = args.id_card
    paths = build_paths(patient_id)
    data_dir = paths["data"]

    print(f"\n{'='*60}")
    print(f"[日期] 当天日期: {TODAY}")
    print(f"[患者] 病人ID: {patient_id}")
    print(f"[目录] 本地上传根目录: {LOCAL_UPLOAD_ROOT}")
    print(f"{'='*60}\n")

    # 动态构建文件清单，文件名加病人ID前缀
    analyzed_dir = data_dir / "02_analyzed"
    lit_dir = data_dir / "03_literature"
    reports_dir = data_dir / "04_reports"
    figures_dir = analyzed_dir / "figures"
    
    upload_map = [
        # --- 原始数据 ---
        (analyzed_dir / "lab_metrics.csv",                  "原始数据",  None),
        (analyzed_dir / "lab_metrics.json",                 "原始数据",  None),
        # --- 文献参考 ---
        (lit_dir / "literature_results.md",                 "文献参考",  None),
        # --- 中间结果 ---
        (lit_dir / "literature_interpretation.md",          "中间结果",  None),
        (lit_dir / "mri_report_check_results.md",            "中间结果",  None),
        (analyzed_dir / "analysis_results_report.md",       "中间结果",  None),
        # --- 统计结果 ---
        (figures_dir / "fig_01_trend_regression.png",       "统计结果",  None),
        (figures_dir / "fig_02_correlation_heatmap.png",     "统计结果",  None),
        (figures_dir / "fig_03_inflammation_status.png",     "统计结果",  None),
        (figures_dir / "fig_04_abnormal_indicators.png",     "统计结果",  None),
        (figures_dir / "fig_05_moving_average.png",         "统计结果",  None),
        (figures_dir / "fig_06_cv_stability.png",           "统计结果",  None),
        (figures_dir / "fig_07_zscore_distribution.png",     "统计结果",  None),
        # --- 最终报告（当天根目录）---
        (reports_dir / "final_integrated_report.md",         None,        None),
    ]
    
    # Step 1: 创建当天日期文件夹
    day_folder = LOCAL_UPLOAD_ROOT / TODAY
    print(f"① 创建当天文件夹: {day_folder}")
    if not create_local_folder(day_folder):
        print("  [失败] 当天文件夹创建失败，退出")
        return
    print(f"  [成功] 当天文件夹: {day_folder}")

    # Step 2: 创建四个子文件夹
    subfolders = {}
    print(f"\n② 创建四个子文件夹")
    for sf_name in SUBFOLDER_NAMES:
        sf_path = day_folder / sf_name
        if create_local_folder(sf_path):
            subfolders[sf_name] = sf_path
        else:
            print(f"  [失败] {sf_name} 创建失败")

    # Step 3: 复制所有文件
    print(f"\n③ 复制所有文件")
    copied_count = 0
    skipped_count = 0
    for local_path, subfolder, rename in upload_map:
        if not local_path.exists():
            print(f"  [警告] 文件不存在，跳过: {local_path}")
            skipped_count += 1
            continue

        if subfolder is None:
            # 根目录
            target_folder = day_folder
        else:
            target_folder = subfolders.get(subfolder)
            if not target_folder:
                print(f"  [警告] 子文件夹 {subfolder} 未创建成功，跳过: {local_path}")
                skipped_count += 1
                continue

        if copy_file_to_folder(local_path, target_folder, rename):
            copied_count += 1
        else:
            skipped_count += 1

    # Step 4: 合并 DSPy prompts 目录到 中间结果/dspy_prompts/
    print(f"\n④ 合并 DSPy prompts 目录")
    dspy_target = subfolders.get("中间结果") / "dspy_prompts"
    dspy_target.mkdir(parents=True, exist_ok=True)
    dspy_sources = [
        lit_dir / "dspy_prompts",                       # 03_literature/dspy_prompts
        reports_dir / "dspy_prompts",                   # 04_reports/dspy_prompts
        WORK_ROOT / "data" / "mri_dspy_prompts",         # 散落: mri_analyzer 旧产物
        WORK_ROOT / "data" / "lab_extractor_dspy_prompts",  # 散落: lab_data_extractor 旧产物
    ]
    dspy_merged = 0
    for src in dspy_sources:
        if not src.exists() or not src.is_dir():
            continue
        for item in src.iterdir():
            dest = dspy_target / item.name
            try:
                if item.is_file():
                    shutil.copy2(item, dest)
                elif item.is_dir():
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
                dspy_merged += 1
                print(f"  [成功] {src.name}/{item.name} -> 中间结果/dspy_prompts/{item.name}")
            except Exception as e:
                print(f"  [失败] 合并 {item.name} 失败: {e}")
    if dspy_merged == 0:
        print("  [警告] 未找到任何 DSPy prompts 源目录")
    else:
        print(f"  [完成] 共合并 {dspy_merged} 个 DSPy 产物")

    print(f"\n{'='*60}")
    print(f"[完成] 全部完成！")
    print(f"   [成功] 成功复制: {copied_count} 个文件")
    print(f"   [DSPy] 合并: {dspy_merged} 个 DSPy 产物")
    print(f"   [警告] 跳过: {skipped_count} 个文件")
    print(f"   [目录] 本地路径: {day_folder}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
