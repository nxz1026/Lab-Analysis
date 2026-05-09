"""
validators.py — 轻量级数据验证，补充 bare except 和类型注解。
使用标准库 typing + 简单校验，不强制引入 Pydantic 依赖。
"""
from __future__ import annotations

import re
from typing import Any, Optional, List, Dict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationResult:
    """验证结果容器。"""
    ok: bool
    value: Any = None
    error: str = ""

    @classmethod
    def ok(cls, value: Any) -> "ValidationResult":
        return cls(ok=True, value=value)

    @classmethod
    def fail(cls, error: str) -> "ValidationResult":
        return cls(ok=False, error=error)


# ── 数值提取验证 ────────────────────────────────────────────────────

def extract_value(result_str: str) -> Optional[float]:
    """
    从检验结果字符串提取数值，支持 >10、<0.5、≤1.0 等格式。
    失败返回 None（不抛异常，保持原行为）。
    """
    if not result_str or not isinstance(result_str, str):
        return None
    s = result_str.strip().strip("*").strip()
    if s in ("—", "–", "-", "", "N/A", "NA", "null"):
        return None
    # 处理不等式前缀
    m = re.search(r"^[≤≥<>]+([^0-9].*?)?([0-9]+\.?\d*)", s)
    if m:
        try:
            return float(m.group(2))
        except (ValueError, IndexError):
            return None
    # 纯数字
    m = re.search(r"^([0-9]+\.?\d*)", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def extract_value_strict(result_str: str, field_name: str = "字段") -> ValidationResult:
    """
    严格版本的 extract_value，验证失败时返回 ValidationResult。
    用于需要明确知道是否成功的场景。
    """
    if not result_str or not isinstance(result_str, str):
        return ValidationResult.fail(f"{field_name}为空或类型错误")
    val = extract_value(result_str)
    if val is None:
        return ValidationResult.fail(f"{field_name}无法解析数值: {result_str!r}")
    return ValidationResult.ok(val)


# ── 路径安全验证 ────────────────────────────────────────────────────

def safe_path_join(base: Path, *parts: str, allow_create: bool = False) -> Path | None:
    """
    安全地拼接路径，防止路径穿越。
    返回拼接后的路径，如果非法则返回 None。
    """
    try:
        # 先 resolve，再拼接
        base_resolved = base.resolve()
        joined = base_resolved.joinpath(*parts).resolve()
        # 确保结果在 base 内部
        if not str(joined).startswith(str(base_resolved)):
            return None
        if allow_create:
            joined.parent.mkdir(parents=True, exist_ok=True)
        return joined
    except (OSError, ValueError):
        return None


# ── JSON 安全解析 ───────────────────────────────────────────────────

def safe_load_json(path: Path, default: Any = None) -> tuple[bool, Any]:
    """
    安全加载 JSON 文件，返回 (success, data)。
    不抛异常，失败时返回 default。
    """
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        return True, data
    except Exception:
        return False, default


# ── API Key 验证 ────────────────────────────────────────────────────

def validate_api_key(key: str | None, name: str) -> str:
    """
    验证 API Key 非空且格式正确。
    空或 None 抛出 ValueError。
    """
    if not key or not isinstance(key, str):
        raise ValueError(f"缺少 {name}，请检查环境变量或 .env 配置")
    key = key.strip()
    if len(key) < 8:
        raise ValueError(f"{name} 格式异常（太短），请检查是否正确配置")
    return key