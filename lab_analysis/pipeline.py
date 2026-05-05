#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline 统一入口：串联各步骤子模块。

用法：
  仓库根目录：python run_analysis.py --patient-id <诊疗卡号>
  或：python -m lab_analysis --patient-id <诊疗卡号>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from lab_analysis.patient_id import encode

WIKI_ROOT = Path.home() / "wiki"


def parse_args():
    parser = argparse.ArgumentParser(description="医学分析 Pipeline 统一入口")
    parser.add_argument("--patient-id", required=True, help="病人诊疗卡号")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 循证解读步骤")
    parser.add_argument("--skip-imaging", action="store_true", help="跳过影像分析步骤")
    return parser.parse_args()


def repo_root() -> Path:
    """本仓库根目录（含 pyproject.toml / lab_analysis 包）。"""
    return Path(__file__).resolve().parent.parent


def get_deid(original_id: str) -> str:
    """从映射文件查 de-identified ID；若无映射则用 encode()。"""
    mapping_file = Path.home() / ".hermes" / "patient_mapping.json"
    if mapping_file.exists():
        with open(mapping_file, encoding="utf-8") as f:
            mapping = json.load(f)
        for deid, orig in mapping.items():
            if orig == original_id or deid == original_id:
                return deid
    return encode(original_id)


def check_patient_data(deid: str) -> bool:
    """检查病人原始数据目录是否存在且有内容（de-id 目录名）。"""
    raw_dir = WIKI_ROOT / "raw" / f"patient_{deid}"
    lab_dir = raw_dir / "lab"
    imaging_dir = raw_dir / "imaging"
    papers_dir = raw_dir / "papers"

    errors = []
    if not raw_dir.exists():
        errors.append(f"  ❌ 病人目录不存在: {raw_dir}")
    else:
        has_lab = lab_dir.exists() and any(lab_dir.iterdir())
        has_papers = papers_dir.exists() and any(papers_dir.iterdir())
        has_imaging = imaging_dir.exists() and any(imaging_dir.iterdir())

        if not has_lab and not has_papers:
            errors.append(f"  ❌ 未找到检验报告: {lab_dir} 或 {papers_dir}")
        if not errors and not has_imaging:
            errors.append(f"  ⚠️  未找到影像数据: {imaging_dir}（将跳过影像分析）")

    if errors:
        print("\n".join(errors))
        print(f"\n当前 {WIKI_ROOT / 'raw'} 下的病人目录：")
        raw_parent = WIKI_ROOT / "raw"
        if raw_parent.exists():
            for d in sorted(raw_parent.iterdir()):
                if d.is_dir():
                    print(f"  - {d.name}")
        else:
            print("  （raw 目录为空或不存在）")
        return False
    return True


def pick_python_exe() -> str:
    """优先使用 ~/wiki/.venv（Hermes 部署）；否则当前解释器。"""
    unix_venv = WIKI_ROOT / ".venv" / "bin" / "python"
    win_venv = WIKI_ROOT / ".venv" / "Scripts" / "python.exe"
    if unix_venv.is_file():
        return str(unix_venv)
    if win_venv.is_file():
        return str(win_venv)
    return sys.executable


def run_step(name: str, module: str, extra_args: list[str] | None = None, env: dict | None = None) -> int:
    """以 python -m lab_analysis.<module> 运行单步。"""
    root = repo_root()
    python = pick_python_exe()
    cmd = [python, "-m", f"lab_analysis.{module}"]
    if extra_args:
        cmd.extend(extra_args)
    print(f"\n{'='*60}")
    print(f"▶ 步骤: {name}")
    print(f"命令: {' '.join(cmd)}")
    print(f"{'='*60}")
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    pp = str(root)
    if full_env.get("PYTHONPATH"):
        full_env["PYTHONPATH"] = pp + os.pathsep + full_env["PYTHONPATH"]
    else:
        full_env["PYTHONPATH"] = pp
    result = subprocess.run(cmd, cwd=str(root), env=full_env)
    return result.returncode


def main():
    args = parse_args()
    original_id = args.patient_id

    deid = get_deid(original_id)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir = f"{deid}/{ts}"

    print(f"[{datetime.now().isoformat()}] Pipeline 启动")
    print(f"👤 原始病人ID: {original_id}")
    print(f"👤 脱敏病人ID: {deid}")
    print(f"📂 输出目录: data/{ts_dir}/")
    print(f"🔖 时间戳: {ts}")

    print("\n① 前置检查：验证病人数据")
    if not check_patient_data(deid):
        wr = WIKI_ROOT
        print(f"\n❌ 病人ID [{deid}] 没有找到对应的原始数据，请确认目录结构：")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'lab'}/        ← 检验报告截图")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'papers'}/    ← 结构化报告（lab_report_*/metrics.md）")
        print(f"   {wr / 'raw' / f'patient_{deid}' / 'imaging'}/   ← MRI 影像序列（可选）")
        print("\n请确认病人ID，或将数据放入上述目录后重新执行。")
        sys.exit(1)

    pid_arg = ["--patient-id", deid]
    ts_env = {"ANALYSIS_TS": ts}

    rc = run_step("② 数据加载 (data_loader)", "data_loader", pid_arg, ts_env)
    if rc != 0:
        print("[!] data_loader 失败，退出")
        sys.exit(1)

    rc = run_step("③ 数据分析 (data_analyzer)", "data_analyzer", pid_arg, ts_env)
    if rc != 0:
        print("[!] data_analyzer 失败，退出")
        sys.exit(1)

    rc = run_step("④ 文献检索 (literature_searcher)", "literature_searcher", pid_arg, ts_env)
    if rc != 0:
        print("[!] literature_searcher 失败，退出")
        sys.exit(1)

    if args.skip_llm:
        print("\n[跳过] 循证解读（--skip-llm）")
    else:
        rc = run_step("⑤ 循证解读 (literature_interpreter)", "literature_interpreter", pid_arg, ts_env)
        if rc != 0:
            print("[!] literature_interpreter 失败（非致命，继续）")

    if args.skip_imaging:
        print("\n[跳过] 影像分析（--skip-imaging）")
    else:
        rc = run_step("⑥ 影像分析 (qwen_vl_report_check)", "qwen_vl_report_check", pid_arg, ts_env)
        if rc != 0:
            print("[!] qwen_vl_report_check 失败（非致命，继续）")

    rc = run_step("⑦ 生成最终报告 (gen_final_report)", "gen_final_report", pid_arg, ts_env)
    if rc != 0:
        print("[!] gen_final_report 失败（非致命，继续）")

    rc = run_step("⑧ 飞书上云 (upload_to_feishu)", "upload_to_feishu", pid_arg, ts_env)
    if rc != 0:
        print("[!] upload_to_feishu 失败（非致命，完成）")

    data_dir = WIKI_ROOT / "data" / ts_dir
    print(f"\n[{datetime.now().isoformat()}] Pipeline 完成")
    print(f"\n输出目录：{data_dir}/")
    if data_dir.exists():
        for f in sorted(data_dir.iterdir()):
            print(f"  - {f.name}")


if __name__ == "__main__":
    main()
