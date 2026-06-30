"""
文献解读模块 - DSPy 增强版

支持传统 Prompt 工程和 DSPy 优化两种模式
用法: python literature_interpreter_dspy.py --id-card <ID> [--use-dspy]
"""

import json
import os
from datetime import datetime
from pathlib import Path

from . import _log
from .config import WORK_ROOT

logger = _log.get_logger(__name__)


def run_standard_mode(args):
    """运行标准 Prompt 工程模式"""
    from lab_analysis.literature_interpreter import build_prompt, call_deepseek

    logger.info("[标准] 构建 prompt...")
    prompt = build_prompt(args.analysis, args.lit)
    prompts_dir = Path(args.out).parent / "dspy_prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    standard_prompt_path = prompts_dir / "literature_interpreter_standard_prompt.txt"
    with open(standard_prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)
    logger.info(f"[标准] 原始 prompt 已保存: {standard_prompt_path}")
    logger.info(f"[标准] prompt 长度: {len(prompt)} 字符")
    logger.info("[标准] 调用 DeepSeek...")
    response = call_deepseek(prompt)
    output = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "deepseek-chat",
        "mode": "standard",
        "prompt_preview": prompt[:500] + "...",
        "prompt_length": len(prompt),
        "prompt_path": str(standard_prompt_path),
        "response": response,
    }
    return output


def run_dspy_mode(args):
    """运行 DSPy 优化模式"""
    try:
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
        dspy.configure(lm=lm)
        logger.info("[DSPy] LLM 已配置: deepseek-chat")
        from lab_analysis.dspy_modules import LiteratureInterpreterModule

        logger.info("[DSPy] 加载分析结果...")
        with open(args.analysis, "r", encoding="utf-8") as f:
            analysis_results = json.load(f)
        logger.info("[DSPy] 加载文献结果...")
        with open(args.lit, "r", encoding="utf-8") as f:
            literature_results = json.load(f)
        patient_id = args.id_card or "unknown"
        logger.info(f"[DSPy] 创建模块实例 (患者ID: {patient_id})...")
        module = LiteratureInterpreterModule()
        compiled_model_path = (
            Path(__file__).parent.parent
            / "models"
            / "dspy"
            / "literature_interpreter_compiled.json"
        )
        if compiled_model_path.exists():
            logger.info(f"[DSPy] 加载编译模型: {compiled_model_path}")
            module.load(compiled_model_path)
            logger.info("[DSPy] 模型加载成功")
        else:
            logger.info("[DSPy] 未找到编译模型, 使用未编译版本")
        logger.info("[DSPy] 执行推理...")
        result = module(
            patient_id=patient_id,
            analysis_results=analysis_results,
            literature_results=literature_results,
        )
        logger.info(f"[DSPy] 置信度: {result.confidence:.2f}")
        logger.info(f"[DSPy] 生成长度: {len(result.interpretation)} 字符")
        prompts_dir = Path(args.out).parent / "dspy_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        try:
            from lab_analysis.dspy_modules.prompt_inspector import (
                extract_module_prompts,
                save_actual_dspy_prompt,
                save_prompts_to_json,
                save_prompts_to_markdown,
            )

            prompts_data = extract_module_prompts(module, "literature_interpreter")
            save_prompts_to_json("literature_interpreter", prompts_data, prompts_dir)
            save_prompts_to_markdown("literature_interpreter", prompts_data, prompts_dir)
            save_actual_dspy_prompt("literature_interpreter", prompts_dir)
            logger.info(
                f"[DSPy] 优化 prompt 已保存: {prompts_dir}/literature_interpreter_dspy_prompts.{{json,md}}"
            )
            logger.info(
                f"[DSPy] 完整 prompt 已保存: {prompts_dir}/literature_interpreter_dspy_actual_prompt.txt"
            )
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
            logger.info(f"[警告] 保存 DSPy prompts 失败: {e}")
        output = {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": "deepseek-chat (DSPy optimized)",
            "mode": "dspy",
            "patient_id": patient_id,
            "interpretation": result.interpretation,
            "confidence": result.confidence,
            "prompts_dir": str(prompts_dir),
        }
        return output
    except ImportError as e:
        logger.info(f"[错误] DSPy 模块导入失败: {e}")
        logger.info("请安装 DSPy: pip install dspy-ai")
        raise SystemExit(1)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        logger.info(f"[错误] DSPy 执行失败: {e}")
        import traceback

        traceback.print_exc()
        raise SystemExit(1)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="文献解读模块 (DSPy 增强版)")
    parser.add_argument("--analysis", type=str, default=None, help="analysis_results.json 路径")
    parser.add_argument("--lit", type=str, default=None, help="literature_results.json 路径")
    parser.add_argument("--out", type=str, default=None, help="输出 JSON 路径")
    parser.add_argument("--id-card", type=str, default=None, help="脱敏ID(由 pipeline 传入)")
    parser.add_argument("--use-dspy", action="store_true", help="使用 DSPy 优化版本")
    args = parser.parse_args()
    wiki_data = WORK_ROOT / "data"
    if args.id_card:
        raw_ts = os.environ.get("ANALYSIS_TS", "")
        ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts or args.id_card
        lit_dir = wiki_data / args.id_card / ts / "03_literature"
        args.analysis = args.analysis or str(
            lit_dir.parent / "02_analyzed" / "analysis_results.json"
        )
        args.lit = args.lit or str(lit_dir / "literature_results.json")
        args.out = args.out or str(lit_dir / "literature_interpretation.json")
    else:
        args.analysis = args.analysis or str(wiki_data / "analysis_results.json")
        args.lit = args.lit or str(wiki_data / "literature_results.json")
        args.out = args.out or str(wiki_data / "literature_interpretation.json")
    for label, path in [("analysis_results", args.analysis), ("literature_results", args.lit)]:
        if path and (not Path(path).exists()):
            logger.info(f"[错误] 前置文件不存在: [{label}] {path}")
            raise SystemExit(1)
    mode_name = "DSPy 优化" if args.use_dspy else "标准 Prompt"
    logger.info(f"\n{'=' * 60}")
    logger.info(f"文献解读 - {mode_name} 模式")
    logger.info(f"{'=' * 60}\n")
    output = run_dspy_mode(args) if args.use_dspy else run_standard_mode(args)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    md_path = Path(args.out).with_suffix(".md")
    interpretation_text = output.get("response") or output.get("interpretation", "")
    md_content = f"# 循证医学解读报告\n\n**生成时间**: {output['generated']}\n**模型**: {output['model']}\n**模式**: {output.get('mode', 'unknown')}\n\n---\n\n{interpretation_text}\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"\n[成功] 文献解读完成 → {args.out}")
    logger.info(f"[报告] Markdown 已保存: {md_path}")


if __name__ == "__main__":
    main()
