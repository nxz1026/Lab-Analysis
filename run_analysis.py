#!/usr/bin/env python3
"""Pipeline 统一入口：data_loader → data_analyzer → literature → ... → upload"""
import sys, subprocess, argparse
from pathlib import Path
from datetime import datetime

WIKI_ROOT = Path.home() / "wiki"

STEPS = [
    ("① 数据加载", "data_loader.py"),
    ("② 数据分析", "data_analyzer.py"),
    ("③ 文献检索", "literature_searcher.py"),
    ("④ 循证解读", "literature_interpreter.py"),
    ("⑤ 影像分析", "qwen_vl_report_check.py"),
    ("⑥ 生成报告", "gen_final_report.py"),
    ("⑦ 飞书上云", "upload_to_feishu.py"),
]


def run(name: str, script: Path, args: list[str]) -> int:
    cmd = [str(WIKI_ROOT / ".venv/bin/python"), str(script)] + args
    print(f"\n{'='*50}\n▶ {name}\n{'='*50}")
    return subprocess.run(cmd, cwd=str(WIKI_ROOT)).returncode


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--patient-id", required=True)
    p.add_argument("--skip-llm", action="store_true")
    p.add_argument("--skip-imaging", action="store_true")
    args = p.parse_args()

    pid, pid_arg = args.patient_id, ["--patient-id", args.patient_id]
    data_dir = WIKI_ROOT / "data" / pid

    print(f"[{datetime.now().isoformat()}] Pipeline 启动 | 病人ID: {pid}")

    for name, script in STEPS:
        # 条件跳过
        if "循证" in name and args.skip_llm:
            print(f"[跳过] {name}")
            continue
        if "影像" in name and args.skip_imaging:
            print(f"[跳过] {name}")
            continue

        rc = run(name, WIKI_ROOT / "scripts" / script, pid_arg)
        if rc != 0:
            print(f"[!] {name} 失败")
            if name in ["① 数据加载", "② 数据分析"]:
                sys.exit(1)

    print(f"\n[{datetime.now().isoformat()}] 完成 | 输出: {data_dir}/")


if __name__ == "__main__":
    main()
