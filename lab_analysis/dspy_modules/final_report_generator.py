"""
DSPy 版本的最终综合临床诊断报告生成模块

使用 DSPy 框架优化多源数据整合和报告生成的质量
"""

import datetime as dt
import os
from pathlib import Path

import dspy

from .. import _log
from ..report_schema import REPORT_MD_TEMPLATE, REPORT_SECTIONS
from ._cache_metrics import record_hit, record_load_fail, record_miss
from ._retry import SafeCallError, make_empty_prediction, safe_predict
from .prompt_inspector import extract_module_prompts, save_prompts_to_json, save_prompts_to_markdown

logger = _log.get_logger(__name__)


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
            logger.error(
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

    def report_quality_metric(example, pred, trace=None):
        """评估报告质量的指标"""
        try:
            score = 0
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
                (
                    1
                    for section in required_sections
                    if hasattr(pred, section) and getattr(pred, section)
                )
            )
            score += present_sections / len(required_sections) * 0.7
            if hasattr(pred, "confidence") and 0.5 <= pred.confidence <= 1.0:
                score += 0.2
            total_length = sum((len(getattr(pred, section, "")) for section in required_sections))
            if total_length > 2000:
                score += 0.1
            return score >= 0.7
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.info(f"[警告] 评估失败: {e}")
            return False

    optimizer = dspy.teleprompt.BootstrapFewShot(metric=report_quality_metric)
    module = FinalReportGenerator()
    compiled_module = optimizer.compile(student=module, trainset=train_data)
    return compiled_module


def save_dspy_prompts(module, output_dir: Path):
    """保存 DSPy 模块的优化 prompt 到磁盘"""
    prompts_data = extract_module_prompts(module, "final_report_generator")
    json_path = save_prompts_to_json("final_report_generator", prompts_data, output_dir)
    md_path = save_prompts_to_markdown("final_report_generator", prompts_data, output_dir)
    return (json_path, md_path)


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

    .. note::
        编译模型路径解析使用 ``importlib.resources``（包相对路径）作为首选方案，
        回退到基于 ``__file__`` 的路径。基于 ``__file__`` 的方案在打包为 wheel
        后可能失效，回退逻辑确保两种场景下都能正确加载模型文件。

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

    load_dotenv()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY 环境变量")
    logger.info("[DSPy] 配置 LLM...")
    lm = dspy.LM(
        model="deepseek/deepseek-chat", api_key=api_key, api_base="https://api.deepseek.com/v1"
    )
    # P0: 配置完成后立即清除内存中的 API key
    del api_key
    old_lm = getattr(dspy.settings, "lm", None)
    dspy.configure(lm=lm)
    logger.info("[DSPy] LLM 已配置: deepseek-chat")
    compiled_model_path: Path | None = None
    try:
        from importlib.resources import files as _pkg_files

        _model_ref = _pkg_files("lab_analysis").joinpath("models/dspy/final_report_generator_compiled.json")
        if _model_ref.is_file():
            compiled_model_path = Path(str(_model_ref))
    except Exception:
        pass
    if compiled_model_path is None:
        compiled_model_path = (
            Path(__file__).parent.parent.parent
            / "models"
            / "dspy"
            / "final_report_generator_compiled.json"
        )
    if compiled_model_path.exists():
        logger.info(f"[DSPy] 加载编译后的模型: {compiled_model_path}")
        try:
            module = FinalReportGenerator()
            module.load(compiled_model_path)
            record_hit("final_report_generator")
            logger.info("[DSPy] 模型加载成功")
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            record_load_fail("final_report_generator")
            logger.info(f"[警告] 模型加载失败 ({e}), 使用未编译版本")
            module = FinalReportGenerator()
    else:
        record_miss("final_report_generator")
        logger.info("[DSPy] 未找到编译模型, 使用未编译版本")
        module = FinalReportGenerator()
    try:
        logger.info("[DSPy] 生成最终报告...")
        result = module(
            patient_info=patient_info,
            lab_summary=lab_summary,
            analysis_results=analysis_results,
            literature_interpretation=literature_interpretation,
            mri_analysis=mri_analysis,
            quality_control=quality_control,
        )
        logger.info(f"[DSPy] 置信度: {result.confidence:.2f}")
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
    except Exception:
        raise
    else:
        try:
            prompts_dir = data_dir / "04_reports" / "dspy_prompts"
            save_dspy_prompts(module, prompts_dir)
            from .prompt_inspector import save_actual_dspy_prompt

            save_actual_dspy_prompt("final_report_generator", prompts_dir)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.info(f"  [警告] 保存 DSPy prompts 失败: {e}")
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
    finally:
        if old_lm is not None:
            dspy.configure(lm=old_lm)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="DSPy 最终报告生成")
    parser.add_argument("--id-card", required=True, help="患者ID")
    args = parser.parse_args()
    work_root = Path(os.environ.get("WORK_ROOT", Path.cwd()))
    raw_ts = os.environ.get("ANALYSIS_TS", args.id_card)
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts
    data_dir = work_root / "data" / args.id_card / ts
    logger.info("[DSPy] 开始生成最终报告...")
    logger.info(f"  患者ID: {args.id_card}")
    logger.info(f"  数据目录: {data_dir}")
    reports_dir = data_dir / "04_reports"
    patient_info_path = reports_dir / "patient_info.json"
    analysis_results_path = data_dir / "02_analyzed" / "analysis_results.json"
    literature_path = reports_dir / "literature_interpretation.md"
    mri_path = reports_dir / "mri_analysis.md"

    def _load_json_or_empty(p: Path) -> dict:
        if not p.exists():
            logger.warning(f"  缺失文件: {p}")
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as exc:
            logger.warning(f"  解析 {p.name} 失败: {exc}")
            return {}

    def _load_md_or_empty(p: Path, fallback: str = "") -> str:
        if not p.exists():
            logger.warning(f"  缺失文件: {p}")
            return fallback
        try:
            return p.read_text(encoding="utf-8")
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as exc:
            logger.warning(f"  读取 {p.name} 失败: {exc}")
            return fallback

    patient_info = _load_json_or_empty(patient_info_path) or {
        "name": args.id_card,
        "age_sex": "未知",
        "exam_id": ts,
    }
    analysis_results = _load_json_or_empty(analysis_results_path)
    literature_interpretation = _load_md_or_empty(literature_path, fallback="文献解读暂缺")
    mri_analysis = _load_md_or_empty(mri_path, fallback="影像数据暂缺")
    lab_summary = _load_md_or_empty(
        reports_dir / "lab_summary.md", fallback=str(analysis_results.get("summary", ""))
    )
    quality_control = _load_md_or_empty(
        reports_dir / "quality_control.md", fallback="一致性评估暂缺"
    )
    try:
        result = run_dspy_final_report(
            patient_id=args.id_card,
            data_dir=data_dir,
            patient_info=patient_info,
            lab_summary=lab_summary,
            analysis_results=analysis_results,
            literature_interpretation=literature_interpretation,
            mri_analysis=mri_analysis,
            quality_control=quality_control,
        )
        logger.info("[DSPy] 报告生成完成!")
        logger.info(f"  结果已保存: {data_dir / '04_reports' / 'final_integrated_report_dspy.md'}")
        logger.info(f"  置信度: {result.get('confidence', 'N/A')}")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as exc:
        logger.error(f"[DSPy] 报告生成失败: {exc}")
        raise SystemExit(1) from exc
