"""
DSPy 版本的检验报告数据提取模块

使用 DSPy 框架优化 Vision 模型的 JSON 结构化提取质量
提高字段识别准确率和格式规范性
"""

from pathlib import Path
from typing import Optional

import dspy

from .. import _log
from ._cache_metrics import record_hit, record_load_fail, record_miss
from ._retry import SafeCallError, make_empty_prediction, safe_predict
from .prompt_inspector import extract_module_prompts, save_prompts_to_json, save_prompts_to_markdown

logger = _log.get_logger(__name__)


class LabDataExtractionSignature(dspy.Signature):
    """检验数据提取的输入输出签名"""

    image_description: str = dspy.InputField(desc="检验报告图片的文字描述或OCR初步结果")
    patient_id: str = dspy.OutputField(desc="患者身份证号（18位数字，最后一位可能是X）")
    report_date: str = dspy.OutputField(desc="报告日期（格式：YYYY-MM-DD）")
    report_type: str = dspy.OutputField(desc="报告类型：outpatient(门诊) 或 inpatient(住院)")
    department: str = dspy.OutputField(desc="科室名称")
    physician: str = dspy.OutputField(desc="送检医生姓名")
    diagnosis: str = dspy.OutputField(desc="临床诊断")
    wbc_value: Optional[float] = dspy.OutputField(desc="WBC 白细胞计数数值")
    wbc_unit: str = dspy.OutputField(desc="WBC 单位")
    wbc_ref_range: str = dspy.OutputField(desc="WBC 参考范围")
    rbc_value: Optional[float] = dspy.OutputField(desc="RBC 红细胞计数数值")
    rbc_unit: str = dspy.OutputField(desc="RBC 单位")
    rbc_ref_range: str = dspy.OutputField(desc="RBC 参考范围")
    hgb_value: Optional[float] = dspy.OutputField(desc="HGB 血红蛋白数值")
    hgb_unit: str = dspy.OutputField(desc="HGB 单位")
    hgb_ref_range: str = dspy.OutputField(desc="HGB 参考范围")
    plt_value: Optional[float] = dspy.OutputField(desc="PLT 血小板计数数值")
    plt_unit: str = dspy.OutputField(desc="PLT 单位")
    plt_ref_range: str = dspy.OutputField(desc="PLT 参考范围")
    crp_value: Optional[float] = dspy.OutputField(desc="CRP C反应蛋白数值")
    crp_unit: str = dspy.OutputField(desc="CRP 单位")
    crp_ref_range: str = dspy.OutputField(desc="CRP 参考范围")
    hs_crp_value: Optional[float] = dspy.OutputField(desc="hs-CRP 超敏C反应蛋白数值")
    hs_crp_unit: str = dspy.OutputField(desc="hs-CRP 单位")
    hs_crp_ref_range: str = dspy.OutputField(desc="hs-CRP 参考范围")
    confidence: float = dspy.OutputField(desc="提取置信度 (0.0-1.0)")
    extraction_notes: str = dspy.OutputField(desc="提取说明，记录不确定或有疑问的地方")


class LabDataExtractor(dspy.Module):
    """基于 DSPy 的检验数据提取器"""

    def __init__(self):
        super().__init__()
        self.extract = dspy.ChainOfThought(LabDataExtractionSignature)

    def forward(self, image_description: str):
        try:
            return safe_predict(
                self.extract, module_name="lab_data_extractor", image_description=image_description
            )
        except SafeCallError as exc:
            logger.error("lab_data_extractor fallback to empty prediction: %s", exc)
            return make_empty_prediction(LabDataExtractionSignature)

    def to_structured_dict(self, prediction) -> dict:
        """将提取结果转换为结构化字典"""
        metrics = {}
        indicator_fields = [
            ("WBC", "wbc"),
            ("RBC", "rbc"),
            ("HGB", "hgb"),
            ("PLT", "plt"),
            ("CRP", "crp"),
            ("hs-CRP", "hs_crp"),
        ]
        for name, prefix in indicator_fields:
            value_key = f"{prefix}_value"
            unit_key = f"{prefix}_unit"
            ref_key = f"{prefix}_ref_range"
            if hasattr(prediction, value_key) and getattr(prediction, value_key) is not None:
                metrics[name] = {
                    "value": getattr(prediction, value_key),
                    "unit": getattr(prediction, unit_key, ""),
                    "ref_range": getattr(prediction, ref_key, ""),
                }
        result = {
            "patient_id": prediction.patient_id,
            "report_date": prediction.report_date,
            "report_type": prediction.report_type,
            "department": prediction.department,
            "physician": prediction.physician,
            "diagnosis": prediction.diagnosis,
            "metrics": metrics,
            "confidence": prediction.confidence,
            "extraction_notes": prediction.extraction_notes,
        }
        return result


