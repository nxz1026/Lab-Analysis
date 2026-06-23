# 复杂度基线 (Complexity Baseline)

> ruff C901 / PLR0911 / PLR0912 / PLR0913 / PLR0915 / C408 全部启用,
> 通过 per-file-ignores 将历史入口函数标记为基线, 不阻断 PR, 但每个被忽略的函数必须在本文档登记。

## 启用规则 (`pyproject.toml`)

```toml
[tool.ruff.lint]
select = ["F", "I", "B", "SIM"]
extend-select = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915", "C408"]
```

| 规则 | 含义 | 默认阈值 |
|---|---|---|
| C901 | cyclomatic complexity | > 10 |
| PLR0911 | too many return statements | > 6 |
| PLR0912 | too many branches | > 12 |
| PLR0913 | too many arguments | > 5 |
| PLR0915 | too many statements | > 50 |
| C408 | unnecessary dict() / list() call | literal 优先 |

## per-file-ignores 当前范围

```toml
[tool.ruff.lint.per-file-ignores]
# === 应用入口 / 编排函数 ===
"lab_analysis/pipeline/run.py"          = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/pipeline/cli.py"          = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/pipeline/steps.py"        = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/__main__.py"              = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/ingest_data/__init__.py"     = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]

# === DSPy 训练 / 编译 ===
"lab_analysis/dspy_modules/lab_data_extractor.py"       = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/dspy_modules/literature_interpreter.py"  = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/dspy_modules/final_report_generator.py"   = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/dspy_modules/mri_analyzer.py"             = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/dspy_modules/multi_patient.py"            = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/literature_interpreter_dspy.py"           = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/qwen_vl_report_check_dspy.py"             = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]

# === 报告生成 ===
"lab_analysis/gen_final_report.py"          = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/gen_final_report_dspy.py"     = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/gen_final_report_pdf.py"      = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]

# === 单文件业务 ===
"lab_analysis/batch_vision_extract.py"      = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/quant_visualizer.py"          = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/quant_metrics.py"             = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/dashboard.py"                 = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/data_loader.py"               = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/data_analyzer.py"             = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/alert_generator.py"           = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/evidence_grader.py"           = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/feedback.py"                  = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0913", "PLR0915"]
"lab_analysis/organize_local_files.py"      = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/upload_to_feishu_backup.py"   = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/literature_filter.py"         = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/literature_searcher/__init__.py" = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/llm_client.py"                = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"lab_analysis/compare_report_modes.py"      = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]

# === 顶层脚本 ===
"examples/*.py"     = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"scripts/*.py"      = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"mcp_server/*.py"   = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"migrate_deid.py"   = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915"]
"tests/*.py"        = ["C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915", "C408"]
```

### P2-2: glob 范围说明 (ruff file-resolver 语义)

ruff 的 per-file-ignores glob 采用 [PEP 639 / file-Resolver 语义](https://docs.astral.sh/ruff/settings/#lint_per-file-ignores):

- **不递归**: `examples/*.py` 只匹配 `examples/` 顶层 `.py` 文件,
  **不包含** `examples/sub/dir.py` (需用 `examples/**/*.py` 才会递归).
- **不匹配目录**: `lab_analysis/ingest_data/__init__.py` 是精确路径,
  `lab_analysis/ingest_data/*.py` 才会匹配所有 ingest_data 子模块.
- **多模式叠加**: 同名规则可以分多行写, ruff 会合并. 例如下面都可以补在 TOML 里:
  - `"lab_analysis/dspy_modules/*.py"` — dspy_modules 下所有顶层文件
  - `"lab_analysis/**/__init__.py"` — 所有包的 `__init__.py` (递归)
- **路径分隔符**: Windows / Linux 都能用 `/`, ruff 内部统一规范化为 POSIX 路径.
- **新增包时检查**: 在 `lab_analysis/` 下新建子包后, 必须在下方表格记录该包下哪些文件需要 ignore.

P2-2 增补的细粒度 ignore 列表 (在 `pyproject.toml` `[tool.ruff.lint.per-file-ignores]` 中加入):

```toml
# === 详被忽略的子模块 ===
"lab_analysis/dashboard.py"                       = ["C901"]  # 只控 cyclomatic, PLR 留给重构
"lab_analysis/pipeline/steps.py"                  = ["PLR0913"]  # run_step 参数多是有意为之
"lab_analysis/ingest_data/_log.py"                = ["PLR0912"]  # Eager init 与 lazy init 两套分支
"lab_analysis/ingest_data/ocr.py"                = ["C901", "PLR0915"]  # SCNet 协议代码
"lab_analysis/literature_searcher/__init__.py"   = ["C901", "PLR0912"]
"lab_analysis/scoring_card/__init__.py"           = ["C901", "PLR0911"]
"lab_analysis/extract_lab_data.py"                = ["C901", "PLR0915"]
"examples/dspy_quant_eval.py"                     = ["C901"]
```

## 基线覆盖范围

P1-4 落地前 ruff 报 57 个复杂度错误。落地后:

| 来源 | 基线函数 | 计划重构窗口 |
|---|---|---|
| `pipeline/run.py::main` | C901 (46), PLR0915 (200+) | 跟随 P2-9 step 装饰器化 |
| `ingest_data/__init__.py::main` | C901 (35), PLR0915 (150+) | 拆 CLI 包装 + 核心函数 |
| `gen_final_report*.py::main` | C901 (20-25) | 拆 step |
| `dspy_modules/*` | C901 (15-18) | 拆 prompt 构建 / 编译 / fallback |
| `quant_visualizer.py::render_*` | C901 (15), PLR0913 (8) | 提取 matplotlib 子函数 |
| `examples/*.py` | C901 (8-12) | 教学示例, 不强拆 |
| `mcp_server/*.py` | C901 (11-15) | MCP 协议要求薄包装, 暂缓 |
| 其它 | 散点 | 跟随模块下一次大改 |

## 解锁策略

- 新增代码 (新文件 / 新函数) **不允许** 进入 per-file-ignores
- 每拆完一个基线函数, 必须:
  1. 从 `[tool.ruff.lint.per-file-ignores]` 删除对应条目
  2. 跑 `ruff check` 确认仍为 0 错误
  3. 在本文档"已重构"章节追加日期 + 函数名 + 新 cyclomatic
  4. 在 `git commit -m` 中引用本文档

## 已重构 (历史)

| 日期 | 函数 | 原 cyclomatic | 新 cyclomatic |
|---|---|---|---|
| 2026-06-23 | `mcp_server/quant_eval.py::run_quant_eval` (PLR0913+PLR0915) | 8/56 | per-file-ignore, 待 P3 重构 |

## 与 CI 的关系

`.github/workflows/tests.yml` 执行 `ruff check`, 当前返回 0 即为通过。
本文件变更须在 PR 描述中单独说明, 不能与业务代码混在一起提交。