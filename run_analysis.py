#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_analysis.py — Pipeline 统一入口
串联 data_loader → data_analyzer → literature_searcher → literature_interpreter
→ qwen_vl_report_check → gen_final_report → upload_to_feishu

用法：python run_analysis.py --patient-id <诊疗卡号>
"""
import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

WIKI_ROOT = Path.home() / "wiki"
SCRIPTS_DIR = WIKI_ROOT / "scripts"


def parse_args():
    parser = argparse.ArgumentParser(description="医学分析 Pipeline 统一入口")
    parser.add_argument("--patient-id", required=True, help="病人诊疗卡号")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 循证解读步骤")
    parser.add_argument("--skip-imaging", action="store_true", help="跳过影像分析步骤")
    return parser.parse_args()


def get_deid(original_id: str) -> str:
    """从映射文件查 de-identified ID。"""
    import json
    mapping_file = Path.home() / ".hermes" / "patient_mapping.json"
    if mapping_file.exists():
        with open(mapping_file) as f:
            mapping = json.load(f)
        # 支持 de-id → original（正向查）和 original → de-id（反向查）
        for deid, orig in mapping.items():
            if orig == original_id or deid == original_id:
                return deid
    # 找不到则用 encode() 生成（兼容旧数据）
    sys.path.insert(0, str(SCRIPTS_DIR))
    from patient_id import encode
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
        print(f"\n当前 /root/wiki/raw/ 下的病人目录：")
        raw_parent = WIKI_ROOT / "raw"
        if raw_parent.exists():
            for d in sorted(raw_parent.iterdir()):
                if d.is_dir():
                    print(f"  - {d.name}")
        else:
            print("  （raw 目录为空或不存在）")
        return False
    return True


def run_step(name: str, script: Path, extra_args: list[str] = None, env: dict = None) -> int:
    """运行单步脚本。"""
    python = str(WIKI_ROOT / ".venv/bin/python")
    cmd = [python, str(script)]
    if extra_args:
        cmd.extend(extra_args)
    print(f"\n{'='*60}")
    print(f"▶ 步骤: {name}")
    print(f"命令: {' '.join(cmd)}")
    print(f"{'='*60}")
    import os
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(cmd, cwd=str(WIKI_ROOT), env=full_env)
    return result.returncode


def main():
    import os
    args = parse_args()
    original_id = args.patient_id

    # 从 mapping 文件或 encode() 获取 de-identified ID
    deid = get_deid(original_id)

    # 生成时间戳目录（de-id 子目录）
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_dir = f"{deid}/{ts}"

    print(f"[{datetime.now().isoformat()}] Pipeline 启动")
    print(f"👤 原始病人ID: {original_id}")
    print(f"👤 脱敏病人ID: {deid}")
    print(f"📂 输出目录: data/{ts_dir}/")
    print(f"🔖 时间戳: {ts}")

    # 前置检查：病人数据是否存在（用 de-id 查 raw 目录）
    print(f"\n① 前置检查：验证病人数据")
    if not check_patient_data(deid):
        print(f"\n❌ 病人ID [{deid}] 没有找到对应的原始数据，请确认目录结构：")
        print(f"   /root/wiki/raw/patient_{deid}/lab/        ← 检验报告截图")
        print(f"   /root/wiki/raw/patient_{deid}/papers/    ← 结构化报告（lab_report_*/metrics.md）")
        print(f"   /root/wiki/raw/patient_{deid}/imaging/   ← MRI 影像序列（可选）")
        print(f"\n请确认病人ID，或将数据放入上述目录后重新执行。")
        sys.exit(1)

    # 统一使用 de-id 传递给子脚本
    pid_arg = ["--patient-id", deid]
    # 通过环境变量传递时间戳（仅时间戳，无 de-id 前缀）
    ts_env = {"ANALYSIS_TS": ts}

    # Step 1: 数据加载
    rc = run_step("② 数据加载 (data_loader)", SCRIPTS_DIR / "data_loader.py", pid_arg, ts_env)
    if rc != 0:
        print(f"[!] data_loader 失败，退出")
        sys.exit(1)

    # Step 2: 数据分析
    rc = run_step("③ 数据分析 (data_analyzer)", SCRIPTS_DIR / "data_analyzer.py", pid_arg, ts_env)
    if rc != 0:
        print(f"[!] data_analyzer 失败，退出")
        sys.exit(1)

    # Step 3: 文献检索
    rc = run_step("④ 文献检索 (literature_searcher)", SCRIPTS_DIR / "literature_searcher.py", pid_arg, ts_env)
    if rc != 0:
        print(f"[!] literature_searcher 失败，退出")
        sys.exit(1)

    # Step 4: 循证解读
    if args.skip_llm:
        print("\n[跳过] 循证解读（--skip-llm）")
    else:
        rc = run_step("⑤ 循证解读 (literature_interpreter)", SCRIPTS_DIR / "literature_interpreter.py", pid_arg, ts_env)
        if rc != 0:
            print(f"[!] literature_interpreter 失败（非致命，继续）")

    # Step 5: 影像分析
    if args.skip_imaging:
        print("\n[跳过] 影像分析（--skip-imaging）")
    else:
        rc = run_step("⑥ 影像分析 (qwen_vl_report_check)", SCRIPTS_DIR / "qwen_vl_report_check.py", pid_arg, ts_env)
        if rc != 0:
            print(f"[!] qwen_vl_report_check 失败（非致命，继续）")

    # Step 6: 生成最终报告
    rc = run_step("⑦ 生成最终报告 (gen_final_report)", SCRIPTS_DIR / "gen_final_report.py", pid_arg, ts_env)
    if rc != 0:
        print(f"[!] gen_final_report 失败（非致命，继续）")

    # Step 7: 飞书上云
    rc = run_step("⑧ 飞书上云 (upload_to_feishu)", SCRIPTS_DIR / "upload_to_feishu.py", pid_arg, ts_env)
    if rc != 0:
        print(f"[!] upload_to_feishu 失败（非致命，完成）")

    data_dir = WIKI_ROOT / "data" / ts_dir
    print(f"\n[{datetime.now().isoformat()}] Pipeline 完成")
    print(f"\n输出目录：{data_dir}/")
    if data_dir.exists():
        for f in sorted(data_dir.iterdir()):
            print(f"  - {f.name}")


if __name__ == "__main__":
    main()
