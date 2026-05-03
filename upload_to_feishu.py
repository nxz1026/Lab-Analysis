#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书云盘上传脚本 — Pipeline 最终步骤
在「检验AI分析」下创建当天日期文件夹，建立三个子文件夹，上传所有分析结果

飞书云盘结构：
P1PIfbUOIll6Mrd9acnc81amnzh（父文件夹「检验AI分析」）
└── {今天日期}/          ← 当天年月日文件夹
    ├── 原始数据/          ← 检验+影像原始数据
    ├── 文献参考/          ← 文献检索结果
    ├── 中间结果/          ← 循证解读
    └── Final_report.md    ← 最终综合报告（根目录）
"""

import subprocess
import json
import os
import argparse
from pathlib import Path
from datetime import date

# ============ 配置 ============
TODAY = date.today().strftime("%Y-%m-%d")
BASE_DIR = Path("/root/wiki")


def build_paths(patient_id: str):
    """根据 patient_id 和 ANALYSIS_TS 环境变量构建路径字典。

    路径结构：data/{patient_id}/{ANALYSIS_TS}/
    - patient_id: de-identified ID（如 846552421134373347）
    - ANALYSIS_TS: 仅时间戳（如 20260503_030142），无 de-id 前缀
    """
    import os
    ts = os.environ.get("ANALYSIS_TS", patient_id)  # fallback 为 patient_id
    data_dir = BASE_DIR / "data" / patient_id / ts
    return {
        "data": data_dir,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="飞书上云 - Pipeline最终步骤")
    parser.add_argument("--patient-id", required=True, help="病人诊疗卡号")
    return parser.parse_args()


# 四个子文件夹名称（按此顺序创建）
SUBFOLDER_NAMES = ["原始数据", "文献参考", "中间结果", "统计结果"]

# 父文件夹 token（检验AI分析）
PARENT_FOLDER_TOKEN = "P1PIfbUOIll6Mrd9acnc81amnzh"


def run(cmd: list[str], cwd: str = None) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"  ❌ 命令失败: {' '.join(cmd)}")
        print(f"     stderr: {result.stderr[:200]}")
    return result.stdout.strip()


def run_json(cmd: list[str]) -> dict:
    """以 JSON 格式运行 lark-cli 命令，返回解析后的 dict"""
    # lark-cli 默认输出是 table/json，通过 --format json 强制指定
    if "--format" not in cmd:
        cmd = cmd + ["--format", "json"]
    out = run(cmd)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print(f"  ❌ JSON解析失败: {out[:200]}")
        return {}


def create_folder(name: str, folder_token: str) -> str | None:
    """创建文件夹，返回 folder_token（已存在也返回 token）"""
    # 先查列表，看是否已存在
    data = run_json([
        "lark-cli", "drive", "files", "list",
        "--params", json.dumps({"folder_token": folder_token}),
    ])
    for f in data.get("data", {}).get("files", []):
        if f.get("name") == name:
            print(f"  ℹ️  文件夹已存在: {name} → token={f['token']}")
            return f["token"]

    # 不存在则创建（使用 +create-folder 而非 files create_folder）
    out = run([
        "lark-cli", "drive", "+create-folder",
        "--name", name, "--folder-token", folder_token,
    ])
    try:
        data = json.loads(out)
        if data.get("ok"):
            token = data.get("data", {}).get("folder_token")
            if token:
                print(f"  ✅ 创建文件夹: {name} → token={token}")
                return token
        print(f"  ❌ 创建文件夹失败: {data.get('error', data.get('msg', ''))}")
    except json.JSONDecodeError:
        print(f"  ❌ JSON解析失败: {out[:200]}")
    return None


def lark_upload(local_path: str, folder_token: str, name: str = None) -> str | None:
    """上传单个文件，返回 file_token"""
    if not os.path.exists(local_path):
        print(f"  ⚠️  文件不存在，跳过: {local_path}")
        return None

    basename = name or os.path.basename(local_path)
    cmd = [
        "lark-cli", "drive", "+upload",
        "--file", f"./{os.path.basename(local_path)}",
        "--folder-token", folder_token,
    ]
    if name:
        cmd += ["--name", name]

    out = run(cmd, cwd=os.path.dirname(local_path))
    try:
        data = json.loads(out)
        if data.get("ok"):
            token = data["data"]["file_token"]
            size = data["data"]["size"]
            print(f"  ✅ {basename} → {size} bytes, token={token}")
            return token
        else:
            print(f"  ❌ 上传失败: {basename} — {data.get('error', {})}")
    except json.JSONDecodeError:
        print(f"  ❌ JSON解析失败: {out[:200]}")
    return None


def main():
    args = parse_args()
    patient_id = args.patient_id
    paths = build_paths(patient_id)
    data_dir = paths["data"]

    print(f"\n{'='*60}")
    print(f"📅 当天日期: {TODAY}")
    print(f"👤 病人ID: {patient_id}")
    print(f"📂 父文件夹: {PARENT_FOLDER_TOKEN}")
    print(f"{'='*60}\n")

    # 动态构建上传清单，文件名加病人ID前缀
    upload_map = [
        # --- 原始数据 ---
        (data_dir / "lab_metrics.csv",                       "原始数据",  None),
        (data_dir / "lab_metrics.json",                      "原始数据",  None),
        # --- 文献参考 ---
        (data_dir / "literature_results.md",               "文献参考",  None),
        # --- 中间结果 ---
        (data_dir / "literature_interpretation.md",   "中间结果",  None),
        (data_dir / "mri_report_check_results.md",         "中间结果",  None),
        # --- 统计结果 ---
        (data_dir / "analysis_results_report.md",            "中间结果",  None),
        (data_dir / "fig_01_trend_regression.png",            "统计结果",  None),
        (data_dir / "fig_02_correlation_heatmap.png",        "统计结果",  None),
        (data_dir / "fig_03_inflammation_status.png",        "统计结果",  None),
        (data_dir / "fig_04_abnormal_indicators.png",        "统计结果",  None),
        # --- 最终报告（当天根目录）---
        (data_dir / "final_integrated_report.md",             None,        None),
    ]
    print(f"① 创建当天文件夹: {TODAY}")
    day_folder_token = create_folder(TODAY, PARENT_FOLDER_TOKEN)
    if not day_folder_token:
        print("  ❌ 当天文件夹创建失败，退出")
        return
    print(f"  ✅ 当天文件夹: token={day_folder_token}")

    # Step 2: 创建四个子文件夹
    subfolders = {}
    print(f"\n② 创建四个子文件夹")
    for sf_name in SUBFOLDER_NAMES:
        token = create_folder(sf_name, day_folder_token)
        if token:
            subfolders[sf_name] = token
            print(f"  ✅ {sf_name} → token={token}")
        else:
            print(f"  ❌ {sf_name} 创建失败")

    # Step 3: 上传所有文件
    print(f"\n③ 上传所有文件")
    for local_path, subfolder, rename in upload_map:
        if not os.path.exists(local_path):
            print(f"  ⚠️  文件不存在，跳过: {local_path}")
            continue
        # 文件名保持原样（不加强制ID前缀）
        orig_name = os.path.basename(local_path)
        upload_name = orig_name
        if subfolder is None:
            # 根目录
            folder_tok = day_folder_token
        else:
            folder_tok = subfolders.get(subfolder)
            if not folder_tok:
                print(f"  ⚠️  子文件夹 {subfolder} 未创建成功，跳过: {local_path}")
                continue
        lark_upload(local_path, folder_tok, upload_name)

    print(f"\n{'='*60}")
    print(f"🎉 全部完成！当天文件夹: https://kcnnvmk14o6i.feishu.cn/drive/folder/{day_folder_token}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
