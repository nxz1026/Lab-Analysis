#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地文件组织 + 飞书云盘上传脚本 — Pipeline 最终步骤

功能：
1. 在本地按照飞书云盘的结构创建文件夹并复制分析结果
2. 可选：自动上传到飞书云盘（需要配置FEISHU_APP_ID和FEISHU_APP_SECRET）

本地文件结构（模拟飞书云盘）：
{WIKI_ROOT}/local_upload/
└── {今天日期}/          ← 当天年月日文件夹
    ├── 原始数据/          ← 检验+影像原始数据
    ├── 文献参考/          ← 文献检索结果
    ├── 中间结果/          ← 循证解读
    ├── 统计结果/          ← 统计分析图表
    └── Final_report.md    ← 最终综合报告（根目录）
"""

import subprocess
import json
import os
import sys
import argparse
import shutil
import requests
from pathlib import Path
from datetime import date

# 设置标准输出编码为UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============ 配置 ============
import os
from dotenv import load_dotenv
load_dotenv()

TODAY = date.today().strftime("%Y-%m-%d")
WIKI_ROOT = Path(os.environ.get("WIKI_ROOT", str(Path.home() / "wiki")))
LOCAL_UPLOAD_ROOT = WIKI_ROOT / "local_upload"  # 本地上传根目录


def build_paths(patient_id: str):
    """根据 patient_id 和 ANALYSIS_TS 环境变量构建路径字典。

    路径结构：data/{patient_id}/{ANALYSIS_TS}/
    - patient_id: de-identified ID（如 846552421134373347）
    - ANALYSIS_TS: 仅时间戳（如 20260503_030142），无 de-id 前缀
    """
    raw_ts = os.environ.get("ANALYSIS_TS", patient_id)
    # ANALYSIS_TS 可能是纯时间戳（run_analysis.py 传入），也可能是 "deid/ts"（直接传参）
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts  # fallback 为 patient_id
    data_dir = WIKI_ROOT / "data" / patient_id / ts
    return {
        "data": data_dir,
        "analyzed": data_dir / "02_analyzed",
        "literature": data_dir / "03_literature",
        "reports": data_dir / "04_reports",
    }


def parse_args():
    parser = argparse.ArgumentParser(description="本地文件组织 + 飞书云盘上传 - Pipeline最终步骤")
    parser.add_argument("--patient-id", required=True, help="病人诊疗卡号")
    parser.add_argument("--upload-to-feishu", action="store_true", help="上传到飞书云盘（需要配置FEISHU_APP_ID和FEISHU_APP_SECRET）")
    return parser.parse_args()


# 四个子文件夹名称（按此顺序创建）
SUBFOLDER_NAMES = ["原始数据", "文献参考", "中间结果", "统计结果"]


# ============ 飞书 API 功能 ============

def check_lark_cli_installed() -> bool:
    """检查 lark-cli 是否已安装"""
    try:
        # Windows 上可能需要 shell=True
        result = subprocess.run(
            ["lark-cli", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=True  # Windows 兼容性
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        print(f"  [DEBUG] lark-cli 检测失败: {e}")
        return False


def upload_file_with_lark_cli(file_path: Path, folder_token: str) -> bool:
    """使用 lark-cli 上传文件到飞书云盘"""
    if not file_path.exists():
        print(f"  ⚠️  文件不存在，跳过: {file_path}")
        return False
    
    # 复制文件到当前目录（使用相对路径）
    temp_file = Path.cwd() / file_path.name
    try:
        shutil.copy2(file_path, temp_file)
        
        # 执行 lark-cli 上传命令
        cmd = [
            "lark-cli", "drive", "upload",
            "--file", str(temp_file),
            "--folder-token", folder_token
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            shell=True  # Windows 兼容性
        )
        
        if result.returncode == 0:
            size = file_path.stat().st_size
            print(f"  ✅ {file_path.name} → {size} bytes")
            return True
        else:
            print(f"  ❌ 上传失败: {file_path.name}")
            print(f"     Error: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ 上传异常: {file_path.name} - {e}")
        return False
    finally:
        # 删除临时文件
        if temp_file.exists():
            temp_file.unlink()


def get_feishu_token(app_id: str, app_secret: str) -> str:
    """获取飞书 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    response = requests.post(url, json={
        "app_id": app_id,
        "app_secret": app_secret
    })
    result = response.json()
    if result.get("code") == 0:
        return result["tenant_access_token"]
    else:
        raise Exception(f"获取token失败: {result}")


