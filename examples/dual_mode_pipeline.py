#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dual_mode_pipeline.py — Standard / DSPy 双模式 Pipeline 对比入口

用途:
    把"一次 pipeline 同时跑 Standard + DSPy 并产出对比报告"封装为一个易用命令,
    内部复用现有 ``--compare-report-modes`` 机制和 ``compare_report_modes`` 模块。

两种模式:
    1) --auto-pick        : 从 data/{deid}/ 自动选最近 std 和 dspy 两次时间戳
    2) --std-ts --dspy-ts : 显式指定两个时间戳

示例:
    # 自动选最近两次
    python examples/dual_mode_pipeline.py --id-card 846552421134373347 --auto-pick

    # 显式指定
    python examples/dual_mode_pipeline.py --id-card 846552421134373347 \\
        --std-ts 20260620_175252 --dspy-ts 20260620_175730

    # 跑完后联动 quant eval
    python examples/dual_mode_pipeline.py --id-card 846552421134373347 \\
        --auto-pick --quant

    # 跑一次新 pipeline (含双模式)
    python examples/dual_mode_pipeline.py --run-fresh --id-card 513229198801040014

输出:
    data/{deid}/{std_ts}/04_reports/
        ├─ mode_comparison.json          # 章节级对比
        ├─ mode_comparison_report.md     # 人类可读对比
        └─ quant_eval_report.{json,md}   # 6 指标量化 (--quant 时)

设计原则:
    - 不重写双跑逻辑,只做包装/调度,避免维护两份对比代码
    - 默认 offline 模式(用已有时间戳),不调 LLM,秒级完成
    - --run-fresh 模式调子进程 ``python -m lab_analysis --compare-report-modes``,
      需要交互式身份证号输入,实际跑会花数分钟 (含 LLM 调用)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# 时间戳目录名格式: YYYYMMDD_HHMMSS (e.g. 20260620_175730)
# auto_pick 用这个过滤, 防止把"846552421134373347"这种 id_card 误当时间戳选进来
_TS_DIR_RE = re.compile(r"^\d{8}_\d{6}$")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 推迟到需要时再 import,避免无关报错
# from lab_analysis.utils import WORK_ROOT


def _resolve_work_root() -> Path:
    from lab_analysis.utils import WORK_ROOT

    return WORK_ROOT


def _auto_pick_runs(deid: str) -> tuple[str | None, str | None]:
    """从 data/{deid}/ 找最近一次 std 和最近一次 dspy 时间戳。

    判定方法:
        - 04_reports/ 下存在 dspy_prompts/ 子目录 → dspy
        - 04_reports/final_integrated_report.md 存在且不在 dspy_prompts/ 目录下 → std
        - 04_reports/final_integrated_report.json 存在但无 md → dspy (历史DSPy跑无md)
    """
    wr = _resolve_work_root()
    patient_dir = wr / "data" / deid
    if not patient_dir.is_dir():
        return None, None

    std_ts: str | None = None
    dspy_ts: str | None = None
    for ts_dir in sorted(patient_dir.iterdir(), reverse=True):
        if not ts_dir.is_dir():
            continue
        # 只接受 YYYYMMDD_HHMMSS 格式目录, 防止 id_card 误选
        if not _TS_DIR_RE.match(ts_dir.name):
            continue
        rep = ts_dir / "04_reports"
        if not rep.is_dir():
            continue
        md = rep / "final_integrated_report.md"
        js = rep / "final_integrated_report.json"
        dspy_prompts = rep / "dspy_prompts"

        is_dspy_run = dspy_prompts.is_dir() or (js.exists() and not md.exists())
        if is_dspy_run and dspy_ts is None:
            dspy_ts = ts_dir.name
        elif md.exists() and std_ts is None:
            std_ts = ts_dir.name
        if std_ts and dspy_ts:
            break
    return std_ts, dspy_ts


