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
from datetime import date

# ============ 配置 ============
TODAY = date.today().strftime("%Y-%m-%d")
BASE_DIR = "/root/wiki"
DATA_DIR = f"{BASE_DIR}/data"

# 父文件夹 token（检验AI分析）
PARENT_FOLDER_TOKEN = "P1PIfbUOIll6Mrd9acnc81amnzh"

# 四个子文件夹名称（按此顺序创建）
SUBFOLDER_NAMES = ["原始数据", "文献参考", "中间结果", "统计结果"]

# 上传后文件与子文件夹的映射
# 格式：(本地路径, 目标子文件夹名称, 重命名)
# 子文件夹为 None 表示上传到当天文件夹根目录
UPLOAD_MAP = [
    # --- 原始数据 ---
    (f"{DATA_DIR}/lab_metrics.csv",                  "原始数据",   None),
    (f"{DATA_DIR}/lab_metrics.json",                 "原始数据",   None),
    # --- 文献参考 ---
    (f"{DATA_DIR}/literature_results.json",          "文献参考",   None),
    # --- 中间结果 ---
    (f"{DATA_DIR}/literature_interpretation_report.md", "中间结果", None),   # 人类可读版
    (f"{DATA_DIR}/mri_report_check_results.json",     "中间结果",   None),   # 可能不存在（步骤⑤超时）
    (f"{BASE_DIR}/检验数据综合分析报告.md",           "中间结果",   None),   # 可能不存在
    # --- 统计结果 ---
    (f"{DATA_DIR}/analysis_results_report.md",         "统计结果",   None),   # 人类可读版
    (f"{DATA_DIR}/fig_01_trend_regression.png",      "统计结果",   None),
    (f"{DATA_DIR}/fig_02_correlation_heatmap.png",   "统计结果",   None),
    (f"{DATA_DIR}/fig_03_inflammation_status.png",   "统计结果",   None),
    (f"{DATA_DIR}/fig_04_abnormal_indicators.png",   "统计结果",   None),
    # --- 最终报告（当天根目录）---
    (f"{DATA_DIR}/final_integrated_report.md",        None,         "Final_report.md"),
]


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
    print(f"\n{'='*60}")
    print(f"📅 当天日期: {TODAY}")
    print(f"📂 父文件夹: {PARENT_FOLDER_TOKEN}")
    print(f"{'='*60}\n")

    # Step 1: 创建当天日期文件夹
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
    for local_path, subfolder, rename in UPLOAD_MAP:
        if subfolder is None:
            # 根目录
            folder_tok = day_folder_token
        else:
            folder_tok = subfolders.get(subfolder)
            if not folder_tok:
                print(f"  ⚠️  子文件夹 {subfolder} 未创建成功，跳过: {local_path}")
                continue
        lark_upload(local_path, folder_tok, rename)

    print(f"\n{'='*60}")
    print(f"🎉 全部完成！当天文件夹: https://kcnnvmk14o6i.feishu.cn/drive/folder/{day_folder_token}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
