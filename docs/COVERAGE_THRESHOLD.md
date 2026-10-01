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

## ⚠️ 当前 CI 真实状态（2026-10-01 复测）

| 环节 | 状态 |
|---|---|
| `Lint (ruff check)` | ✅ **已通过**（退出码 0）。原 1365 项 → 现仅保留 1 项登记豁免（`_log.py` PLR0913，见 `COMPLEXITY_BASELINE.md`） |
| `Lint (ruff format --check)` | ❌ **仍红**：35 个文件未按 `ruff format` 格式化。**这是存量问题**——在改动前的 HEAD 上同样是 35 个，非本次引入 |
| `Static type check (mypy)` | — 未执行（被上一环节阻断） |
| `Audit DSPy compiled models` | — 未执行；修好 mtime 检查后预计会因模型过期而红，见 `UPGRADE_NOTES_2026-10.md` |
| `Test with pytest + coverage` | — 未执行 |

### 剩余一个门：`ruff format --check`

`tests.yml` 该步骤的注释写着「仓库已完成全量 format 迁移，严格阳断保证不再回退」，
但**实测 HEAD 上也有 35 个文件不合规**，该注释与事实不符。

处理方式二选一：

1. 跑一次 `python -m ruff format .` —— 一次性解决，但会产生一个覆盖 35 个文件的大 diff，
   **建议单独成一个 commit**，不要和审计修复混在一起，否则真实改动会被淹没。
2. 暂时把该步骤改为非阻断（如 `continue-on-error: true`），
   在注释里注明存量待清，避免它继续挡住 pytest。

> `ruff check` 已经绿了，但在 `ruff format` 这一步解决之前，pytest 仍然跑不到。
> **这是现在卡住 CI 的唯一环节。**

### `fail_under` 与实际覆盖率不一致

`pyproject.toml` 现为 `fail_under = 60`，而本文件历史演进记录停在 42% / 实际 43.83%。
**在 pytest 真正跑起来并产出 `coverage.xml` 之前，60 这个数字没有依据**；
若实际覆盖率仍接近 44%，pytest 步骤会因覆盖率不达标而红。
建议：先让 format 步骤通过、让 pytest 跑一次拿到真实数字，再决定 60 是保留还是回调。

## 配置文件位置

`pyproject.toml` 中（`fail_under` 现值 60，见上方说明）:

```toml
[tool.coverage.run]
branch = true
source = ["lab_analysis"]
omit = [
    "lab_analysis/__main__.py",
    "lab_analysis/cleanup_runs.py",
]

[tool.coverage.report]
# 当前生效门槛 60；历史演进 22.80% → 25% → 40% → 42%(2026-06) 已不再对应当前配置。
# 60 尚未经真实覆盖率验证（pytest 因 lint 红灯从未在 CI 执行），见上文。
fail_under = 60
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