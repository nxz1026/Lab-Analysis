#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文献解读模块 - DSPy 增强版

支持传统 Prompt 工程和 DSPy 优化两种模式
用法: python literature_interpreter_dspy.py --patient-id <ID> [--use-dspy]
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))


def run_standard_mode(args):
    """运行标准 Prompt 工程模式"""
    from lab_analysis.literature_interpreter import build_prompt, call_deepseek
    
    print("[标准] 构建 prompt...")
    prompt = build_prompt(args.analysis, args.lit)
    
    print("[标准] 调用 DeepSeek...")
    response = call_deepseek(prompt)
    
    output = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "deepseek-chat",
        "mode": "standard",
        "prompt_preview": prompt[:500] + "...",
        "response": response,
    }
    
    return output


def run_dspy_mode(args):
    """运行 DSPy 优化模式"""
    try:
        import dspy
        from dotenv import load_dotenv
        
        # 加载环境变量
        load_dotenv()
        
        # 配置 DSPy LM
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            raise ValueError("未找到 DEEPSEEK_API_KEY 环境变量")
        
        print("[DSPy] 配置 LLM...")
        lm = dspy.LM(
            model='deepseek/deepseek-chat',
            api_key=api_key,
            api_base='https://api.deepseek.com/v1'
        )
        dspy.configure(lm=lm)
        print(f"[DSPy] LLM 已配置: deepseek-chat")
        
        from lab_analysis.dspy_modules import LiteratureInterpreterModule
        
        print("[DSPy] 加载分析结果...")
        with open(args.analysis, 'r', encoding='utf-8') as f:
            analysis_results = json.load(f)
        
        print("[DSPy] 加载文献结果...")
        with open(args.lit, 'r', encoding='utf-8') as f:
            literature_results = json.load(f)
        
        # 提取患者ID
        patient_id = args.patient_id or "unknown"
        
        print(f"[DSPy] 创建模块实例 (患者ID: {patient_id})...")
        module = LiteratureInterpreterModule()
        
        print("[DSPy] 执行推理...")
        result = module(
            patient_id=patient_id,
            analysis_results=analysis_results,
            literature_results=literature_results
        )
        
        output = {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "model": "deepseek-chat (DSPy optimized)",
            "mode": "dspy",
            "patient_id": patient_id,
            "interpretation": result.interpretation,
            "confidence": result.confidence,
        }
        
        print(f"[DSPy] 置信度: {result.confidence:.2f}")
        print(f"[DSPy] 生成长度: {len(result.interpretation)} 字符")
        
        return output
        
    except ImportError as e:
        print(f"[错误] DSPy 模块导入失败: {e}")
        print("请安装 DSPy: pip install dspy-ai")
        sys.exit(1)
    except Exception as e:
        print(f"[错误] DSPy 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="文献解读模块 (DSPy 增强版)")
    parser.add_argument("--analysis", type=str, default=None,
                        help="analysis_results.json 路径")
    parser.add_argument("--lit", type=str, default=None,
                        help="literature_results.json 路径")
    parser.add_argument("--out", type=str, default=None,
                        help="输出 JSON 路径")
    parser.add_argument("--patient-id", type=str, default=None, 
                        help="诊疗卡号，设置后自动推导路径")
    parser.add_argument("--use-dspy", action="store_true", 
                        help="使用 DSPy 优化版本")
    args = parser.parse_args()
    
    # 自动路径推断
    wiki_data = WORK_ROOT / "data"
    if args.patient_id:
        raw_ts = os.environ.get("ANALYSIS_TS", "")
        ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or args.patient_id)
        lit_dir = wiki_data / args.patient_id / ts / "03_literature"
        args.analysis = args.analysis or str(lit_dir.parent / "02_analyzed" / "analysis_results.json")
        args.lit = args.lit or str(lit_dir / "literature_results.json")  # 修正文件名
        args.out = args.out or str(lit_dir / "literature_interpretation.json")
    else:
        args.analysis = args.analysis or str(wiki_data / "analysis_results.json")
        args.lit = args.lit or str(wiki_data / "literature_results.json")
        args.out = args.out or str(wiki_data / "literature_interpretation.json")
    
    # 前置检查
    for label, path in [("analysis_results", args.analysis), ("literature_results", args.lit)]:
        if path and not Path(path).exists():
            print(f"[错误] 前置文件不存在: [{label}] {path}")
            sys.exit(1)
    
    # 选择执行模式
    mode_name = "DSPy 优化" if args.use_dspy else "标准 Prompt"
    print(f"\n{'='*60}")
    print(f"文献解读 - {mode_name} 模式")
    print(f"{'='*60}\n")
    
    if args.use_dspy:
        output = run_dspy_mode(args)
    else:
        output = run_standard_mode(args)
    
    # 保存结果
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 同时写人类可读的 Markdown 版本
    md_path = Path(args.out).with_suffix(".md")
    interpretation_text = output.get("response") or output.get("interpretation", "")
    md_content = f"# 循证医学解读报告\n\n**生成时间**: {output['generated']}\n**模型**: {output['model']}\n**模式**: {output.get('mode', 'unknown')}\n\n---\n\n{interpretation_text}\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    print(f"\n[成功] 文献解读完成 → {args.out}")
    print(f"[报告] Markdown 已保存: {md_path}")
    

if __name__ == "__main__":
    main()
