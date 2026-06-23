# mypy baseline (2026-06-23)

## 扫描命令

```bash
python -m mypy lab_analysis/ --ignore-missing-imports --no-strict-optional
```

## 当前状态

- **扫描文件**: 71
- **错误数**: 0
- **涉及文件**: 0

## 历史错误类型分布

| 规则 | 数量 | 修复方式 |
|------|------|---------|
| misc (overload signature 不一致) | 1 | `patient_id.py` 统一 fallback 参数名 |
| assignment (str → float) | 4 | `data_loader.py` 显式 `dict[str, float \| str]` 注解 |
| var-annotated (空 dict 无注解) | 2 | `data_loader.py` / `literature_filter.py` 加 `list[dict[...]]` |
| attr-defined (DSPy / PIL stub) | 3 | `prompt_inspector.py` 用 `Dict[str, Any]`, `ocr.py` / `quant_visualizer.py` 用 `# type: ignore[attr-defined]` |
| index (动态 key) | 1 | `compare_report_modes.py` 改用 `f"{mode}_length"` 动态 key |
| arg-type (annotate xy 期望 float) | 1 | `quant_visualizer.py` 用 `enumerate` 代替 `zip(xs, y)` 给 x |
| call-arg (boxplot labels 弃用) | 1 | `analysis/charts.py` 改用 `tick_labels=` |
| misc (sum/divisor 类型推导) | 6 | `compare_report_modes.py` 加 `list[dict[str, Any]]` 注解 + `int(...)` 包裹 |

## 已清理

2026-06-23: 22 → 0 (修复 9 个文件中的 22 个错误)

## 演进策略

1. **当前阶段**: mypy 0 错误, 已纳入 CI gate (`.github/workflows/tests.yml`)
2. **未来强化**: 跟随 ruff strict 模式逐步收紧 `strict_optional`, `warn_unused_ignores`, `warn_redundant_casts`

## 与 CI 的关系

mypy 现在是 PR merge 必过项。任何 `# type: ignore` 新增必须在本文件登记理由与位置。