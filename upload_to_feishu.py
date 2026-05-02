#!/usr/bin/env python3
"""飞书云盘上传 - Pipeline最终步骤"""
import subprocess, json, argparse
from pathlib import Path
from datetime import date

WIKI = Path.home() / "wiki"
TODAY = date.today().strftime("%Y-%m-%d")
PARENT = "P1PIfbUOIll6Mrd9acnc81amnzh"  # 检验AI分析
SUBFOLDERS = ["原始数据", "文献参考", "中间结果", "统计结果"]


def run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0: print(f"  ❌ {' '.join(cmd)}: {r.stderr[:100]}")
    return r.stdout.strip()


def run_json(cmd):
    out = run(cmd + ["--format", "json"] if "--format" not in cmd else cmd)
    try: return json.loads(out)
    except: print(f"  ❌ JSON解析失败: {out[:100]}"); return {}


def create_folder(name, parent_token):
    data = run_json(["lark-cli", "drive", "files", "list", "--params", json.dumps({"folder_token": parent_token})])
    for f in data.get("data", {}).get("files", []):
        if f.get("name") == name:
            print(f"  ℹ️  已存在: {name} → {f['token']}")
            return f["token"]
    out = run(["lark-cli", "drive", "+create-folder", "--name", name, "--folder-token", parent_token])
    try:
        d = json.loads(out)
        if d.get("ok") and (token := d.get("data", {}).get("folder_token")):
            print(f"  ✅ {name} → {token}"); return token
        print(f"  ❌ 创建失败: {d.get('error', d.get('msg', ''))}")
    except: print(f"  ❌ JSON解析失败: {out[:100]}")
    return None


def upload(local, folder_token, name=None):
    if not Path(local).exists(): print(f"  ⚠️  跳过: {local}"); return
    basename = name or Path(local).name
    out = run(["lark-cli", "drive", "+upload", "--file", f"./{Path(local).name}", "--folder-token", folder_token] +
               (["--name", name] if name else []), cwd=str(Path(local).parent))
    try:
        d = json.loads(out)
        if d.get("ok"):
            t = d["data"]["file_token"]; s = d["data"]["size"]
            print(f"  ✅ {basename} → {s} bytes"); return t
        print(f"  ❌ {basename}: {d.get('error', {})}")
    except: print(f"  ❌ JSON: {out[:100]}")


def main():
    p = argparse.ArgumentParser(); p.add_argument("--patient-id", required=True); args = p.parse_args()
    pid = args.patient_id
    data_dir = WIKI / "data" / pid

    print(f"\n{'='*50}\n📅 {TODAY} | 病人: {pid}\n{'='*50}\n")

    # 当天文件夹
    day_token = create_folder(TODAY, PARENT)
    if not day_token: print("❌ 当天文件夹创建失败"); return
    print(f"✅ 当天文件夹: {day_token}\n")

    # 子文件夹
    sub_tokens = {n: create_folder(n, day_token) for n in SUBFOLDERS}
    print()

    # 上传文件
    uploads = [
        (data_dir / "lab_metrics.csv", "原始数据"),
        (data_dir / "lab_metrics.json", "原始数据"),
        (data_dir / "literature_results.json", "文献参考"),
        (data_dir / "literature_interpretation.json", "中间结果"),
        (data_dir / "mri_report_check_results.json", "中间结果"),
        (data_dir / "analysis_results.json", "统计结果"),
        (data_dir / "fig_01_trend_regression.png", "统计结果"),
        (data_dir / "fig_02_correlation_heatmap.png", "统计结果"),
        (data_dir / "fig_03_inflammation_status.png", "统计结果"),
        (data_dir / "fig_04_abnormal_indicators.png", "统计结果"),
        (data_dir / "final_integrated_report.md", None),
    ]

    for path, sub in uploads:
        if sub is None:
            upload(path, day_token, f"{pid}_{path.name}")
        else:
            upload(path, sub_tokens.get(sub), f"{pid}_{path.name}")

    print(f"\n{'='*50}\n🎉 完成! https://kcnnvmk14o6i.feishu.cn/drive/folder/{day_token}\n{'='*50}")


if __name__ == "__main__":
    main()
