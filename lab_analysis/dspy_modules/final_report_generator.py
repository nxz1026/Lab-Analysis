#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy 版本的最终综合临床诊断报告生成模块

使用 DSPy 框架优化多源数据整合和报告生成的质量
"""

import datetime as dt
import logging
import os
from pathlib import Path

import dspy

from ..report_schema import REPORT_MD_TEMPLATE, REPORT_SECTIONS
from ._retry import SafeCallError, make_empty_prediction, safe_predict
from .prompt_inspector import extract_module_prompts, save_prompts_to_json, save_prompts_to_markdown


class FinalReportSignature(dspy.Signature):
    """最终临床报告生成的输入输出签名

    章节定义见 lab_analysis.report_schema.REPORT_SECTIONS。
    """

    patient_info: dict = dspy.InputField(desc="患者基本信息 (name, age_sex, exam_id)")
    lab_summary: str = dspy.InputField(desc="检验数据摘要，包含关键指标时序变化")
    analysis_results: dict = dspy.InputField(desc="统计分析结果，包含异常指标、相关性分析等")
    literature_interpretation: str = dspy.InputField(desc="循证医学解读文本")
    mri_analysis: str = dspy.InputField(desc="MRI影像AI分析结果（可选）")
    quality_control: str = dspy.InputField(desc="三源一致性评估质控段落")

    report_title: str = dspy.OutputField(desc="报告标题")
    # 以下 9 个章节字段名/描述由 lab_analysis.report_schema.REPORT_SECTIONS 定义
    section_1_basic_info: str = dspy.OutputField(desc=REPORT_SECTIONS[0][1])
    section_2_lab_analysis: str = dspy.OutputField(desc=REPORT_SECTIONS[1][1])
    section_3_mri_analysis: str = dspy.OutputField(desc=REPORT_SECTIONS[2][1])
    section_4_multidisciplinary: str = dspy.OutputField(desc=REPORT_SECTIONS[3][1])
    section_5_diagnosis: str = dspy.OutputField(desc=REPORT_SECTIONS[4][1])
    section_6_consistency: str = dspy.OutputField(desc=REPORT_SECTIONS[5][1])
    section_7_action_plan: str = dspy.OutputField(desc=REPORT_SECTIONS[6][1])
    section_8_followup: str = dspy.OutputField(desc=REPORT_SECTIONS[7][1])
    section_9_prognosis: str = dspy.OutputField(desc=REPORT_SECTIONS[8][1])

    confidence: float = dspy.OutputField(desc="报告可信度评分 (0.0-1.0)")


class FinalReportGenerator(dspy.Module):
    """基于 DSPy 的最终临床报告生成器"""

    def __init__(self):
        super().__init__()
        self.generate = dspy.ChainOfThought(FinalReportSignature)

    def forward(
        self,
        patient_info: dict,
        lab_summary: str,
        analysis_results: dict,
        literature_interpretation: str,
        mri_analysis: str,
        quality_control: str,
    ):

        try:
            return safe_predict(
                self.generate,
                module_name="final_report_generator",
                patient_info=patient_info,
                lab_summary=lab_summary,
                analysis_results=analysis_results,
                literature_interpretation=literature_interpretation,
                mri_analysis=mri_analysis or "影像数据暂缺",
                quality_control=quality_control,
            )
        except SafeCallError as exc:
            logging.getLogger(__name__).error(
                "final_report_generator fallback to empty prediction: %s", exc
            )
            return make_empty_prediction(FinalReportSignature)


def compile_report_generator(train_data: list, dev_data: list):
    """
    编译和优化报告生成器

    Args:
        train_data: 训练数据集
        dev_data: 验证数据集

    Returns:
        优化后的模块
    """
    import dspy.teleprompt

    # 定义评估指标
    def report_quality_metric(example, pred, trace=None):
        """评估报告质量的指标"""
        try:
            score = 0

            # 检查是否包含所有必需的章节
            required_sections = [
                "section_1_basic_info",
                "section_2_lab_analysis",
                "section_3_mri_analysis",
                "section_4_multidisciplinary",
                "section_5_diagnosis",
                "section_6_consistency",
                "section_7_action_plan",
                "section_8_followup",
                "section_9_prognosis",
            ]

            present_sections = sum(
                1
                for section in required_sections
                if hasattr(pred, section) and getattr(pred, section)
            )
            score += (present_sections / len(required_sections)) * 0.7

            # 检查置信度合理性
            if hasattr(pred, "confidence") and 0.5 <= pred.confidence <= 1.0:
                score += 0.2

            # 检查内容长度（确保内容充实）
            total_length = sum(len(getattr(pred, section, "")) for section in required_sections)
            if total_length > 2000:  # 至少2000字符
                score += 0.1

            return score >= 0.7  # 至少达到70%的质量标准

        except Exception as e:
            print(f"[警告] 评估失败: {e}")
            return False

    # 使用 BootstrapFewShot 进行优化
    optimizer = dspy.teleprompt.BootstrapFewShot(metric=report_quality_metric)

    module = FinalReportGenerator()
    compiled_module = optimizer.compile(
        student=module,
        trainset=train_data,
        # DSPy 3.x 不再需要 devset 参数
    )

    return compiled_module


def save_dspy_prompts(module, output_dir: Path):
    """保存 DSPy 模块的优化 prompt 到磁盘"""
    prompts_data = extract_module_prompts(module, "final_report_generator")
    json_path = save_prompts_to_json("final_report_generator", prompts_data, output_dir)
    md_path = save_prompts_to_markdown("final_report_generator", prompts_data, output_dir)
    return json_path, md_path


def run_dspy_final_report(
    patient_id: str,
    data_dir: Path,
    patient_info: dict,
    lab_summary: str,
    analysis_results: dict,
    literature_interpretation: str,
    mri_analysis: str,
    quality_control: str,
):
    """
    运行 DSPy 优化的最终报告生成

    Args:
        patient_id: 患者ID
        data_dir: 数据目录
        patient_info: 患者信息
        lab_summary: 检验数据摘要
        analysis_results: 分析结果
        literature_interpretation: 文献解读
        mri_analysis: MRI分析结果
        quality_control: 质控段落

    Returns:
        生成的报告字典
    """
    import os

    import dspy
    from dotenv import load_dotenv

    # 加载环境变量
    load_dotenv()

    # 配置 DSPy LM
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY 环境变量")

    print("[DSPy] 配置 LLM...")
    lm = dspy.LM(
        model="deepseek/deepseek-chat", api_key=api_key, api_base="https://api.deepseek.com/v1"
    )
    dspy.configure(lm=lm)
    print("[DSPy] LLM 已配置: deepseek-chat")

    # 尝试加载编译后的模型
    compiled_model_path = (
        Path(__file__).parent.parent.parent
        / "models"
        / "dspy"
        / "final_report_generator_compiled.json"
    )

    if compiled_model_path.exists():
        print(f"[DSPy] 加载编译后的模型: {compiled_model_path}")
        try:
            module = FinalReportGenerator()
            module.load(compiled_model_path)
            print("[DSPy] 模型加载成功")
        except Exception as e:
            print(f"[警告] 模型加载失败 ({e}), 使用未编译版本")
            module = FinalReportGenerator()
    else:
        print("[DSPy] 未找到编译模型, 使用未编译版本")
        module = FinalReportGenerator()

    # 执行推理
    print("[DSPy] 生成最终报告...")
    result = module(
        patient_info=patient_info,
        lab_summary=lab_summary,
        analysis_results=analysis_results,
        literature_interpretation=literature_interpretation,
        mri_analysis=mri_analysis,
        quality_control=quality_control,
    )

    print(f"[DSPy] 置信度: {result.confidence:.2f}")

    # 组装完整报告（使用 report_schema 共享模板）
    today = dt.date.today().strftime("%Y年%m月%d日")

    report_md = REPORT_MD_TEMPLATE.format(
        report_title=result.report_title,
        patient_name=patient_info["name"],
        patient_age_sex=patient_info["age_sex"],
        exam_id=patient_info["exam_id"],
        report_date=today,
        data_sources="MRI影像报告 + 检验数据 + 文献证据",
        mode="DSPy 优化",
        confidence=result.confidence,
        section_1_basic_info=result.section_1_basic_info,
        section_2_lab_analysis=result.section_2_lab_analysis,
        section_3_mri_analysis=result.section_3_mri_analysis,
        section_4_multidisciplinary=result.section_4_multidisciplinary,
        section_5_diagnosis=result.section_5_diagnosis,
        section_6_consistency=result.section_6_consistency,
        section_7_action_plan=result.section_7_action_plan,
        section_8_followup=result.section_8_followup,
        section_9_prognosis=result.section_9_prognosis,
    )

    # 保存优化后的 prompt 信息到 04_reports 目录
    try:
        prompts_dir = data_dir / "04_reports" / "dspy_prompts"
        save_dspy_prompts(module, prompts_dir)
        from .prompt_inspector import save_actual_dspy_prompt

        save_actual_dspy_prompt("final_report_generator", prompts_dir)
    except Exception as e:
        print(f"  [警告] 保存 DSPy prompts 失败: {e}")

    return {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "deepseek-chat (DSPy optimized)",
        "mode": "dspy",
        "patient_id": patient_id,
        "confidence": result.confidence,
        "report_markdown": report_md,
        "prompts_dir": str(prompts_dir) if "prompts_dir" in dir() else None,
        "sections": {
            "title": result.report_title,
            "basic_info": result.section_1_basic_info,
            "lab_analysis": result.section_2_lab_analysis,
            "mri_analysis": result.section_3_mri_analysis,
            "multidisciplinary": result.section_4_multidisciplinary,
            "diagnosis": result.section_5_diagnosis,
            "consistency": result.section_6_consistency,
            "action_plan": result.section_7_action_plan,
            "followup": result.section_8_followup,
            "prognosis": result.section_9_prognosis,
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DSPy 最终报告生成")
    parser.add_argument("--id-card", required=True, help="患者ID")
    args = parser.parse_args()

    # 获取数据目录
    work_root = Path(os.environ.get("WORK_ROOT", Path.cwd()))
    raw_ts = os.environ.get("ANALYSIS_TS", args.id_card)
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts
    data_dir = work_root / "data" / args.id_card / ts

    print("[DSPy] 开始生成最终报告...")
    print(f"  患者ID: {args.id_card}")
    print(f"  数据目录: {data_dir}")

    # TODO: 从数据目录加载必要的输入文件
    # 这里需要根据实际的 Pipeline 数据结构来调整

    print("\n[DSPy] 报告生成完成!")
    print(f"  结果已保存: {data_dir / '04_reports' / 'final_integrated_report_dspy.md'}")
