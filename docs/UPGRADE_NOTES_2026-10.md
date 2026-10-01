# 升级须知 (2026-10 审计修复)

本文件记录 2026-10-01 一次全量审计（24k 行 / 192 文件）与修复所带来的**行为变更**，
以及合并前**必须由维护者处理**的事项。

> 修复在**未部署环境、未运行测试套件**的前提下完成。验证手段为 ruff 静态检查、
> 针对单模块的直接调用、3.10 语法兼容扫描与全模块导入冒烟。
> **所有改动尚无回归保护，请先让 CI 的 pytest 真正跑起来。**
>
> 附：原 1365 项 lint 已逐项修复（`ruff check .` 退出码 0），详见下方第 3 节。

---

## 一、合并前必须处理（按优先级）

### 1. ⚠️ PHI：git 历史中仍含真实患者病历

`models/dspy/*_compiled.json` 的 few-shot 演示样本此前包含一位患者的完整纵向病历
（假名、检查号、四个精确采样日期、精确检验值、影像所见、慢性胰腺炎诊断）。
**工作区已替换为合成值，JSON 结构与 demos 保持合法**；但：

- 该仓库是**公开**的，历史提交（`d293aea` / `7c42ac6` / `34bdeb9`）中仍有原始内容。
- 从「罕见病 + 精确日期 + 精确检验值」的组合看，**这可能构成需要按 PIPL / HIPAA
  处理的隐私事件**，建议尽快评估并按流程处置。
- 彻底清除需要 `git filter-repo` 重写历史或轮换仓库——这是对外可见且难以撤销的操作，
  本次**未执行**，留给维护者决策。

### 2. 重新编译 DSPy 模型

`dspy_modules/*.py` 有改动、编译产物也做过脱敏，来源时间戳已落后于源码。
现在 `scripts/audit_dspy_models.py` 的过期检查（比较真实文件 mtime）已经真正生效，
CI 会在 pytest 之前就以「STALE」红掉。**这是正确信号，不是 bug。**

```bash
python examples/compile_all_dspy_modules_v2.py     # 用合成数据重新编译
python examples/compile_all_dspy_modules_v2.py --force
git add models/dspy && git commit                   # 与源码改动同一次提交
```

### 3. `ruff check` 已绿 ✅，但 `ruff format --check` 仍红

原 1365 项 lint 已**逐项修复**（不是基线豁免），`ruff check .` 现在退出码 0。
唯一保留的豁免是 `_log.py` 的 `PLR0913`——`add_file_handler` 是配置型 API
（2 个定位参数 + 4 个带默认值的 keyword-only 选项），并成 5 个会让调用端更难读，
已按 `COMPLEXITY_BASELINE.md` 的既有机制登记。

**但 CI 仍卡在下一个门：`ruff format --check` 有 35 个文件不合规。**
这是**存量问题**——改动前的 HEAD 上同样是 35 个，与本次修复无关
（`tests.yml` 里「已完成全量 format 迁移」的注释与事实不符）。

二选一：

1. 跑一次 `python -m ruff format .`。**建议单独成一个 commit**——它会改 35 个文件，
   和审计修复混在一起会让真实改动被淹没。
2. 暂把该步骤设为非阻断（`continue-on-error: true`）并注明存量待清。

> 在这一步解决前，pytest 仍然跑不到。这是现在卡住 CI 的**唯一**环节。

### 4. lint 修复中顺带发现并修掉的问题

- `scripts/cov_summary.py` 里**硬编码了某台机器的绝对路径**
  （`r"e:\...\Lab-Analysis\coverage.xml"`），换机器直接崩。已改为默认取仓库根目录下的
  `coverage.xml` 并支持命令行参数覆盖，文件缺失时给出可操作的提示。
  同时清掉了该文件里一处 `if False else 0` 的死代码。
- `llm_client.py` / `literature_searcher/pubmed.py` 原本从 `lab_analysis.utils` 取
  `api_retry_decorator`（`utils.py` 只是再导出）。删掉那个再导出会直接破坏这两个模块，
  已改为直接从 `lab_analysis.retry` 导入。
- `extract_lab_data/ocr.py` 的 `call_scnet_ocr` 复杂度超标（C901 11 / PLR0912 13），
  已拆成 `_prepare_upload` / `_post_ocr` / `_extract_text_lines` 三个函数，
  行为逐例验证与原实现一致。

---

## 二、行为变更（可能影响既有使用方式）

### `WORK_ROOT` 默认值变了

| | 之前 | 现在 |
|---|---|---|
| 未设 `WORK_ROOT` 时 | `Path.cwd()`（当前目录） | 项目根（含 `pyproject.toml` 的目录） |

**原因**：原先同一份代码从不同目录运行会解析出**不同的 `.hermes/master.key` 和不同的
`data/` 根**，而密钥缺失时是自动新建的（只 warn 不报错）——同一患者会得到两个不同的
`deid`、落在两棵互不可解密的树里。

**影响**：既有安装若数据在旧位置，需**显式设置 `WORK_ROOT`**。

### `metadata.md` 不再写明文身份证号

`raw/patient_<deid>/papers/lab_report_*/metadata.md` 的
`| 身份证号 | 110101... |` 已改为 `| 患者ID | <deid> |`。

- `pipeline/steps.py:extract_patient_id_from_reports()` 相应改为返回 **deid**。
- `pipeline/run.py:main()` 接受两种来源：从 `metadata.md` 自动识别出的 deid 直接使用；
  交互输入的明文走 `validate_id_card` + `get_deid`。

**重跑 pipeline 的注意事项**：自动识别分支拿不到明文身份证号，而**摄入需要它**
（要 OCR 校验报告归属）。因此重跑已摄入数据时会：