def find_folder_by_name(folder_name: str, access_token: str, parent_token: str = None) -> str:
    """根据文件夹名称查找folder_token"""
    url = "https://open.feishu.cn/open-apis/drive/v1/files"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    # 构建查询参数
    params = {
        "type": "folder"
    }
    if parent_token:
        params["folder_token"] = parent_token
    else:
        params["folder_token"] = "root"
    
    try:
        response = requests.get(url, headers=headers, params=params)
        result = response.json()
        
        if result.get("code") == 0:
            files = result.get("data", {}).get("files", [])
            for file in files:
                if file.get("name") == folder_name:
                    return file.get("token")
            return None
        else:
            print(f"  ⚠️  查找文件夹失败: Code={result.get('code')}, Msg={result.get('msg')}")
            return None
    except Exception as e:
        print(f"  ❌ 查找异常: {e}")
        return None


def create_folder_in_feishu(folder_name: str, parent_token: str, access_token: str) -> str:
    """在飞书云盘中创建文件夹，返回文件夹token"""
    # 使用正确的API端点和参数
    url = "https://open.feishu.cn/open-apis/drive/v1/files/create_folder"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # 构建payload，根目录时不传folder_token
    payload = {
        "name": folder_name
    }
    if parent_token and parent_token != "root":
        payload["folder_token"] = parent_token
    
    # 调试信息
    print(f"    [DEBUG] URL: {url}")
    print(f"    [DEBUG] Payload: {payload}")
    
    response = requests.post(url, headers=headers, json=payload)
    
    try:
        result = response.json()
        if result.get("code") == 0:
            return result["data"]["token"]
        else:
            print(f"  ⚠️  创建文件夹失败: {folder_name} - Code: {result.get('code')}, Msg: {result.get('msg')}")
            return None
    except Exception as e:
        print(f"  ❌ JSON解析失败: {e}")
        print(f"    Response text: {response.text[:200]}")
        return None


def upload_file_to_feishu(file_path: Path, folder_token: str, access_token: str) -> bool:
    """上传文件到飞书云盘指定文件夹"""
    if not file_path.exists():
        print(f"  ⚠️  文件不存在，跳过: {file_path}")
        return False
    
    url = "https://open.feishu.cn/open-apis/drive/v1/files/upload_all"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    with open(file_path, 'rb') as f:
        files = {
            "file": (file_path.name, f)
        }
        data = {
            "folder_token": folder_token,
            "file_name": file_path.name
        }
        
        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            result = response.json()
            if result.get("code") == 0:
                size = file_path.stat().st_size
                print(f"  ✅ {file_path.name} → {size} bytes")
                return True
            else:
                print(f"  ❌ 上传失败: {file_path.name} - {result.get('msg')}")
                return False
        except Exception as e:
            print(f"  ❌ 上传异常: {file_path.name} - {e}")
            return False


def create_local_folder(folder_path: Path) -> bool:
    """在本地创建文件夹"""
    try:
        folder_path.mkdir(parents=True, exist_ok=True)
        print(f"  ✅ 创建文件夹: {folder_path}")
        return True
    except Exception as e:
        print(f"  ❌ 创建文件夹失败: {folder_path} - {e}")
        return False


def copy_file_to_folder(local_path: Path, target_folder: Path, rename: str = None) -> bool:
    """复制文件到目标文件夹"""
    if not local_path.exists():
        print(f"  ⚠️  文件不存在，跳过: {local_path}")
        return False
    
    target_name = rename or local_path.name
    target_path = target_folder / target_name
    
    try:
        shutil.copy2(local_path, target_path)
        size = target_path.stat().st_size
        print(f"  ✅ {target_name} → {size} bytes")
        return True
    except Exception as e:
        print(f"  ❌ 复制失败: {local_path} - {e}")
        return False