def compile_lab_extractor(train_data: list, dev_data: list):
    """
    编译和优化检验数据提取器

    Args:
        train_data: 训练数据集 (image_description -> structured_output)
        dev_data: 验证数据集

    Returns:
        优化后的模块
    """
    import dspy.teleprompt

    def extraction_accuracy_metric(example, pred, trace=None):
        """评估提取准确性的指标"""
        try:
            score = 0
            required_fields = ["patient_id", "report_date", "report_type"]
            present_fields = sum(
                (1 for field in required_fields if hasattr(pred, field) and getattr(pred, field))
            )
            score += present_fields / len(required_fields) * 0.4
            indicator_prefixes = ["wbc", "rbc", "hgb", "plt", "crp", "hs_crp"]
            has_indicators = any(
                (
                    hasattr(pred, f"{p}_value") and getattr(pred, f"{p}_value") is not None
                    for p in indicator_prefixes
                )
            )
            if has_indicators:
                score += 0.3
            if hasattr(pred, "confidence") and 0.5 <= pred.confidence <= 1.0:
                score += 0.2
            if hasattr(pred, "report_date"):
                date_str = pred.report_date
                if len(date_str) == 10 and date_str[4] == "-" and (date_str[7] == "-"):
                    score += 0.1
            return score >= 0.7
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.info(f"[警告] 评估失败: {e}")
            return False

    optimizer = dspy.teleprompt.BootstrapFewShot(metric=extraction_accuracy_metric)
    module = LabDataExtractor()
    compiled_module = optimizer.compile(student=module, trainset=train_data)
    return compiled_module


def save_dspy_prompts(module, output_dir: Path):
    """保存 DSPy 模块的优化 prompt 到磁盘"""
    prompts_data = extract_module_prompts(module, "lab_data_extractor")
    json_path = save_prompts_to_json("lab_data_extractor", prompts_data, output_dir)
    md_path = save_prompts_to_markdown("lab_data_extractor", prompts_data, output_dir)
    return (json_path, md_path)


def run_dspy_extraction(image_path: Path, initial_ocr_text: str = ""):
    """
    运行 DSPy 优化的检验数据提取

    Args:
        image_path: 检验报告图片路径
        initial_ocr_text: 初步 OCR 识别文本（可选）

    Returns:
        结构化的检验数据字典
    """
    import os

    import dspy
    from dotenv import load_dotenv

    load_dotenv()
    work_root = Path(os.environ.get("WORK_ROOT", Path.cwd()))
    api_key = os.environ.get("ZHIPU_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("未找到 ZHIPU_API_KEY 或 DEEPSEEK_API_KEY")
    logger.info("[DSPy] 配置 LLM...")
    lm = dspy.LM(
        model="deepseek/deepseek-chat", api_key=api_key, api_base="https://api.deepseek.com/v1"
    )
    dspy.configure(lm=lm)
    logger.info("[DSPy] LLM 已配置: deepseek-chat")
    compiled_model_path = (
        Path(__file__).parent.parent / "models" / "dspy" / "lab_extractor_compiled.json"
    )
    if compiled_model_path.exists():
        logger.info(f"[DSPy] 加载编译后的模型: {compiled_model_path}")
        try:
            module = LabDataExtractor()
            module.load(compiled_model_path)
            record_hit("lab_data_extractor")
            logger.info("[DSPy] 模型加载成功")
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            record_load_fail("lab_data_extractor")
            logger.info(f"[警告] 模型加载失败 ({e}), 使用未编译版本")
            module = LabDataExtractor()
    else:
        record_miss("lab_data_extractor")
        logger.info("[DSPy] 未找到编译模型, 使用未编译版本")
        module = LabDataExtractor()
    image_description = initial_ocr_text or f"检验报告图片: {image_path.name}"
    logger.info("[DSPy] 提取检验数据...")
    result = module(image_description=image_description)
    logger.info(f"[DSPy] 置信度: {result.confidence:.2f}")
    logger.info(f"[DSPy] 提取说明: {result.extraction_notes}")
    structured_data = module.to_structured_dict(result)
    try:
        prompts_dir = work_root / "data" / "lab_extractor_dspy_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        save_dspy_prompts(module, prompts_dir)
        from .prompt_inspector import save_actual_dspy_prompt

        save_actual_dspy_prompt("lab_data_extractor", prompts_dir)
        structured_data["prompts_dir"] = str(prompts_dir)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        logger.info(f"  [警告] 保存 DSPy prompts 失败: {e}")
    return structured_data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DSPy 检验数据提取")
    parser.add_argument("--image", required=True, help="检验报告图片路径")
    parser.add_argument("--ocr-text", default="", help="初步OCR识别文本")
    args = parser.parse_args()
    image_path = Path(args.image)
    logger.info("[DSPy] 开始提取检验数据...")
    logger.info(f"  图片: {image_path}")
    result = run_dspy_extraction(image_path, args.ocr_text)
    logger.info("\n[DSPy] 提取完成!")
    logger.info(f"  患者ID: {result['patient_id']}")
    logger.info(f"  报告日期: {result['report_date']}")
    logger.info(f"  指标数量: {len(result['metrics'])}")
    logger.info("  结果已保存")
