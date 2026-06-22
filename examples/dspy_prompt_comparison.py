#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy Prompt 对比工具

自动对比标准模式 (Prompt Engineering) 与 DSPy 优化模式 (Prompt Optimization) 的 prompt:
1. 提取标准模式生成的 prompt (从 dspy_prompts/*_standard_prompt.txt)
2. 提取 DSPy 优化模式生成的 prompt (从 dspy_prompts/*_dspy_prompts.json)
3. 生成对比报告 (Markdown + JSON)

用法:
    python examples/dspy_prompt_comparison.py --data-dir data/<patient_id>/<timestamp>
    python examples/dspy_prompt_comparison.py --data-dir data/<patient_id>/<timestamp> --module literature_interpreter
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))


def find_dspy_prompts_dirs(data_dir: Path) -> Dict[str, Path]:
    """查找 data_dir 下所有的 dspy_prompts 目录"""
    dirs = {}
    candidates = {
        "literature_interpreter": data_dir / "03_literature" / "dspy_prompts",
        "mri_analyzer": data_dir / "03_literature" / "dspy_prompts",
        "final_report_generator": data_dir / "04_reports" / "dspy_prompts",
    }
    for name, path in candidates.items():
        if path.exists():
            dirs[name] = path
    return dirs


def load_standard_prompt(prompts_dir: Path, module_name: str) -> Optional[Dict]:
    """加载标准模式的 prompt"""
    candidates = [
        f"{module_name}_standard_prompt.txt",
    ]
    for filename in candidates:
        path = prompts_dir / filename
        if path.exists():
            content = path.read_text(encoding="utf-8")
            return {
                "type": "standard",
                "path": str(path),
                "content": content,
                "length": len(content),
                "lines": content.count("\n") + 1,
                "filename": filename,
            }
    return None


def load_dspy_prompts(prompts_dir: Path, module_name: str) -> Optional[Dict]:
    """加载 DSPy 优化模式的 prompts"""
    json_path = prompts_dir / f"{module_name}_dspy_prompts.json"
    md_path = prompts_dir / f"{module_name}_dspy_prompts.md"

    if not json_path.exists():
        return None

    data = json.loads(json_path.read_text(encoding="utf-8"))

    # 提取关键信息
    summary = {
        "type": "dspy",
        "path": str(json_path),
        "module_name": data.get("module_name", module_name),
        "module_type": data.get("module_type", ""),
        "predictors": [],
        "total_demos": data.get("total_demos", 0),
    }

    for pred in data.get("predictors", []):
        sig = pred.get("signature", {})
        summary["predictors"].append(
            {
                "name": pred.get("predictor_name", ""),
                "type": pred.get("predictor_type", ""),
                "signature_name": sig.get("signature_name", ""),
                "instructions": sig.get("instructions", ""),
                "instructions_length": len(sig.get("instructions", "")),
                "input_fields": sig.get("input_fields", {}),
                "output_fields": sig.get("output_fields", {}),
                "num_demos": pred.get("num_demos", 0),
                "demos": pred.get("demos", []),
            }
        )

    # 估算优化后的总 prompt 长度
    total_length = 0
    for pred in summary["predictors"]:
        total_length += pred["instructions_length"]
        # 加上输入输出字段描述的长度
        for desc in pred["input_fields"].values():
            total_length += len(str(desc))
        for desc in pred["output_fields"].values():
            total_length += len(str(desc))
        # 加上 demos 的长度
        for demo in pred["demos"]:
            for k, v in demo.items():
                if not k.startswith("_"):
                    total_length += len(str(v))

    # 加上标准的 ChainOfThought 模板 (~ 500字符)
    summary["estimated_total_length"] = total_length + 500

    if md_path.exists():
        summary["markdown_path"] = str(md_path)

    return summary


def compare_prompts(standard: Dict, dspy: Dict) -> Dict:
    """对比标准模式与 DSPy 模式的 prompt"""
    comparison = {
        "module_name": dspy.get("module_name", "unknown"),
        "standard_mode": {
            "length": standard["length"],
            "lines": standard["lines"],
            "path": standard["path"],
        },
        "dspy_mode": {
            "estimated_length": dspy.get("estimated_total_length", 0),
            "total_demos": dspy.get("total_demos", 0),
            "predictors": len(dspy.get("predictors", [])),
            "path": dspy.get("path", ""),
        },
        "differences": {},
        "key_improvements": [],
    }

    # 计算差异
    std_len = standard["length"]
    dspy_len = dspy.get("estimated_total_length", 0)
    if std_len > 0:
        ratio = dspy_len / std_len
        comparison["differences"]["length_ratio"] = round(ratio, 2)
        comparison["differences"]["length_increase"] = dspy_len - std_len

    # 提取关键改进点
    for pred in dspy.get("predictors", []):
        if pred["num_demos"] > 0:
            comparison["key_improvements"].append(
                f"{pred['name']}: 添加了 {pred['num_demos']} 个 few-shot 示例"
            )
        if pred["instructions_length"] > 100:
            comparison["key_improvements"].append(
                f"{pred['name']}: 优化了指令 ({pred['instructions_length']} 字符)"
            )

        # 列出输入输出字段
        if pred["input_fields"]:
            comparison["key_improvements"].append(
                f"{pred['name']}: {len(pred['input_fields'])} 个输入字段 -> "
                f"{', '.join(list(pred['input_fields'].keys())[:3])}"
                f"{'...' if len(pred['input_fields']) > 3 else ''}"
            )
        if pred["output_fields"]:
            comparison["key_improvements"].append(
                f"{pred['name']}: {len(pred['output_fields'])} 个输出字段 -> "
                f"{', '.join(list(pred['output_fields'].keys())[:3])}"
                f"{'...' if len(pred['output_fields']) > 3 else ''}"
            )

    return comparison


def generate_markdown_report(comparisons: List[Dict], output_path: Path):
    """生成 Markdown 格式的对比报告"""
    lines = [
        "# DSPy Prompt 对比报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**对比模块数**: {len(comparisons)}",
        "",
        "---",
        "",
        "## 总览",
        "",
        "| 模块 | 标准模式长度 | DSPy模式长度(估) | 长度比 | Few-shot示例数 | 改进点 |",
        "|------|------------|----------------|--------|--------------|--------|",
    ]

    for cmp in comparisons:
        module_name = cmp["module_name"]
        std_len = cmp["standard_mode"]["length"]
        dspy_len = cmp["dspy_mode"]["estimated_length"]
        ratio = cmp["differences"].get("length_ratio", "N/A")
        demos = cmp["dspy_mode"]["total_demos"]
        improvements = len(cmp["key_improvements"])
        lines.append(
            f"| {module_name} | {std_len} | {dspy_len} | {ratio}x | {demos} | {improvements} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # 每个模块的详细对比
    for cmp in comparisons:
        module_name = cmp["module_name"]
        lines.append(f"## 模块: `{module_name}`")
        lines.append("")

        # 标准模式
        lines.append("### 标准模式 Prompt")
        lines.append("")
        lines.append(f"- **文件**: `{cmp['standard_mode']['path']}`")
        lines.append(f"- **长度**: {cmp['standard_mode']['length']} 字符")
        lines.append(f"- **行数**: {cmp['standard_mode']['lines']} 行")
        lines.append("")

        # DSPy 模式
        lines.append("### DSPy 优化模式 Prompt")
        lines.append("")
        lines.append(f"- **文件**: `{cmp['dspy_mode']['path']}`")
        lines.append(f"- **预估长度**: {cmp['dspy_mode']['estimated_length']} 字符")
        lines.append(f"- **Predictor 数**: {cmp['dspy_mode']['predictors']}")
        lines.append(f"- **Few-shot 示例总数**: {cmp['dspy_mode']['total_demos']}")
        lines.append("")

        # 差异
        lines.append("### 关键差异")
        lines.append("")
        diff = cmp["differences"]
        if "length_ratio" in diff:
            lines.append(
                f"- **Prompt 长度变化**: {diff['length_ratio']}x "
                f"({'增加' if diff.get('length_increase', 0) > 0 else '减少'} "
                f"{abs(diff.get('length_increase', 0))} 字符)"
            )
        lines.append("")

        # 改进点
        lines.append("### DSPy 优化改进点")
        lines.append("")
        for imp in cmp["key_improvements"]:
            lines.append(f"- {imp}")
        lines.append("")

        lines.append("---")
        lines.append("")

    lines.append("## 总结")
    lines.append("")
    lines.append("### DSPy 框架的关键优势:")
    lines.append("")
    lines.append(
        "1. **自动 Few-shot 示例选择**: 通过 BootstrapFewShot 优化器自动从训练数据中选择高质量示例"
    )
    lines.append("2. **结构化 Signature**: 使用声明式 Signature 定义输入输出,自动生成优化的指令")
    lines.append("3. **可解释的优化**: 所有 prompts 和示例都被结构化保存,便于审查和改进")
    lines.append("4. **模型无关**: 同一套 prompt 可适配不同 LLM (DeepSeek, Qwen-VL 等)")
    lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def generate_json_report(comparisons: List[Dict], output_path: Path):
    """生成 JSON 格式的对比报告"""
    report = {
        "generated_at": datetime.now().isoformat(),
        "total_comparisons": len(comparisons),
        "comparisons": comparisons,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="DSPy Prompt 对比工具")
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="数据目录路径,例如: data/846552421134373347/20260611_170121",
    )
    parser.add_argument(
        "--module",
        type=str,
        choices=["literature_interpreter", "mri_analyzer", "final_report_generator"],
        help="指定要对比的模块 (默认全部)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None, help="报告输出目录 (默认: data_dir/reports/)"
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = WORK_ROOT / data_dir

    if not data_dir.exists():
        print(f"[错误] 数据目录不存在: {data_dir}")
        sys.exit(1)

    print(f"[信息] 数据目录: {data_dir}")
    print("[信息] 查找 dspy_prompts 目录...")

    prompts_dirs = find_dspy_prompts_dirs(data_dir)
    if not prompts_dirs:
        print("[错误] 未找到任何 dspy_prompts 目录")
        print(
            "  请先运行 DSPy 优化模式: python -m lab_analysis.literature_interpreter_dspy --use-dspy"
        )
        sys.exit(1)

    print(f"[信息] 找到 {len(prompts_dirs)} 个 prompts 目录:")
    for name, path in prompts_dirs.items():
        print(f"  - {name}: {path}")

    # 确定输出目录
    output_dir = Path(args.output_dir) if args.output_dir else data_dir / "reports"
    if not output_dir.is_absolute():
        output_dir = WORK_ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # 过滤掉空的 prompts_dir
    valid_prompts_dirs = {}
    for name, path in prompts_dirs.items():
        if any(path.glob("*")):
            valid_prompts_dirs[name] = path
        else:
            print(f"[跳过] {name}: prompts 目录为空")

    comparisons = []
    target_modules = [args.module] if args.module else list(valid_prompts_dirs.keys())

    for module_name in target_modules:
        if module_name not in valid_prompts_dirs:
            print(f"[警告] 模块 {module_name} 没有 prompts 目录,跳过")
            continue

        prompts_dir = valid_prompts_dirs[module_name]
        print(f"\n[{module_name}] 加载 prompts...")

        standard = load_standard_prompt(prompts_dir, module_name)
        dspy_data = load_dspy_prompts(prompts_dir, module_name)

        if not standard:
            print("  [警告] 未找到标准模式 prompt 文件")
        if not dspy_data:
            print("  [警告] 未找到 DSPy 模式 prompt 文件")

        if standard and dspy_data:
            print(f"  [标准] prompt: {standard['length']} 字符")
            print(f"  [DSPy] 预估: {dspy_data['estimated_total_length']} 字符")
            print(f"  [DSPy] Few-shot: {dspy_data['total_demos']} 个")
            comparison = compare_prompts(standard, dspy_data)
            comparisons.append(comparison)
        elif dspy_data:
            print("  [信息] 仅 DSPy 数据,生成独立报告")
            comparisons.append(
                {
                    "module_name": module_name,
                    "standard_mode": {"length": 0, "lines": 0, "path": "(未运行标准模式)"},
                    "dspy_mode": {
                        "estimated_length": dspy_data.get("estimated_total_length", 0),
                        "total_demos": dspy_data.get("total_demos", 0),
                        "predictors": len(dspy_data.get("predictors", [])),
                        "path": dspy_data.get("path", ""),
                    },
                    "differences": {},
                    "key_improvements": ["仅 DSPy 模式数据,未运行标准模式进行对比"],
                }
            )

    if not comparisons:
        print("\n[错误] 没有可对比的数据")
        sys.exit(1)

    # 生成报告
    md_path = output_dir / "dspy_prompt_comparison.md"
    json_path = output_dir / "dspy_prompt_comparison.json"

    generate_markdown_report(comparisons, md_path)
    generate_json_report(comparisons, json_path)

    print("\n[OK] 对比报告生成完成!")
    print(f"  [Markdown] {md_path}")
    print(f"  [JSON]     {json_path}")
    print("\n[提示] 可使用以下命令查看对比:")
    print(f"  cat {md_path}")


if __name__ == "__main__":
    main()
