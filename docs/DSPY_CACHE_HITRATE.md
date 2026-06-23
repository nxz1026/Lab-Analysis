# DSPy 编译缓存命中率埋点

## 目标

在不改变运行行为的前提下，统计每次 `run_dspy_xxx()` 加载编译模型时的
cache hit / miss / load_fail 比例，作为后续"是否值得重编译"的判断依据。

## 埋点模块

| 模块 | 文件 | 触发点 |
|---|---|---|
| `final_report_generator` | `lab_analysis/dspy_modules/final_report_generator.py` | `if compiled_model_path.exists(): ...` |
| `lab_data_extractor` | `lab_analysis/dspy_modules/lab_data_extractor.py` | 同上 |
| `mri_analyzer` | `lab_analysis/dspy_modules/mri_analyzer.py` | `if model_path and Path(model_path).exists(): ...` |
| `literature_interpreter` | `lab_analysis/dspy_modules/literature_interpreter.py` | 当前未启用编译缓存 (仅 `compile_interpreter()`) — 留作 N/A |

> `multi_patient.py` 不涉及单个模块的 compile cache。

## 指标文件

落盘位置: `logs/dspy_cache_metrics.json` (可通过 `DSPY_CACHE_METRICS_FILE`
环境变量覆盖)。

Schema:
```json
{
  "modules": {
    "<name>": {"hit": int, "miss": int, "load_fail": int}
  },
  "totals": {"hit": int, "miss": int, "load_fail": int}
}
```

## 查看与重置

```bash
python scripts/dspy_cache_stats.py            # 表格
python scripts/dspy_cache_stats.py --json     # 原始 JSON
python scripts/dspy_cache_stats.py --reset    # 清零
```

## 告警阈值 (建议)

| 指标 | 期望 | 行动 |
|---|---|---|
| 单模块 hit ≥ 90% | 健康 | 无 |
| 单模块 hit < 50% | 异常 | 排查 `models/dspy/*.json` 是否被删除/重命名 |
| `load_fail` > 0 | 异常 | 检查 .json 与当前模块签名是否兼容 (重新 `compile_xxx()`) |

## 在 CI 中如何接入

`.github/workflows/tests.yml` 已加入 `DSPy cache health (load_fail == 0)` 步骤:

```yaml
- name: DSPy cache health (load_fail == 0)
  run: |
    python -c "
    import json, sys, os
    p = 'logs/dspy_cache_metrics.json'
    if not os.path.exists(p):
        print('[OK] 无 metrics 文件, 跳过')
        sys.exit(0)
    m = json.load(open(p, encoding='utf-8'))
    fails = m.get('totals', {}).get('load_fail', 0)
    sys.exit(1 if fails > 0 else 0)
    "
```

gate 行为:
- metrics 文件不存在 → `[OK]` 跳过 (本轮没跑 DSPy)
- `load_fail == 0` → `[OK]` 通过
- `load_fail > 0` → `[FAIL]` 列出所有失败模块, 提示重 compile

配套测试: `tests/test_dspy_cache_metrics.py` (13 用例) 覆盖埋点 / 持久化 / 重置 / CLI / CI gate 逻辑。

## 设计权衡

- **进程内内存缓存 + 启动时落盘**: 避免每次埋点都重读 JSON，O(1) 写入。
- **原子写入 (tmp + replace)**: 多进程并发时不会出现半截 JSON。
- **不发送远端 metrics**: 默认纯本地，避免引入额外依赖。