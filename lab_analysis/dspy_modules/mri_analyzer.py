"""
DSPy 版本的 MRI 影像分析模块

使用 DSPy 框架优化医学影像的结构化分析和报告印证质量
提高解剖定位准确性、所见描述规范性和印证评价可靠性
"""

import logging
import os
from pathlib import Path
from typing import Dict, List

import dspy

from .. import _log
from ._cache_metrics import record_hit, record_load_fail, record_miss
from ._retry import SafeCallError, make_empty_prediction, safe_predict
from .prompt_inspector import extract_module_prompts, save_prompts_to_json, save_prompts_to_markdown

logger = _log.get_logger(__name__)


class MRIAnalysisSignature(dspy.Signature):
    """MRI 影像分析的输入输出签名"""

    image_description: str = dspy.InputField(
        desc="影像的文字描述或序列信息 (如: T2WI横断面，代表层面)"
    )
    report_findings: str = dspy.InputField(desc="纸质放射科报告的关键发现段落")
    clinical_context: str = dspy.InputField(desc="临床背景信息 (患者年龄、性别、检查指征等)")
    anatomical_localization: str = dspy.OutputField(
        desc="解剖定位：明确指出这张图片大约在哪个层面（肝脏？胰腺？肾脏？其他？）"
    )
    imaging_findings: str = dspy.OutputField(
        desc="影像所见：详细描述可见的结构和信号特征，使用专业医学术语"
    )
    consistency_evaluation: str = dspy.OutputField(
        desc="印证评价：对照纸质报告描述，判断该影像表现是否与报告一致？选择：一致/不一致/补充，并说明理由"
    )
    additional_findings: str = dspy.OutputField(
        desc="补充发现：纸质报告未提及但影像可见的异常（如无则写'无显著补充发现'）"
    )
    confidence_score: float = dspy.OutputField(desc="置信度评分 (0.0-1.0)，反映分析的确定性程度")

    def validate_output(self) -> bool:
        """验证输出质量"""
        required_fields = ["anatomical_localization", "imaging_findings", "consistency_evaluation"]
        for field in required_fields:
            value = getattr(self, field, "")
            if not value or len(value.strip()) < 10:
                return False
        confidence = getattr(self, "confidence_score", 0)
        return 0.0 <= confidence <= 1.0


class MRIAnalysisModule(dspy.Module):
    """
    MRI 影像分析 DSPy 模块

    结合 Vision 模型的图像识别能力和 LLM 的医学推理能力,
    生成结构化的影像分析报告并与纸质报告进行印证
    """

    def __init__(self):
        super().__init__()
        self.predictor = dspy.ChainOfThought(MRIAnalysisSignature)

    def forward(
        self, image_description: str, report_findings: str, clinical_context: str
    ) -> dspy.Prediction:
        """
        执行 MRI 影像分析

        Args:
            image_description: 影像序列描述
            report_findings: 纸质报告关键发现
            clinical_context: 临床背景信息

        Returns:
            结构化分析结果
        """
        try:
            result = safe_predict(
                self.predictor,
                module_name="mri_analyzer",
                image_description=image_description,
                report_findings=report_findings,
                clinical_context=clinical_context,
            )
            return result
        except SafeCallError as exc:
            logging.getLogger(__name__).error("mri_analyzer fallback to empty prediction: %s", exc)
            return make_empty_prediction(MRIAnalysisSignature)


def compile_mri_analyzer(train_data: List[Dict], dev_data: List[Dict]):
    """
    编译和优化 MRI 分析模块

    Args:
        train_data: 训练数据集 (影像描述, 报告发现, 临床背景, 专家标注分析)
        dev_data: 验证数据集

    Returns:
        优化后的模块
    """
    import dspy.teleprompt

    def analysis_metric(example, pred, trace=None):
        """评估分析质量的指标"""
        try:
            score = 0.0
            required_sections = ["解剖定位", "影像所见", "印证评价"]
            full_text = (
                pred.anatomical_localization
                + " "
                + pred.imaging_findings
                + " "
                + pred.consistency_evaluation
            )
            section_score = sum((1 for section in required_sections if section in full_text)) / len(
                required_sections
            )
            score += section_score * 0.5
            if hasattr(pred, "confidence_score") and 0.6 <= pred.confidence_score <= 1.0:
                score += 0.3
            if len(full_text) > 200:
                score += 0.2
            return score > 0.7
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            return False

    optimizer = dspy.teleprompt.BootstrapFewShot(
        metric=analysis_metric, max_bootstrapped_demos=3, max_labeled_demos=5
    )
    logger.info("[编译] 开始优化 MRI 分析模块...")
    logger.info(f"       训练集: {len(train_data)} 样本")
    logger.info(f"       验证集: {len(dev_data)} 样本")
    compiled_module = optimizer.compile(MRIAnalysisModule(), trainset=train_data)
    logger.info("[成功] 模块编译完成")
    return compiled_module


