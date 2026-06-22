#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy 版本的文献解读模块

使用 DSPy 框架优化循证医学解读的生成质量
"""

from pathlib import Path
from typing import Dict, List

import dspy

import logging

from ._retry import SafeCallError, make_empty_prediction, safe_predict
from .prompt_inspector import extract_module_prompts, save_prompts_to_json, save_prompts_to_markdown


class LiteratureInterpretationSignature(dspy.Signature):
    """文献解读的输入输出签名"""

    patient_id: str = dspy.InputField(desc="患者ID(脱敏)")
    analysis_results: dict = dspy.InputField(desc="数据分析结果,包含异常指标和统计信息")
    literature_results: dict = dspy.InputField(desc="文献检索结果,包含相关论文摘要")

    interpretation: str = dspy.OutputField(
        desc="专业的循证医学解读,包括:\n"
        "1. 异常指标的病理生理机制解释\n"
        "2. 与文献证据的关联分析\n"
        "3. 临床意义和建议\n"
        "4. 需要进一步检查的项目"
    )
    confidence: float = dspy.OutputField(desc="解读的可信度评分(0-1)")


class LiteratureInterpreterModule(dspy.Module):
    """基于 DSPy 的文献解读模块"""

    def __init__(self):
        super().__init__()
        # 使用 ChainOfThought 提升推理质量
        self.interpret = dspy.ChainOfThought(LiteratureInterpretationSignature)

    def forward(self, patient_id: str, analysis_results: dict, literature_results: dict):
        """执行文献解读"""
        try:
            prediction = safe_predict(
                self.interpret,
                module_name="literature_interpreter",
                patient_id=patient_id,
                analysis_results=analysis_results,
                literature_results=literature_results,
            )
        except SafeCallError as exc:
            logging.getLogger(__name__).error(
                "literature_interpreter fallback to empty prediction: %s", exc
            )
            return make_empty_prediction(LiteratureInterpretationSignature)

        return dspy.Prediction(
            interpretation=prediction.interpretation, confidence=prediction.confidence
        )


def compile_interpreter(train_data: List[Dict], dev_data: List[Dict]):
    """
    编译和优化文献解读模块

    Args:
        train_data: 训练数据集 (患者ID, 分析结果, 文献结果, 专家解读)
        dev_data: 验证数据集

    Returns:
        优化后的模块
    """
    import dspy.teleprompt

    # 定义评估指标
    def interpret_metric(example, pred, trace=None):
        """评估解读质量的指标"""
        try:
            # 检查是否包含关键要素
            required_sections = ["病理生理", "临床意义", "建议"]

            score = sum(1 for section in required_sections if section in pred.interpretation) / len(
                required_sections
            )

            # 检查可信度合理性
            if hasattr(pred, "confidence") and 0.5 <= pred.confidence <= 1.0:
                score += 0.2

            return score >= 0.5  # 至少满足一半条件
        except Exception as e:
            print(f"[警告] 评估失败: {e}")
            return False

    # 使用 BootstrapFewShot 进行优化 (DSPy 3.x API)
    optimizer = dspy.teleprompt.BootstrapFewShot(metric=interpret_metric)

    module = LiteratureInterpreterModule()
    compiled_module = optimizer.compile(
        student=module,
        trainset=train_data,
        # DSPy 3.x 不再需要 devset 参数
    )

    return compiled_module


def save_dspy_prompts(module, output_dir: Path):
    """保存 DSPy 模块的优化 prompt 到磁盘"""
    prompts_data = extract_module_prompts(module, "literature_interpreter")
    json_path = save_prompts_to_json("literature_interpreter", prompts_data, output_dir)
    md_path = save_prompts_to_markdown("literature_interpreter", prompts_data, output_dir)
    return json_path, md_path


def run_dspy_interpretation(patient_id: str, data_dir: Path):
    """
    运行 DSPy 版本的文献解读

    Args:
        patient_id: 患者ID
        data_dir: 数据目录

    Returns:
        解读结果字典
    """
    import json

    # 加载前置数据
    analysis_path = data_dir / "02_analyzed" / "analysis_results.json"
    literature_path = data_dir / "03_literature" / "literature_results.json"

    with open(analysis_path, "r", encoding="utf-8") as f:
        analysis_results = json.load(f)

    with open(literature_path, "r", encoding="utf-8") as f:
        literature_results = json.load(f)

    # 初始化模块 (实际使用时应该加载已编译的模块)
    interpreter = LiteratureInterpreterModule()

    # 执行解读
    result = interpreter(
        patient_id=patient_id,
        analysis_results=analysis_results,
        literature_results=literature_results,
    )

    # 保存结果
    output = {
        "patient_id": patient_id,
        "interpretation": result.interpretation,
        "confidence": result.confidence,
        "model": "DSPy-LiteratureInterpreter",
    }

    output_path = data_dir / "03_literature" / "literature_interpretation_dspy.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 保存优化后的 prompt 信息到 03_literature 目录
    try:
        prompts_dir = data_dir / "03_literature" / "dspy_prompts"
        save_dspy_prompts(interpreter, prompts_dir)
        from .prompt_inspector import save_actual_dspy_prompt

        save_actual_dspy_prompt("literature_interpreter", prompts_dir)
        output["prompts_dir"] = str(prompts_dir)
    except Exception as e:
        print(f"  [警告] 保存 DSPy prompts 失败: {e}")

    return output


if __name__ == "__main__":
    import argparse
    import os
    from pathlib import Path

    parser = argparse.ArgumentParser(description="DSPy 文献解读")
    parser.add_argument("--id-card", required=True, help="患者ID")
    args = parser.parse_args()

    # 获取数据目录
    work_root = Path(os.environ.get("WORK_ROOT", Path.cwd()))
    raw_ts = os.environ.get("ANALYSIS_TS", args.id_card)
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts
    data_dir = work_root / "data" / args.id_card / ts

    print("[DSPy] 开始文献解读...")
    print(f"  患者ID: {args.id_card}")
    print(f"  数据目录: {data_dir}")

    result = run_dspy_interpretation(args.id_card, data_dir)

    print("\n[DSPy] 解读完成!")
    print(f"  可信度: {result['confidence']:.2f}")
    print(f"  结果已保存: {data_dir / '03_literature' / 'literature_interpretation_dspy.json'}")
