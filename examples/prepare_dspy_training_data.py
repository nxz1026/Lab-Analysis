#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy 训练数据准备工具

从已有的 Pipeline 运行结果中提取训练样本
用于 DSPy 模块的编译和优化
"""

import json
from pathlib import Path
from typing import Dict, List


def extract_training_samples(data_root: Path = None) -> List[Dict]:
    """
    从已有数据中提取训练样本

    Returns:
        List of training samples with structure:
        {
            "patient_id": str,
            "analysis_results": dict,
            "literature_results": dict,
            "interpretation": str (ground truth or expert annotation)
        }
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data"

    samples = []

    print("=" * 60)
    print("DSPy 训练数据准备")
    print("=" * 60)
    print(f"\n扫描数据目录: {data_root}")

    # 遍历所有患者
    for patient_dir in data_root.glob("*"):
        if not patient_dir.is_dir():
            continue

        patient_id = patient_dir.name
        print(f"\n[患者] {patient_id}")

        # 遍历所有时间戳
        for ts_dir in sorted(patient_dir.glob("*")):
            if not ts_dir.is_dir():
                continue

            timestamp = ts_dir.name
            print(f"  [时间戳] {timestamp}")

            # 检查是否有必要的文件
            analyzed_dir = ts_dir / "02_analyzed"
            literature_dir = ts_dir / "03_literature"

            if not analyzed_dir.exists() or not literature_dir.exists():
                print("    [跳过] 缺少必要目录")
                continue

            # 提取数据分析结果
            analysis_json = analyzed_dir / "analysis_results.json"  # 修正文件名

            analysis_results = {}
            if analysis_json.exists():
                try:
                    with open(analysis_json, "r", encoding="utf-8") as f:
                        analysis_results = json.load(f)
                    print("    [成功] 加载分析结果")
                except Exception as e:
                    print(f"    [警告] 加载分析结果失败: {e}")
                    continue

            # 提取文献检索结果
            search_results_json = literature_dir / "search_results.json"
            interpretation_md = literature_dir / "interpretation.md"

            literature_results = {}
            interpretation_text = ""

            if search_results_json.exists():
                try:
                    with open(search_results_json, "r", encoding="utf-8") as f:
                        literature_results = json.load(f)
                    print("    [成功] 加载文献结果")
                except Exception as e:
                    print(f"    [警告] 加载文献结果失败: {e}")
                    continue

            if interpretation_md.exists():
                try:
                    interpretation_text = interpretation_md.read_text(encoding="utf-8")
                    print(f"    [成功] 加载解读文本 ({len(interpretation_text)} 字符)")
                except Exception as e:
                    print(f"    [警告] 加载解读文本失败: {e}")

            # 构建训练样本
            sample = {
                "patient_id": patient_id,
                "timestamp": timestamp,
                "analysis_results": analysis_results,
                "literature_results": literature_results,
                "interpretation": interpretation_text,
            }

            samples.append(sample)
            print("    [样本] 已添加训练样本")

    print(f"\n{'=' * 60}")
    print(f"[汇总] 共提取 {len(samples)} 个训练样本")
    print(f"{'=' * 60}")

    return samples


def save_training_data(samples: List[Dict], output_path: Path = None):
    """保存训练数据到 JSONL 文件"""
    if output_path is None:
        output_path = Path(__file__).parent.parent / "data" / "dspy_training.jsonl"

    print(f"\n[保存] 保存到: {output_path}")

    with open(output_path, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"[成功] 保存 {len(samples)} 个样本")
    return output_path


def main():
    """主函数"""
    print("\n" + "[STATS]" * 30)
    print("DSPy 训练数据准备工具")
    print("[STATS]" * 30 + "\n")

    # 提取训练样本
    samples = extract_training_samples()

    if not samples:
        print("\n[警告] 未找到训练样本!")
        print("请确保:")
        print("1. 已运行完整的 Pipeline")
        print("2. 数据目录包含 02_analyzed 和 03_literature 子目录")
        return

    # 保存训练数据
    output_path = save_training_data(samples)

    print(f"\n{'=' * 60}")
    print("[完成] 训练数据准备完成!")
    print(f"{'=' * 60}")
    print("\n下一步:")
    print(f"1. 检查训练数据: {output_path}")
    print("2. 运行 DSPy 编译: python examples/compile_dspy_module.py")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
