#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy Prompt 提取工具

提供从 DSPy 模块中提取优化后的 prompt 信息的功能,包括:
- Signature 的 instructions
- 输入/输出字段描述
- Few-shot 示例 (demos)
- DSPy 内部生成的完整 prompt
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


def safe_str(obj: Any, max_length: int = 1000) -> str:
    """安全地将对象转为字符串,截断过长内容"""
    try:
        s = str(obj)
        if len(s) > max_length:
            return s[:max_length] + f"... [截断, 共 {len(s)} 字符]"
        return s
    except Exception:
        return f"<无法序列化: {type(obj).__name__}>"


def extract_field_desc(field) -> str:
    """安全提取字段描述"""
    try:
        if hasattr(field, 'json_schema_extra') and field.json_schema_extra:
            return field.json_schema_extra.get('desc', '') or field.json_schema_extra.get('description', '')
        if hasattr(field, 'desc'):
            return str(field.desc) if field.desc else ''
        if hasattr(field, 'description'):
            return str(field.description) if field.description else ''
        return ''
    except Exception:
        return ''


def extract_signature_info(signature) -> Dict:
    """提取 Signature 信息"""
    info = {
        "signature_name": getattr(signature, '__name__', 'Unknown'),
        "docstring": safe_str(getattr(signature, '__doc__', ''), 500),
        "instructions": "",
        "input_fields": {},
        "output_fields": {},
    }

    # 提取 instructions
    try:
        instructions = getattr(signature, 'instructions', None)
        if instructions is None and hasattr(signature, '__doc__'):
            instructions = signature.__doc__
        info["instructions"] = safe_str(instructions, 2000)
    except Exception:
        pass

    # 提取输入字段
    try:
        input_fields = getattr(signature, 'input_fields', {}) or {}
        for name, field in input_fields.items():
            info["input_fields"][name] = extract_field_desc(field)
    except Exception:
        pass

    # 提取输出字段
    try:
        output_fields = getattr(signature, 'output_fields', {}) or {}
        for name, field in output_fields.items():
            info["output_fields"][name] = extract_field_desc(field)
    except Exception:
        pass

    return info


def extract_demos_info(predictor) -> List[Dict]:
    """提取 predictor 中的 few-shot demos"""
    demos = []
    try:
        demos_list = getattr(predictor, 'demos', []) or []
        for i, demo in enumerate(demos_list):
            demo_dict = {}
            # demo 可能是 Example 对象或 dict
            if hasattr(demo, '__dict__'):
                items = demo.__dict__.items()
            elif isinstance(demo, dict):
                items = demo.items()
            else:
                continue

            for key, value in items:
                if key.startswith('_'):
                    continue
                demo_dict[key] = safe_str(value, 300)

            if demo_dict:
                demo_dict['_demo_index'] = i + 1
                demos.append(demo_dict)
    except Exception as e:
        demos.append({"_error": f"提取 demos 失败: {safe_str(e, 200)}"})

    return demos


def extract_predictor_info(predictor, predictor_name: str = "predictor") -> Dict:
    """提取 predictor 完整信息"""
    info = {
        "predictor_name": predictor_name,
        "predictor_type": type(predictor).__name__,
        "num_demos": 0,
        "demos": [],
        "signature": {},
    }

    # 提取 Signature
    try:
        signature = getattr(predictor, 'signature', None)
        if signature is not None:
            info["signature"] = extract_signature_info(signature)
    except Exception as e:
        info["signature"] = {"_error": safe_str(e, 200)}

    # 提取 demos
    try:
        demos = extract_demos_info(predictor)
        info["demos"] = demos
        info["num_demos"] = len(demos)
    except Exception as e:
        info["demos"] = [{"_error": safe_str(e, 200)}]

    return info


def extract_module_prompts(module, module_name: str) -> Dict:
    """从 DSPy Module 提取所有 predictor 的 prompt 信息"""
    result = {
        "module_name": module_name,
        "module_type": type(module).__name__,
        "predictors": [],
        "total_demos": 0,
    }

    try:
        # named_predictors() 返回模块内所有 predictor
        predictors = module.named_predictors() if hasattr(module, 'named_predictors') else []
        for name, predictor in predictors:
            pred_info = extract_predictor_info(predictor, name)
            result["predictors"].append(pred_info)
            result["total_demos"] += pred_info.get("num_demos", 0)
    except Exception as e:
        result["_error"] = f"提取 predictors 失败: {safe_str(e, 300)}"

    return result