def main():
    args = parse_args()
    patient_id = args.patient_id
    paths = build_paths(patient_id)
    analyzed_dir = paths["analyzed"]
    literature_dir = paths["literature"]
    reports_dir = paths["reports"]

    print(f"\n{'='*60}")
    print(f"📅 当天日期: {TODAY}")
    print(f"👤 病人ID: {patient_id}")
    print(f"📂 本地上传根目录: {LOCAL_UPLOAD_ROOT}")
    print(f"{'='*60}\n")

    # 动态构建文件清单（适配新目录结构），文件名加病人ID前缀
    upload_map = [
        # --- 原始数据 ---
        (analyzed_dir / "lab_metrics.csv",                       "原始数据",  None),
        (analyzed_dir / "lab_metrics.json",                      "原始数据",  None),
        # --- 文献参考 ---
        (literature_dir / "literature_results.md",               "文献参考",  None),
        # --- 中间结果 ---
        (literature_dir / "literature_interpretation.md",        "中间结果",  None),
        (literature_dir / "mri_report_check_results.md",         "中间结果",  None),
        (reports_dir / "analysis_results_report.md",             "中间结果",  None),
        # --- 统计结果（7张图表）---
        (analyzed_dir / "figures" / "fig_01_trend_regression.png",      "统计结果",  None),
        (analyzed_dir / "figures" / "fig_02_correlation_heatmap.png",   "统计结果",  None),
        (analyzed_dir / "figures" / "fig_03_inflammation_status.png",   "统计结果",  None),
        (analyzed_dir / "figures" / "fig_04_abnormal_indicators.png",   "统计结果",  None),
        (analyzed_dir / "figures" / "fig_05_moving_average.png",        "统计结果",  None),
        (analyzed_dir / "figures" / "fig_06_cv_stability.png",          "统计结果",  None),
        (analyzed_dir / "figures" / "fig_07_zscore_distribution.png",   "统计结果",  None),
        # --- 最终报告（当天根目录）---
        (reports_dir / "final_integrated_report.md",             None,        None),
    ]
    
    # Step 1: 创建当天日期文件夹
    day_folder = LOCAL_UPLOAD_ROOT / TODAY
    print(f"① 创建当天文件夹: {day_folder}")
    if not create_local_folder(day_folder):
        print("  ❌ 当天文件夹创建失败，退出")
        return
    print(f"  ✅ 当天文件夹: {day_folder}")

    # Step 2: 创建四个子文件夹
    subfolders = {}
    print(f"\n② 创建四个子文件夹")
    for sf_name in SUBFOLDER_NAMES:
        sf_path = day_folder / sf_name
        if create_local_folder(sf_path):
            subfolders[sf_name] = sf_path
        else:
            print(f"  ❌ {sf_name} 创建失败")

    # Step 3: 复制所有文件
    print(f"\n③ 复制所有文件")
    copied_count = 0
    skipped_count = 0
    for local_path, subfolder, rename in upload_map:
        if not local_path.exists():
            print(f"  ⚠️  文件不存在，跳过: {local_path}")
            skipped_count += 1
            continue
        
        if subfolder is None:
            # 根目录
            target_folder = day_folder
        else:
            target_folder = subfolders.get(subfolder)
            if not target_folder:
                print(f"  ⚠️  子文件夹 {subfolder} 未创建成功，跳过: {local_path}")
                skipped_count += 1
                continue
        
        if copy_file_to_folder(local_path, target_folder, rename):
            copied_count += 1
        else:
            skipped_count += 1

    print(f"\n{'='*60}")
    print(f"🎉 本地文件组织完成！")
    print(f"   ✅ 成功复制: {copied_count} 个文件")
    print(f"   ⚠️  跳过: {skipped_count} 个文件")
    print(f"   📂 本地路径: {day_folder}")
    print(f"{'='*60}\n")
    
    # Step 4: 可选 - 上传到飞书云盘
    if args.upload_to_feishu:
        print(f"\n{'='*60}")
        print(f"🚀 开始上传到飞书云盘...")
        print(f"{'='*60}\n")
        
        # 检查 lark-cli 是否安装
        has_lark_cli = check_lark_cli_installed()
        
        if not has_lark_cli:
            print("❌ 未检测到 lark-cli，请先安装：")
            print("   npm install -g @larksuiteoapi/lark-cli")
            print("   或: pip install lark-oapi")
            print("\n💡 提示：您可以继续使用本地文件组织功能，然后手动上传到飞书")
            return
        
        print("✅ 检测到 lark-cli 已安装\n")
        
        # 检查飞书配置
        folder_token = os.environ.get("FEISHU_FOLDER_TOKEN")
        
        if not folder_token:
            print("❌ 缺少 FEISHU_FOLDER_TOKEN 配置")
            print("\n⚠️  请先完成以下步骤：")
            print("   1. 在飞书云盘中创建文件夹：'检验AI分析'")
            print("   2. 右键点击该文件夹 → '复制链接'")
            print("   3. 从链接中提取 folder_token")
            print("   4. 在 .env 文件中设置：FEISHU_FOLDER_TOKEN=xxx")
            return
        
        try:
            # 创建当天日期文件夹（使用 lark-cli）
            print(f"① 检查/创建飞书云盘文件夹: {TODAY}")
            
            # 先列出文件夹，检查是否已存在
            list_cmd = [
                "lark-cli", "drive", "files", "list",
                "--params", f'{{"folder_token": "{folder_token}", "page_size": 50}}'
            ]
            
            result = subprocess.run(
                list_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                shell=True  # Windows 兼容性
            )
            
            day_folder_token = None
            if result.returncode == 0:
                import json as json_module
                try:
                    data = json_module.loads(result.stdout)
                    files = data.get("data", {}).get("files", [])
                    for f in files:
                        if f.get("name") == TODAY and f.get("type") == "folder":
                            day_folder_token = f.get("token")
                            print(f"  ✅ 找到现有文件夹: {day_folder_token}")
                            break
                except:
                    pass
            
            # 如果不存在，创建文件夹
            if not day_folder_token:
                print(f"  ⚠️  未找到'{TODAY}'文件夹，正在创建...")
                create_cmd = [
                    "lark-cli", "drive", "+create-folder",
                    "--name", TODAY,
                    "--folder-token", folder_token
                ]
                
                result = subprocess.run(
                    create_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    shell=True  # Windows 兼容性
                )
                
                if result.returncode == 0:
                    import json as json_module
                    try:
                        data = json_module.loads(result.stdout)
                        day_folder_token = data.get("data", {}).get("token")
                        if day_folder_token:
                            print(f"  ✅ 已创建文件夹: {day_folder_token}")
                        else:
                            print(f"  ⚠️  创建成功但未返回token")
                            return
                    except Exception as parse_err:
                        print(f"  ❌ 解析创建结果失败: {parse_err}")
                        print(f"     Raw output: {result.stdout[:200] if result.stdout else 'empty'}")
                        return
                else:
                    stderr_msg = result.stderr if result.stderr else "Unknown error"
                    print(f"  ❌ 创建文件夹失败: {stderr_msg[:200]}")
                    return
            
            # 创建四个子文件夹
            print(f"\n② 创建四个子文件夹")
            feishu_subfolders = {}
            for sf_name in SUBFOLDER_NAMES:
                create_cmd = [
                    "lark-cli", "drive", "+create-folder",
                    "--name", sf_name,
                    "--folder-token", day_folder_token
                ]
                
                result = subprocess.run(
                    create_cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    shell=True  # Windows 兼容性
                )
                
                if result.returncode == 0:
                    import json as json_module
                    try:
                        data = json_module.loads(result.stdout)
                        sf_token = data.get("data", {}).get("token")
                        feishu_subfolders[sf_name] = sf_token
                        print(f"  ✅ {sf_name}: {sf_token}")
                    except:
                        print(f"  ⚠️  {sf_name} 创建成功但解析token失败")
                else:
                    print(f"  ⚠️  {sf_name} 创建失败")
            
            # 上传所有文件
            print(f"\n③ 上传所有文件到飞书云盘")
            uploaded_count = 0
            upload_skipped = 0
            for local_path, subfolder, rename in upload_map:
                if not local_path.exists():
                    upload_skipped += 1
                    continue
                
                if subfolder is None:
                    # 根目录
                    target_token = day_folder_token
                else:
                    target_token = feishu_subfolders.get(subfolder)
                    if not target_token:
                        upload_skipped += 1
                        continue
                
                if upload_file_with_lark_cli(local_path, target_token):
                    uploaded_count += 1
                else:
                    upload_skipped += 1
            
            print(f"\n{'='*60}")
            print(f"🎉 飞书上传完成！")
            print(f"   ✅ 成功上传: {uploaded_count} 个文件")
            print(f"   ⚠️  跳过: {upload_skipped} 个文件")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n❌ 飞书上传失败: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("💡 提示: 使用 --upload-to-feishu 参数可自动上传到飞书云盘")


if __name__ == "__main__":
    main()
