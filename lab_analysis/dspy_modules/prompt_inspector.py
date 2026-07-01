"""
DSPy Prompt 提取工具

提供从 DSPy 模块中提取优化后的 prompt 信息的功能,包括:
- Signature 的 instructions
- 输入/输出字段描述
- Few-shot 示例 (demos)
- DSPy 内部生成的完整 prompt
- 从 LM history 中捕获实际发送给 LLM 的完整 prompt

保存的文件命名约定:
  - ``{module}_dspy_prompts.json``       — Signature + 字段 + demos 结构信息
  - ``{module}_dspy_prompts.md``          — 同上, Markdown 可读版
  - ``{module}_dspy_actual_prompt.txt``   — 实际发送给 LLM 的完整 prompt 文本
  - ``{module}_standard_prompt.txt``      — 标准模式 (非 DSPy) 的手写 prompt
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import _log
from .._phi_filter import strip_phi

logger = _log.get_logger(__name__)

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
        if hasattr(field, "json_schema_extra") and field.json_schema_extra:
            return field.json_schema_extra.get("desc", "") or field.json_schema_extra.get(
                "description", ""
            )
        if hasattr(field, "desc"):
            return str(field.desc) if field.desc else ""
        if hasattr(field, "description"):
            return str(field.description) if field.description else ""
        return ""
    except Exception:
        return ""


def extract_signature_info(signature) -> Dict[str, Any]:
    """提取 Signature 信息"""
    info: Dict[str, Any] = {
        "signature_name": getattr(signature, "__name__", "Unknown"),
        "docstring": safe_str(getattr(signature, "__doc__", ""), 500),
        "instructions": "",
        "input_fields": {},
        "output_fields": {},
    }
    try:
        instructions = getattr(signature, "instructions", None)
        if instructions is None and hasattr(signature, "__doc__"):
            instructions = signature.__doc__
        info["instructions"] = safe_str(instructions, 2000)
    except Exception as exc:
        logger.warning("extract_signature_info: instructions 提取失败: %s", exc)
    try:
        input_fields = getattr(signature, "input_fields", {}) or {}
        for name, field in input_fields.items():
            info["input_fields"][name] = extract_field_desc(field)
    except Exception as exc:
        logger.warning("extract_signature_info: input_fields 提取失败: %s", exc)
    try:
        output_fields = getattr(signature, "output_fields", {}) or {}
        for name, field in output_fields.items():
            info["output_fields"][name] = extract_field_desc(field)
    except Exception as exc:
        logger.warning("extract_signature_info: output_fields 提取失败: %s", exc)
    return info


def extract_demos_info(predictor) -> List[Dict[str, Any]]:
    """提取 predictor 中的 few-shot demos"""
    demos: list[Dict[str, Any]] = []
    try:
        demos_list = getattr(predictor, "demos", []) or []
        for i, demo in enumerate(demos_list):
            demo_dict: Dict[str, Any] = {}
            if hasattr(demo, "__dict__"):
                items = demo.__dict__.items()
            elif isinstance(demo, dict):
                items = demo.items()
            else:
                continue
            for key, value in items:
                if key.startswith("_"):
                    continue
                demo_dict[key] = safe_str(value, 300)
            if demo_dict:
                demo_dict["_demo_index"] = i + 1
                demos.append(demo_dict)
    except Exception as e:
        demos.append({"_error": f"提取 demos 失败: {safe_str(e, 200)}"})
    return demos


def extract_predictor_info(predictor, predictor_name: str = "predictor") -> Dict[str, Any]:
    """提取 predictor 完整信息"""
    info: Dict[str, Any] = {
        "predictor_name": predictor_name,
        "predictor_type": type(predictor).__name__,
        "num_demos": 0,
        "demos": [],
        "signature": {},
    }
    try:
        signature = getattr(predictor, "signature", None)
        if signature is not None:
            info["signature"] = extract_signature_info(signature)
    except Exception as e:
        info["signature"] = {"_error": safe_str(e, 200)}
    try:
        demos = extract_demos_info(predictor)
        info["demos"] = demos
        info["num_demos"] = len(demos)
    except Exception as e:
        info["demos"] = [{"_error": safe_str(e, 200)}]
    return info


def extract_module_prompts(module, module_name: str) -> Dict[str, Any]:
    """从 DSPy Module 提取所有 predictor 的 prompt 信息"""
    result: Dict[str, Any] = {
        "module_name": module_name,
        "module_type": type(module).__name__,
        "predictors": [],
        "total_demos": 0,
    }
    try:
        predictors = module.named_predictors() if hasattr(module, "named_predictors") else []
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
    input_fields = sig.get("input_fields", {})
    if input_fields:
        parts.append("--- Input Fields ---")
        for name, desc in input_fields.items():
            parts.append(f"- {name}: {desc}")
        parts.append("")
    output_fields = sig.get("output_fields", {})
    if output_fields:
        parts.append("--- Output Fields ---")
        for name, desc in output_fields.items():
            parts.append(f"- {name}: {desc}")
        parts.append("")
    demos = predictor_info.get("demos", [])
    if demos:
        parts.append(f"--- Few-shot Examples ({len(demos)}) ---")
        for i, demo in enumerate(demos, 1):
            parts.append(f"\n[Example {i}]")
            for k, v in demo.items():
                if k.startswith("_"):
                    continue
                parts.append(f"{k}: {v}")
        parts.append("")
    return "\n".join(parts)


def save_prompts_to_json(module_name: str, prompts_data: Dict, output_dir: Path) -> Path:
    """保存 prompt 信息到 JSON 文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{module_name}_dspy_prompts.json"
    with open(output_path, "w", encoding="utf-8") as f:
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
            lines.append("**Docstring**:")
            lines.append("```")
            lines.append(sig.get("docstring", ""))
            lines.append("```")
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
        demos = pred.get("demos", [])
        if demos:
            lines.append(f"### Few-shot 示例 ({len(demos)})")
            lines.append("")
            for i, demo in enumerate(demos, 1):
                lines.append(f"#### 示例 {i}")
                lines.append("")
                for k, v in demo.items():
                    if k.startswith("_"):
                        continue
                    lines.append(f"**{k}**:")
                    lines.append("```")
                    lines.append(str(v))
                    lines.append("```")
                    lines.append("")
        lines.append("---")
        lines.append("")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return output_path


