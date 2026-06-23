# 覆盖率门槛渐进 (Coverage Threshold)

## 目标

让覆盖率成为 PR merge 的硬约束, 同时避免一次性拉高 fail_under 导致开发体验崩溃。

## 演进

| 日期 | fail_under | 实际 | 缓冲 | 触发 |
|---|---|---|---|---|
| 2026-05 (P0 之前) | — | 22.80% | — | 基线 |
| 2026-06 初 (P0-2 后) | 25% | 26% | +1% | 起步门槛 |
| 2026-06-23 (P2-7) | 40% | 41.23% | +1.23% | P0/P1/P2-6 测试新增到位 |
| 2026-06-23 (P2-3) | 42% | 43.83% | +1.83% | P1-4/P1-5 fatal-cleanup + subprocess-timeout 测试覆盖 |

## 渐进策略

- **缓冲要求**: 实际覆盖率 ≥ fail_under + 1% 才允许提门槛, 避免 PR 边界 case 偶发 fail
- **每 PR 增长**: +2% (如 40 → 42 → 44 → ... → 60)
- **触发条件**: 每次新增或大改业务代码后, 同步补测试, 再提升门槛
- **不能跨越**: 不允许单次提 ≥ 5%, 必须有连续 PR 证明可持续

## 当前覆盖率结构 (2026-06-23 P2-3 后)

```
TOTAL: 43.83%  (5999 statements, 3370 miss, 1760 branch, 109 branch miss)
```

高分模块 (≥70%): 略, 见 `coverage.xml` 与 CI artifact  
低分模块 (<30%): 由 `--cov-report=term-missing` 列出 (CI 上传 `coverage-${{ matrix.python-version }}`)

## 配置文件位置

`pyproject.toml` 中:

```toml
[tool.coverage.run]
branch = true
source = ["lab_analysis"]
omit = [
    "lab_analysis/__main__.py",
    "lab_analysis/cleanup_runs.py",
]

[tool.coverage.report]
# CI 阈值渐进 (P2-7 → P2-3): 25% → 40% → 42%
# 历史: 22.80% (2026-05) → 25% (2026-06 初) → 40% (2026-06-23 P2-7) → 42% (2026-06-23 P2-3)
# 后续每 PR +2%, 但要求总覆盖大于阈值 +1 缓冲
fail_under = 42
show_missing = true
skip_covered = false
exclude_lines = [
    "pragma: no cover",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
    "\\.\\.\\.",
]
```

## CI 行为

`.github/workflows/tests.yml` 调用:

```yaml
- name: Test with pytest + coverage
  run: python -m pytest --cov=lab_analysis --cov-report=term-missing --cov-report=xml:coverage.xml --cov-branch
  env:
    LAB_DEID_KEY: "VW5..."
```

退出码非 0 → CI 红灯, 合并被阻断。

## 与 PR 流程的耦合

1. 提 PR → CI 跑 pytest --cov
2. coverage.xml 上传 artifact (Python 3.12)
3. 若 fail_under 红线 → 阻塞合并
4. 修复方式: 补测试 (推荐) 或在 PR 描述中申请 relax threshold (需说明理由, 仅临时)

## 历史 PR 记录 (后续填)

| 日期 | PR | fail_under 变化 | 实际 |
|---|---|---|---|
| — | — | — | — |