- 未指定 `--skip-ingest` → 打 warning 并跳过摄入；
- 显式指定了 `--ingest-*` 参数 → 直接报错退出（避免把 `None` 当 ID 传下去）。

需要重新摄入时，走交互输入身份证号的流程。

### 步骤⑦ 影像分析需要显式提供纸质报告文本

新增 `--report-text` / `--exam-id` / `--exam-date` / `--indication` / `--patient-desc`。
**不提供 `--report-text` 时只做纯影像描述、跳过印证**，输出 `cross_checked: false`。
详见 README「步骤⑦ 影像分析」。

> 此前模块内置了一份写死的病例报告（某患者检查号、年龄性别、肝/胰病灶）并无条件注入
> 每位患者的提示词与报告表头——任何一次非该患者的运行都会产出错归属的临床报告。

### 最终报告改读筛选后的文献

`gen_final_report.py` 现在优先读 `literature_results.filtered.json`
（evidence_grader 分级后的结果），没有则回退 `literature_results.json`。
此前两个 LLM 消费端都只读未筛选的 `all_papers`，**证据分级步骤对交付物完全无效**，
只有评分卡读筛选版。文件缺失时行为不变。

### MCP 工具的路径约束

- `run_quant_eval(out_dir=...)` / `render_quant_trend(out_base=...)` 现在要求
  解析后的路径位于 `WORK_ROOT` 之内，否则返回错误。`id_card` / `std_ts` / `dspy_ts`
  增加 `^[A-Za-z0-9_-]{1,64}$` 校验。
  （此前 LLM 可在任意可写路径建目录并覆写文件，无鉴权无审计。）
- `list_patients` 的脱敏 ID 过滤上界由 `{15,50}` 放宽为 `{1,64}`。
  真实 deid = base64url(12B nonce + 18B 明文 + 16B tag) = **62 字符**，
  原上界会把所有真实患者过滤掉，该工具恒返回 0 个患者。

### 评分卡现在真的会生成

`python -m lab_analysis.scoring_card` 此前必然 `ImportError`（`__main__.py` 导入
`main`，包内却只有 `_cli`）；pipeline 以 `fatal=False` 调用它，只打错误日志继续，
**评分卡从未生成**，FHIR 导出因此连带缺失 `RiskAssessment` 与
`DiagnosticReport.conclusion`。现已可正常运行。

### 评分卡维度极性

`inflammation`（炎症活动度）与 `lab_abnormality`（实验室异常度）是**越高越差**。
此前它们与另外三个「越高越好」的维度共用一套 emoji 阈值，导致最重的患者被标为
**「炎症活动度 100/100 ✅ 良好」**；置信度加权也把这两个维度正向加进了每个诊断假设
（炎症越重，「慢性胰腺炎（缓解期）」置信度越高）。现已按极性分别处理。

极性表见 `io._DIM_HIGHER_IS_BETTER` 与 `hypotheses._HIGHER_IS_WORSE`，
**新增维度时两处必须同步更新**。

### LLM 失败不再静默产出「格式完整正文为空」的报告

四个 DSPy 模块在 LLM 连续失败时会返回全零兜底预测，被照常套进完整报告模板落盘。
现在 `run_dspy_final_report` 会识别兜底结果，置 `degraded: true` 并在报告顶部加失败横幅。
下游可读 `final_integrated_report.json` 的 `degraded` 字段。

---

## 三、已修复但可能需要回归测试覆盖的点

以下问题都能被「测试全绿」掩盖，建议补测试：

| 点 | 原因 |
|---|---|
| FHIR `Observation.id` | 此前 `lab_metrics.json` 宽表被按窄表解析，导出**零条**检验数据；单测用的是窄表假数据。修复后 id 用 `sha256(metric\|date)[:8]` 消歧（`NEUT%` 与 `NEUT#` 同日不撞），长度 ≤47 |
| DSPy/标准模式 `analysis` 类型 | 统一为 `[{"text": ...}]`；消费端 `gen_final_report.py` 只认 list，此前 DSPy 分支写 str 会让**全部**影像证据退化成占位符 |
| `gen_final_report_dspy` 影像章节 | 读的是 `05_imaging/*.md`（DSPy 模式从不生成该文件）→ 恒为空；现改为优先读 `03_literature/*.md`，回退到 JSON 自行拼摘要 |
| 多篇文献解析边界 | `raw_lines[i-1]` 取的是全文第 i 行而非上一条 PMID 所在行，第 2 条起错位 31–35 字符，期刊名被截断、标题被摘要顶替 |
| `analysis_results_report.md` | 生产在 `04_reports/`，归档从 `02_analyzed/` 读 → 统计报告从未进入交付目录 |
| 患者归属 | `raw/` 下有多个病人目录时，旧逻辑返回「文件系统第一个」；现在发现多个不同 deid 会明确报错中止 |
| 摄入子进程超时 | 三处 `subprocess.run` 原本无 `timeout`，与 `run_step` 的 `PIPELINE_STEP_TIMEOUT` 语义不一致 |
| `score_imaging_consistency` | 未做报告印证时（`cross_checked: false`）返回中性 50，不再因「只记录成功项」而恒为 100 |

---

## 四、文档同步

- `docs/DOCSTRING_BASELINE.md` — 由 `python scripts/scan_docstrings.py` 重新生成
- `docs/COMPLEXITY_BASELINE.md` — 补登 `final_report_generator` / `gen_final_report_dspy` 新触发的规则
- `docs/COVERAGE_THRESHOLD.md` — 补「当前 CI 真实状态」小节；`fail_under` 现值 60
  未经真实覆盖率验证（pytest 因 lint 红灯从未在 CI 执行）
- `README.md` / `README_EN.md` — `WORK_ROOT` 默认值、单一来源、PHI 红线、步骤⑦ 新参数