def _compare_existing(deid: str, std_ts: str, dspy_ts: str) -> dict:
    """对已有两次时间戳做对比,产出 mode_comparison.{json,md}。"""
    from lab_analysis.compare_report_modes import (
        compare_reports_from_files,
        format_comparison_md,
    )

    wr = _resolve_work_root()
    std_md = wr / "data" / deid / std_ts / "04_reports" / "final_integrated_report.md"
    dspy_json = wr / "data" / deid / dspy_ts / "04_reports" / "final_integrated_report.json"

    if not std_md.exists():
        raise FileNotFoundError(f"std md 缺失: {std_md}")
    if not dspy_json.exists():
        raise FileNotFoundError(f"dspy json 缺失: {dspy_json}")

    cmp = compare_reports_from_files(std_md, dspy_json)

    out_dir = wr / "data" / deid / std_ts / "04_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mode_comparison.json").write_text(
        json.dumps(cmp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "mode_comparison_report.md").write_text(format_comparison_md(cmp), encoding="utf-8")

    return {
        "out_dir": str(out_dir),
        "std_md": str(std_md),
        "dspy_json": str(dspy_json),
        "comparison": cmp,
    }


def _print_summary(result: dict, deid: str, std_ts: str, dspy_ts: str) -> None:
    cmp = result["comparison"]
    print()
    print("=" * 72)
    print(f"  双模式对比完成: deid={deid}")
    print(f"    std_ts:  {std_ts}")
    print(f"    dspy_ts: {dspy_ts}")
    print("-" * 72)
    print(f"  std 总字符数:  {cmp.get('std_total_length', 0):,}")
    print(f"  dspy 总字符数: {cmp.get('dspy_total_length', 0):,}")
    print(f"  章节数:        {cmp.get('n_sections', 0)}")
    print(f"  平均内容重叠率: {cmp.get('avg_overlap_rate', 0):.2%}")
    print(f"  DSPy 置信度:   {cmp.get('dspy_confidence', 'N/A')}")
    print("-" * 72)
    print("  产物:")
    print(f"    {result['out_dir']}/mode_comparison.json")
    print(f"    {result['out_dir']}/mode_comparison_report.md")


def _run_fresh_pipeline(id_card: str) -> int:
    """调子进程跑新 pipeline (含 --compare-report-modes)。

    注意: 会触发交互式身份证号输入 (除非 stdin 非交互),会调 LLM API。
    """
    env = dict(os.environ)
    pp = str(PROJECT_ROOT)
    env["PYTHONPATH"] = pp + os.pathsep + env.get("PYTHONPATH", "")

    cmd = [
        sys.executable,
        "-m",
        "lab_analysis",
        "--compare-report-modes",
    ]
    print(f"[run-fresh] 执行: {' '.join(cmd)}")
    print("[run-fresh] 注意: 会要求交互式输入身份证号,会调 LLM API")
    r = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
    return r.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Standard / DSPy 双模式对比")
    parser.add_argument("--id-card", required=True, help="脱敏患者 ID")
    parser.add_argument("--std-ts", help="std 模式时间戳,形如 20260620_175252")
    parser.add_argument("--dspy-ts", help="dspy 模式时间戳")
    parser.add_argument(
        "--auto-pick",
        action="store_true",
        help="自动从 data/{id}/ 选最近 std 和 dspy 两次时间戳",
    )
    parser.add_argument(
        "--quant",
        action="store_true",
        help="对比完成后联动 examples/dspy_quant_eval.py 跑 6 指标量化",
    )
    parser.add_argument(
        "--run-fresh",
        action="store_true",
        help="跑一次新 pipeline (含 --compare-report-modes),会调 LLM",
    )
    args = parser.parse_args()

    if args.run_fresh:
        rc = _run_fresh_pipeline(args.id_card)
        return rc

    # 离线模式
    if args.auto_pick:
        std_ts, dspy_ts = _auto_pick_runs(args.id_card)
        if not std_ts or not dspy_ts:
            print(
                f"[错误] auto-pick 失败: std={std_ts} dspy={dspy_ts}\n"
                f"        请用 --std-ts 和 --dspy-ts 显式指定,或用 --run-fresh 重跑"
            )
            return 1
        print(f"[auto-pick] std_ts={std_ts} dspy_ts={dspy_ts}")
    else:
        if not args.std_ts or not args.dspy_ts:
            parser.error("需要 --auto-pick 或同时给 --std-ts 和 --dspy-ts")
        std_ts, dspy_ts = args.std_ts, args.dspy_ts

    try:
        result = _compare_existing(args.id_card, std_ts, dspy_ts)
    except FileNotFoundError as e:
        print(f"[错误] {e}")
        return 1
    except Exception as e:
        print(f"[错误] 对比失败: {e}")
        import traceback

        traceback.print_exc()
        return 1

    _print_summary(result, args.id_card, std_ts, dspy_ts)

    if args.quant:
        print()
        print("[quant] 联动 dspy_quant_eval.py ...")
        try:
            import examples.dspy_quant_eval as qe

            qe.run(
                id_card=args.id_card,
                std_ts=std_ts,
                dspy_ts=dspy_ts,
                out_dir=Path(result["out_dir"]),
            )
        except ImportError:
            print("[错误] examples/dspy_quant_eval.py 尚未存在,先实现 B 任务")
            return 2
        except Exception as e:
            print(f"[错误] quant 失败: {e}")
            import traceback

            traceback.print_exc()
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