def save_dspy_prompts(module, output_dir: Path):
    """保存 DSPy 模块的优化 prompt 到磁盘"""
    prompts_data = extract_module_prompts(module, "mri_analyzer")
    json_path = save_prompts_to_json("mri_analyzer", prompts_data, output_dir)
    md_path = save_prompts_to_markdown("mri_analyzer", prompts_data, output_dir)
    return (json_path, md_path)


def run_dspy_mri_analysis(
    image_desc: str, report_findings: str, clinical_context: str, model_path: str = None
):
    """
    运行 DSPy 优化的 MRI 分析

    Args:
        image_desc: 影像序列描述
        report_findings: 纸质报告关键发现
        clinical_context: 临床背景信息
        model_path: 编译后的模型路径 (可选)

    Returns:
        结构化分析结果字典
    """
    import dspy
    from dotenv import load_dotenv

    load_dotenv()
    work_root = Path(os.environ.get("WORK_ROOT", Path.cwd()))
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        raise ValueError("未找到 DASHSCOPE_API_KEY 环境变量")
    logger.info("[DSPy] 配置 LLM...")
    lm = dspy.LM(
        model="openai/qwen-vl-plus",
        api_key=api_key,
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    dspy.configure(lm=lm)
    logger.info("[DSPy] LLM 已配置: qwen-vl-plus (OpenAI 兼容模式)")
    module = MRIAnalysisModule()
    if model_path and Path(model_path).exists():
        logger.info(f"[加载] 从 {model_path} 加载编译模型...")
        try:
            module.load(model_path)
            record_hit("mri_analyzer")
            logger.info("[成功] 模型加载完成")
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            record_load_fail("mri_analyzer")
            logger.info(f"[警告] 模型加载失败 ({e}), 使用未编译版本")
    else:
        if model_path:
            record_miss("mri_analyzer")
    logger.info("[分析] 执行 MRI 影像分析...")
    result = module(
        image_description=image_desc,
        report_findings=report_findings,
        clinical_context=clinical_context,
    )
    output = {
        "anatomical_localization": result.anatomical_localization,
        "imaging_findings": result.imaging_findings,
        "consistency_evaluation": result.consistency_evaluation,
        "additional_findings": result.additional_findings,
        "confidence_score": result.confidence_score,
        "mode": "dspy_optimized",
    }
    logger.info(f"[成功] 分析完成 (置信度: {result.confidence_score:.2f})")
    try:
        prompts_dir = work_root / "data" / "mri_dspy_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        save_dspy_prompts(module, prompts_dir)
        from .prompt_inspector import save_actual_dspy_prompt

        save_actual_dspy_prompt("mri_analyzer", prompts_dir)
        output["prompts_dir"] = str(prompts_dir)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        logger.info(f"  [警告] 保存 DSPy prompts 失败: {e}")
    return output


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("DSPy MRI 分析模块测试")
    logger.info("=" * 60)
    test_image_desc = "T2WI横断面，肝脏层面，肝右后叶区域"
    test_report = "肝右后叶上段：长径约2.2cm异常信号影，T1稍低、T2及STIR稍高，\n增强少许点片状弱强化，考虑感染性病变，较前明显缩小"
    test_clinical = "男，38岁，胰管支架置入后复查，腹痛待查"
    try:
        result = run_dspy_mri_analysis(
            image_desc=test_image_desc, report_findings=test_report, clinical_context=test_clinical
        )
        logger.info("\n" + "=" * 60)
        logger.info("分析结果:")
        logger.info("=" * 60)
        for key, value in result.items():
            logger.info(f"{key}: {value}")
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        logger.info(f"[错误] 测试失败: {e}")
        import traceback

        traceback.print_exc()