def get_actual_dspy_prompt() -> str:
    """
    从 DSPy LM 历史中捕获最近一次调用的完整 Prompt。

    DSPy 内部将 Signature instructions + ChainOfThought 推理指令 + Few-shot demos
    组装为完整 prompt 后发送给 LLM，该完整 prompt 保存在 LM 的 history 中。
    此函数从 history[-1] 提取该完整 prompt。

    Returns:
        完整 prompt 文本；若无法获取则返回以 "[错误]" 开头的描述。
    """
    try:
        import dspy
    except ImportError:
        return "[错误] DSPy 未安装"
    try:
        lm = getattr(dspy.settings, "lm", None)
        if lm is None:
            return "[错误] DSPy LM 未配置，请先调用 dspy.configure(lm=...)"
        history = getattr(lm, "history", [])
        if not history:
            return "[错误] DSPy LM 历史为空，尚未执行任何推理调用"
        last_call = history[-1]
        prompt_sources = []
        if "prompt" in last_call:
            val = last_call["prompt"]
            if isinstance(val, str):
                prompt_sources.append(val)
            elif isinstance(val, (list, dict)):
                prompt_sources.append(json.dumps(val, ensure_ascii=False, indent=2))
        if "messages" in last_call:
            msgs = last_call["messages"]
            prompt_sources.append(json.dumps(msgs, ensure_ascii=False, indent=2))
        if "kwargs" in last_call and isinstance(last_call["kwargs"], dict):
            msgs = last_call["kwargs"].get("messages", [])
            if msgs:
                prompt_sources.append(json.dumps(msgs, ensure_ascii=False, indent=2))
        if prompt_sources:
            seen = set()
            parts = []
            for s in prompt_sources:
                key = s[:200]
                if key not in seen:
                    seen.add(key)
                    parts.append(s)
            return "\n\n======= 分隔线 =======\n\n".join(parts)
        return json.dumps(last_call, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        return f"[错误] 获取 DSPy prompt 时发生异常: {type(e).__name__}: {e}"


def save_actual_dspy_prompt(module_name: str, output_dir: Path) -> Optional[Path]:
    """
    保存 DSPy 最近一次调用的完整 Prompt 到文本文件。

    保存位置: ``{output_dir}/{module_name}_dspy_actual_prompt.txt``

    Args:
        module_name: 模块名称（用于文件名，如 ``literature_interpreter``）
        output_dir:   prompt 保存目录

    Returns:
        保存的文件路径；失败返回 None
    """
    try:
        prompt_text = get_actual_dspy_prompt()
        if prompt_text.startswith("[错误]"):
            logger.info(f"  [警告] {prompt_text}")
            return None
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{module_name}_dspy_actual_prompt.txt"
        # P0: 落盘前过滤 PHI
        output_path.write_text(strip_phi(prompt_text), encoding="utf-8")
        logger.info(f"  [保存] 完整 DSPy prompt 已保存 ({len(prompt_text)} 字符): {output_path}")
        return output_path
    except Exception as e:
        logger.info(f"  [警告] 保存实际 DSPy prompt 失败: {e}")
        return None