def reconstruct_full_prompt(predictor_info: Dict) -> str:
    """根据 predictor 信息重建完整的 prompt(模拟 DSPy 内部格式)"""
    parts = []

    sig = predictor_info.get("signature", {})
    instructions = sig.get("instructions", "")
    if instructions:
        parts.append(f"--- Instructions ---\n{instructions}\n")

    # 输入字段
    input_fields = sig.get("input_fields", {})
    if input_fields:
        parts.append("--- Input Fields ---")
        for name, desc in input_fields.items():
            parts.append(f"- {name}: {desc}")
        parts.append("")

    # 输出字段
    output_fields = sig.get("output_fields", {})
    if output_fields:
        parts.append("--- Output Fields ---")
        for name, desc in output_fields.items():
            parts.append(f"- {name}: {desc}")
        parts.append("")

    # Few-shot demos
    demos = predictor_info.get("demos", [])
    if demos:
        parts.append(f"--- Few-shot Examples ({len(demos)}) ---")
        for i, demo in enumerate(demos, 1):
            parts.append(f"\n[Example {i}]")
            for k, v in demo.items():
                if k.startswith('_'):
                    continue
                parts.append(f"{k}: {v}")
        parts.append("")

    return "\n".join(parts)


def save_prompts_to_json(module_name: str, prompts_data: Dict, output_dir: Path) -> Path:
    """保存 prompt 信息到 JSON 文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{module_name}_dspy_prompts.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(prompts_data, f, ensure_ascii=False, indent=2)
    return output_path


def save_prompts_to_markdown(module_name: str, prompts_data: Dict, output_dir: Path) -> Path:
    """保存 prompt 信息到 Markdown 文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{module_name}_dspy_prompts.md"

    lines = [
        f"# {module_name} - DSPy 优化后 Prompt 详情",
        "",
        f"**模块类型**: `{prompts_data.get('module_type', 'Unknown')}`",
        f"**Predictor 总数**: {len(prompts_data.get('predictors', []))}",
        f"**Few-shot 示例总数**: {prompts_data.get('total_demos', 0)}",
        "",
    ]

    for pred in prompts_data.get("predictors", []):
        lines.append(f"## Predictor: `{pred.get('predictor_name', 'unknown')}`")
        lines.append("")
        lines.append(f"- **类型**: `{pred.get('predictor_type', 'Unknown')}`")
        lines.append(f"- **Few-shot 示例数**: {pred.get('num_demos', 0)}")
        lines.append("")

        sig = pred.get("signature", {})
        lines.append(f"### Signature: `{sig.get('signature_name', 'Unknown')}`")
        lines.append("")
        if sig.get("docstring"):
            lines.append(f"**Docstring**:")
            lines.append(f"```")
            lines.append(sig.get("docstring", ""))
            lines.append(f"```")
            lines.append("")

        if sig.get("instructions"):
            lines.append("**Instructions**:")
            lines.append("```")
            lines.append(sig.get("instructions", ""))
            lines.append("```")
            lines.append("")

        if sig.get("input_fields"):
            lines.append("**输入字段**:")
            for name, desc in sig.get("input_fields", {}).items():
                lines.append(f"- `{name}`: {desc}")
            lines.append("")

        if sig.get("output_fields"):
            lines.append("**输出字段**:")
            for name, desc in sig.get("output_fields", {}).items():
                lines.append(f"- `{name}`: {desc}")
            lines.append("")

        # Demos
        demos = pred.get("demos", [])
        if demos:
            lines.append(f"### Few-shot 示例 ({len(demos)})")
            lines.append("")
            for i, demo in enumerate(demos, 1):
                lines.append(f"#### 示例 {i}")
                lines.append("")
                for k, v in demo.items():
                    if k.startswith('_'):
                        continue
                    lines.append(f"**{k}**:")
                    lines.append(f"```")
                    lines.append(str(v))
                    lines.append(f"```")
                    lines.append("")

        lines.append("---")
        lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    return output_path