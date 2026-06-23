#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版 DSPy 训练数据收集工具

从多个来源收集训练数据:
1. 已有 Pipeline 运行结果
2. 手动标注的示例
3. 历史病例数据

输出格式化的 JSONL 文件,用于 DSPy 模块编译
"""

import json
from pathlib import Path
from typing import Dict, List


def collect_literature_interpretation_samples(data_root: Path = None) -> List[Dict]:
    """
    收集文献解读训练样本

    Returns:
        List of samples for literature_interpreter module
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data"

    samples = []

    print("=" * 60)
    print("收集文献解读训练样本")
    print("=" * 60)

    for patient_dir in sorted(data_root.glob("*")):
        if not patient_dir.is_dir():
            continue

        patient_id = patient_dir.name

        # 遍历所有时间戳目录
        for ts_dir in sorted(patient_dir.glob("*")):
            if not ts_dir.is_dir():
                continue

            timestamp = ts_dir.name

            # 检查必需文件
            analysis_file = ts_dir / "02_analyzed" / "analysis_results.json"
            lit_file = ts_dir / "03_literature" / "literature_results.json"
            interp_file = ts_dir / "03_literature" / "literature_interpretation.json"

            if not (analysis_file.exists() and lit_file.exists()):
                continue

            try:
                # 加载分析结果
                with open(analysis_file, "r", encoding="utf-8") as f:
                    analysis_results = json.load(f)

                # 加载文献结果
                with open(lit_file, "r", encoding="utf-8") as f:
                    literature_results = json.load(f)

                # 加载专家解读(如果存在)
                interpretation = ""
                if interp_file.exists():
                    with open(interp_file, "r", encoding="utf-8") as f:
                        interp_data = json.load(f)
                        interpretation = interp_data.get("response", "")

                sample = {
                    "patient_id": patient_id,
                    "timestamp": timestamp,
                    "analysis_results": analysis_results,
                    "literature_results": literature_results,
                    "interpretation": interpretation or "待专家标注",
                    "source": "pipeline_run",
                }

                samples.append(sample)
                print(f"  [成功] {patient_id}/{timestamp}")

            except Exception as e:
                print(f"  [警告] {patient_id}/{timestamp}: {e}")

    print(f"\n总计收集: {len(samples)} 个样本\n")
    return samples


def collect_lab_extraction_samples(data_root: Path = None) -> List[Dict]:
    """
    收集检验数据提取训练样本

    Returns:
        List of samples for lab_data_extractor module
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "raw"

    samples = []

    print("=" * 60)
    print("收集检验数据提取训练样本")
    print("=" * 60)

    # 查找所有检验报告图片
    lab_dir = data_root / "Origin_data"
    if not lab_dir.exists():
        print(f"  [警告] 目录不存在: {lab_dir}")
        return samples

    image_files = list(lab_dir.glob("*.jpg")) + list(lab_dir.glob("*.png"))

    for img_file in sorted(image_files):
        # 查找对应的提取结果
        result_file = img_file.with_suffix(".json")

        if not result_file.exists():
            continue

        try:
            with open(result_file, "r", encoding="utf-8") as f:
                extraction_result = json.load(f)

            sample = {
                "image_path": str(img_file),
                "extraction_result": extraction_result,
                "source": "vision_extraction",
            }

            samples.append(sample)
            print(f"  [成功] {img_file.name}")

        except Exception as e:
            print(f"  [警告] {img_file.name}: {e}")

    print(f"\n总计收集: {len(samples)} 个样本\n")
    return samples


def add_manual_examples() -> List[Dict]:
    """
    添加手动标注的示例数据

    Returns:
        List of manually annotated examples
    """
    print("=" * 60)
    print("添加手动标注示例")
    print("=" * 60)

    manual_examples = [
        {
            "patient_id": "manual_example_001",
            "timestamp": "manual",
            "analysis_results": {
                "abnormal_indicators": [
                    {"name": "白细胞计数", "value": 12.5, "unit": "10^9/L", "status": "偏高"},
                    {"name": "C反应蛋白", "value": 45.2, "unit": "mg/L", "status": "显著升高"},
                ],
                "trend_analysis": "炎症指标呈上升趋势",
            },
            "literature_results": {
                "papers": [
                    {
                        "title": "白细胞计数在感染诊断中的临床意义",
                        "abstract": "本研究探讨了白细胞计数作为感染标志物的敏感性和特异性...",
                    }
                ]
            },
            "interpretation": """患者白细胞计数和C反应蛋白均显著升高,提示存在急性细菌感染或炎症反应。

**病理生理机制:**
- 白细胞升高反映骨髓造血功能活跃,是机体对感染的免疫应答
- C反应蛋白作为急性期反应蛋白,在炎症刺激下由肝脏合成增加

**临床意义:**
结合临床表现,建议进一步排查感染灶,必要时进行细菌培养和药敏试验。

**建议:**
1. 完善血常规、降钙素原等炎症指标
2. 寻找感染源(呼吸道、泌尿道等)
3. 根据病情考虑经验性抗生素治疗""",
            "source": "manual_annotation",
            "quality": "expert_reviewed",
        }
    ]

    for example in manual_examples:
        print(f"  [成功] 添加手动示例: {example['patient_id']}")

    print(f"\n总计添加: {len(manual_examples)} 个手动示例\n")
    return manual_examples


def save_training_data(samples: List[Dict], output_file: Path):
    """
    保存训练数据为 JSONL 格式

    Args:
        samples: 训练样本列表
        output_file: 输出文件路径
    """
    print("=" * 60)
    print("保存训练数据")
    print("=" * 60)

    # 确保目录存在
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # 写入 JSONL 文件
    with open(output_file, "w", encoding="utf-8") as f:
        for sample in samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print(f"[成功] 已保存到: {output_file}")
    print(f"       总样本数: {len(samples)}")

    # 统计样本来源
    source_stats = {}
    for sample in samples:
        source = sample.get("source", "unknown")
        source_stats[source] = source_stats.get(source, 0) + 1

    print("\n样本来源分布:")
    for source, count in source_stats.items():
        print(f"  - {source}: {count} 个")


def main():
    """主函数"""
    print("\n" + "[STATS]" * 30)
    print("DSPy 训练数据收集工具")
    print("[STATS]" * 30 + "\n")

    all_samples = []

    # 1. 收集文献解读样本
    lit_samples = collect_literature_interpretation_samples()
    all_samples.extend(lit_samples)

    # 2. 收集检验数据提取样本
    lab_samples = collect_lab_extraction_samples()
    all_samples.extend(lab_samples)

    # 3. 添加手动标注示例
    manual_samples = add_manual_examples()
    all_samples.extend(manual_samples)

    # 4. 保存训练数据
    output_file = Path(__file__).parent.parent / "data" / "dspy_training_enhanced.jsonl"
    save_training_data(all_samples, output_file)

    print("\n" + "=" * 60)
    print("[DONE] 训练数据收集完成!")
    print("=" * 60)
    print("\n下一步:")
    print(f"1. 检查数据质量: {output_file}")
    print("2. 运行编译脚本: python examples/compile_dspy_module.py")
    print("3. 验证优化效果: python examples/dspy_quant_eval.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
