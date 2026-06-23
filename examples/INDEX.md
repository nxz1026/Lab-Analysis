# examples/ — 入口脚本索引

按用途分组, 每行: 文件名 + 一句简介 + 用法。

## DSPy 编译 (产线 model 输出)

| 文件 | 简介 | 用法 |
|---|---|---|
| [`compile_all_dspy_modules_v2.py`](compile_all_dspy_modules_v2.py) | **统一编译 4 个 DSPy module** (active)。v2 修复 BootstrapFewShot 训练样本数 + 注入 compiled_at metadata。CI / 本地都用这个。 | `python examples/compile_all_dspy_modules_v2.py` |
| [`compile_dspy_module.py`](compile_dspy_module.py) | 单独编译某个模块 (默认 literature_interpreter), 适合增量调优。 | `python examples/compile_dspy_module.py --module mri_analyzer` |
| [`compile_mri_analyzer_fix.py`](compile_mri_analyzer_fix.py) | 针对 mri_analyzer 的 bugfix 编译补丁, 一次性脚本。 | `python examples/compile_mri_analyzer_fix.py` |

> 历史 v1 (`compile_all_dspy_modules.py`) 已删除 (2026-06-23, P3-13), 用 v2 取代。

## DSPy 训练数据

| 文件 | 简介 | 用法 |
|---|---|---|
| [`collect_dspy_training_data.py`](collect_dspy_training_data.py) | 从 `data/<deid>/<ts>/04_reports/` 提取训练样本, 输出 JSON。 | `python examples/collect_dspy_training_data.py` |
| [`prepare_dspy_training_data.py`](prepare_dspy_training_data.py) | 上一步的 JSON 转为 dspy.Example 格式 (含 `.with_inputs(...)`)。 | `python examples/prepare_dspy_training_data.py` |

## DSPy 评估 / 对比 / 监控

| 文件 | 简介 | 用法 |
|---|---|---|
| [`dspy_quant_eval.py`](dspy_quant_eval.py) | 对编译后模型跑量化评估 (F1 / coverage / recall / confidence)。CI `quant_eval_gate` 也基于此。 | `python examples/dspy_quant_eval.py` |
| [`dspy_prompt_comparison.py`](dspy_prompt_comparison.py) | 跨多次编译产物对比 prompt 差异 (节流 + 找出 regression)。 | `python examples/dspy_prompt_comparison.py` |
| [`monitor_dspy_performance.py`](monitor_dspy_performance.py) | 监控模型调用延迟 / token 消耗 / 命中率, 输出 dashboard-friendly JSON。 | `python examples/monitor_dspy_performance.py` |
| [`dspy_quickstart.py`](dspy_quickstart.py) | 5 分钟跑通: 配置 → 一次推理 → 打印结果。适合新人 oncall。 | `python examples/dspy_quickstart.py` |

## 端到端 / 双模式对比

| 文件 | 简介 | 用法 |
|---|---|---|
| [`dual_mode_pipeline.py`](dual_mode_pipeline.py) | 同时跑 Standard + DSPy 模式, 输出对比 report。Pipeline `--compare-report-modes` 即此。 | `python examples/dual_mode_pipeline.py` |

## 一次性 Demo (含 LLM 调用, 默认需要 API key)

> 以下 6 个 demo 在 P3-13 重命名: `test_*.py` → `demo_*.py`, 避免被 pytest 误收集。

| 文件 | 简介 | 用法 |
|---|---|---|
| [`demo_dashscope_compatibility.py`](demo_dashscope_compatibility.py) | 验证阿里 DashScope SDK 与 DSPy 兼容 (Qwen-VL OCR 调用链)。 | `python examples/demo_dashscope_compatibility.py` |
| [`demo_dspy_basic.py`](demo_dspy_basic.py) | DSPy 模块最小可运行 demo (lm 配置 + 一次 forward)。 | `python examples/demo_dspy_basic.py` |
| [`demo_dspy_e2e.py`](demo_dspy_e2e.py) | DSPy 端到端 demo (4 module 串起来, 跑一次完整 pipeline)。 | `python examples/demo_dspy_e2e.py` |
| [`demo_dspy_llm.py`](demo_dspy_llm.py) | 仅验证 LM 配置 + 单次 call, 不走 DSPy module。 | `python examples/demo_dspy_llm.py` |
| [`demo_dspy_prompt_e2e.py`](demo_dspy_prompt_e2e.py) | 验证 DSPy 实际发送给 LLM 的 prompt 与本地预测一致。 | `python examples/demo_dspy_prompt_e2e.py` |
| [`demo_prompt_extraction.py`](demo_prompt_extraction.py) | 从 DSPy module 提取 signature / demos / 实际 prompt 落盘。 | `python examples/demo_prompt_extraction.py` |

## 命名约定

- `compile_*.py` — 改写 `models/dspy/*.json`, 算产线写入
- `demo_*.py` / `test_*.py`(已弃用) — 一次性调用 demo, **不** 写产线
- `collect_*.py` / `prepare_*.py` — 数据准备
- `dspy_*.py` / `monitor_*.py` — 评估 / 监控
- `dual_*.py` — 对比 / e2e

## 与 CI 的关系

CI 用的是 `scripts/audit_dspy_models.py --ci` (验 compiled models 与源码签名是否同步),
**不** 跑 examples/。examples/ 是本地 / 产线工具, 不进 PR gate。

## 清理历史

| 日期 | 变更 | 原因 |
|---|---|---|
| 2026-06-23 | 删除 `compile_all_dspy_modules.py` (v1, 351 行) | v2 含 metadata 注入 + BootstrapFewShot 修复, v2 是 active |
| 2026-06-23 | `test_*.py` → `demo_*.py` (6 个) | 避免 pytest 自动收集, 语义更清晰 (demo ≠ test) |
| 2026-06-23 | 添加本 INDEX.md | 让新人快速找到入口 |

## 风格约定

- 顶部必含 shebang `#!/usr/bin/env python3` + UTF-8 声明
- 模块 docstring 写明: 用途 / 输出 / 用法 / 依赖
- 读取 `.env` 用 `from dotenv import load_dotenv; load_dotenv()`
- API key 一律从 env 读, 不写死
- 写产线产物的脚本 (`compile_*`) 必须有 dry-run / backup 选项