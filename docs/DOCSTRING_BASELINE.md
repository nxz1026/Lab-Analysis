# Docstring Coverage Baseline

扫描目标: `lab_analysis/`  (72 个 .py 文件)

## 总体统计

| 类别 | 有 docstring | 总数 | 覆盖率 |
|---|---:|---:|---:|
| 模块 | 72 | 72 | 100% |
| 类 | 14 | 15 | 93% |
| 顶层函数 | 234 | 297 | 78% |
| 方法 | 7 | 26 | 26% |
| **可调用合计** | **241** | **323** | **74%** |

## 覆盖率最低的 15 个文件

| 文件 | 总节点 | 有 docstring | 缺失 |
|---|---:|---:|---:|
| `lab_analysis\pipeline\context.py` | 12 | 3 | 9 |
| `lab_analysis\analysis\_compute.py` | 8 | 1 | 7 |
| `lab_analysis\dashboard.py` | 6 | 1 | 5 |
| `lab_analysis\dspy_modules\_cache_metrics.py` | 10 | 6 | 4 |
| `lab_analysis\dspy_modules\final_report_generator.py` | 11 | 7 | 4 |
| `lab_analysis\evidence_grader.py` | 12 | 8 | 4 |
| `lab_analysis\fhir_exporter.py` | 8 | 4 | 4 |
| `lab_analysis\analysis\_base.py` | 4 | 1 | 3 |
| `lab_analysis\literature_interpreter.py` | 5 | 2 | 3 |
| `lab_analysis\report_schema_models.py` | 12 | 9 | 3 |
| `lab_analysis\scoring_card\io.py` | 6 | 3 | 3 |
| `lab_analysis\dspy_modules\lab_data_extractor.py` | 10 | 8 | 2 |
| `lab_analysis\feedback.py` | 10 | 8 | 2 |
| `lab_analysis\gen_final_report.py` | 6 | 4 | 2 |
| `lab_analysis\gen_final_report_pdf.py` | 5 | 3 | 2 |

## 完整文件明细

| 文件 | 模块 | 类 doc | 函数 doc | 方法 doc |
|---|---:|---:|---:|---:|
| `lab_analysis\__init__.py` | 1/1 | 0/0 | 0/0 | 0/0 |
| `lab_analysis\__main__.py` | 1/1 | 0/0 | 0/0 | 0/0 |
| `lab_analysis\_log.py` | 1/1 | 0/0 | 3/3 | 0/0 |
| `lab_analysis\alert_generator.py` | 1/1 | 0/0 | 8/8 | 0/0 |
| `lab_analysis\analysis\__init__.py` | 1/1 | 0/0 | 0/0 | 0/0 |
| `lab_analysis\analysis\_base.py` | 1/1 | 0/0 | 0/3 | 0/0 |
| `lab_analysis\analysis\_compute.py` | 1/1 | 0/0 | 0/7 | 0/0 |
| `lab_analysis\analysis\charts.py` | 1/1 | 0/0 | 7/7 | 0/0 |
| `lab_analysis\analysis\run.py` | 1/1 | 0/0 | 4/4 | 0/0 |
| `lab_analysis\batch_vision_extract.py` | 1/1 | 0/0 | 5/6 | 0/0 |
| `lab_analysis\cleanup_runs.py` | 1/1 | 0/0 | 5/6 | 0/0 |
| `lab_analysis\compare_report_modes.py` | 1/1 | 0/0 | 7/7 | 0/0 |
| `lab_analysis\dashboard.py` | 1/1 | 0/0 | 0/5 | 0/0 |
| `lab_analysis\data_analyzer.py` | 1/1 | 0/0 | 0/0 | 0/0 |
| `lab_analysis\data_loader.py` | 1/1 | 0/0 | 7/8 | 0/0 |
| `lab_analysis\dspy_modules\__init__.py` | 1/1 | 0/0 | 0/0 | 0/0 |
| `lab_analysis\dspy_modules\_cache_metrics.py` | 1/1 | 0/0 | 5/9 | 0/0 |
| `lab_analysis\dspy_modules\_retry.py` | 1/1 | 1/1 | 3/3 | 0/0 |
| `lab_analysis\dspy_modules\final_report_generator.py` | 1/1 | 2/2 | 4/6 | 0/2 |
| `lab_analysis\dspy_modules\lab_data_extractor.py` | 1/1 | 2/2 | 4/4 | 1/3 |
| `lab_analysis\dspy_modules\literature_interpreter.py` | 1/1 | 2/2 | 4/4 | 1/2 |
| `lab_analysis\dspy_modules\mri_analyzer.py` | 1/1 | 2/2 | 4/4 | 2/3 |
| `lab_analysis\dspy_modules\multi_patient.py` | 1/1 | 1/1 | 9/9 | 0/0 |
| `lab_analysis\dspy_modules\prompt_inspector.py` | 1/1 | 0/0 | 11/11 | 0/0 |
| `lab_analysis\error_logger.py` | 1/1 | 0/0 | 6/6 | 0/0 |
| `lab_analysis\evidence_grader.py` | 1/1 | 0/1 | 7/9 | 0/1 |
| `lab_analysis\extract_lab_data\__init__.py` | 1/1 | 0/0 | 1/2 | 0/0 |
| `lab_analysis\extract_lab_data\ocr.py` | 1/1 | 0/0 | 2/2 | 0/0 |
| `lab_analysis\extract_lab_data\parser.py` | 1/1 | 0/0 | 3/3 | 0/0 |
| `lab_analysis\extract_lab_data\report.py` | 1/1 | 0/0 | 4/4 | 0/0 |
| `lab_analysis\feedback.py` | 1/1 | 0/0 | 7/9 | 0/0 |
| `lab_analysis\fhir_exporter.py` | 1/1 | 0/0 | 3/7 | 0/0 |
| `lab_analysis\gen_final_report.py` | 1/1 | 0/0 | 3/5 | 0/0 |
| `lab_analysis\gen_final_report_dspy.py` | 1/1 | 0/0 | 3/4 | 0/0 |
| `lab_analysis\gen_final_report_pdf.py` | 1/1 | 0/0 | 2/4 | 0/0 |
| `lab_analysis\ingest_data\__init__.py` | 1/1 | 0/0 | 0/1 | 0/0 |
| `lab_analysis\ingest_data\_log.py` | 1/1 | 0/0 | 1/1 | 0/0 |
| `lab_analysis\ingest_data\batch.py` | 1/1 | 0/0 | 2/2 | 0/0 |
| `lab_analysis\ingest_data\dicom.py` | 1/1 | 0/0 | 3/3 | 0/0 |
| `lab_analysis\ingest_data\lab.py` | 1/1 | 0/0 | 2/2 | 0/0 |
| `lab_analysis\ingest_data\report.py` | 1/1 | 0/0 | 1/1 | 0/0 |
| `lab_analysis\lab_prediction.py` | 1/1 | 0/0 | 3/3 | 0/0 |
| `lab_analysis\literature_filter.py` | 1/1 | 0/0 | 4/5 | 0/0 |
| `lab_analysis\literature_interpreter.py` | 1/1 | 0/0 | 1/4 | 0/0 |
| `lab_analysis\literature_interpreter_dspy.py` | 1/1 | 0/0 | 2/3 | 0/0 |
| `lab_analysis\literature_searcher\__init__.py` | 1/1 | 0/0 | 1/2 | 0/0 |
| `lab_analysis\literature_searcher\parser.py` | 1/1 | 0/0 | 2/2 | 0/0 |
| `lab_analysis\literature_searcher\pubmed.py` | 1/1 | 0/0 | 2/2 | 0/0 |
| `lab_analysis\literature_searcher\strategies.py` | 1/1 | 0/0 | 1/1 | 0/0 |
| `lab_analysis\llm_client.py` | 1/1 | 0/0 | 7/7 | 0/0 |
| `lab_analysis\organize_local_files.py` | 1/1 | 0/0 | 3/5 | 0/0 |
| `lab_analysis\patient_id.py` | 1/1 | 0/0 | 7/8 | 0/0 |
| `lab_analysis\pipeline\__init__.py` | 1/1 | 0/0 | 0/0 | 0/0 |
| `lab_analysis\pipeline\cli.py` | 1/1 | 0/0 | 3/4 | 0/0 |
| `lab_analysis\pipeline\context.py` | 1/1 | 1/1 | 0/0 | 1/10 |
| `lab_analysis\pipeline\ingest.py` | 1/1 | 0/0 | 1/1 | 0/0 |
| `lab_analysis\pipeline\run.py` | 1/1 | 0/0 | 1/2 | 0/0 |
| `lab_analysis\pipeline\steps.py` | 1/1 | 0/0 | 4/4 | 0/0 |
| `lab_analysis\pipeline.py` | 1/1 | 0/0 | 0/0 | 0/0 |
| `lab_analysis\quant_metrics.py` | 1/1 | 0/0 | 8/8 | 0/0 |
| `lab_analysis\quant_visualizer.py` | 1/1 | 0/0 | 4/4 | 0/0 |
| `lab_analysis\qwen_vl_report_check.py` | 1/1 | 0/0 | 1/3 | 0/0 |
| `lab_analysis\qwen_vl_report_check_dspy.py` | 1/1 | 0/0 | 3/4 | 0/0 |
| `lab_analysis\report_schema.py` | 1/1 | 0/0 | 1/1 | 0/0 |
| `lab_analysis\report_schema_models.py` | 1/1 | 3/3 | 3/3 | 2/5 |
| `lab_analysis\scoring_card\__init__.py` | 1/1 | 0/0 | 0/1 | 0/0 |
| `lab_analysis\scoring_card\dimensions.py` | 1/1 | 0/0 | 6/6 | 0/0 |
| `lab_analysis\scoring_card\hypotheses.py` | 1/1 | 0/0 | 4/6 | 0/0 |
| `lab_analysis\scoring_card\io.py` | 1/1 | 0/0 | 2/5 | 0/0 |
| `lab_analysis\scoring_card\types.py` | 1/1 | 0/0 | 0/0 | 0/0 |
| `lab_analysis\upload_to_feishu_backup.py` | 1/1 | 0/0 | 9/11 | 0/0 |
| `lab_analysis\utils.py` | 1/1 | 0/0 | 11/13 | 0/0 |

## 建议

- 短期：所有公共 API (`non-underscore` 函数/方法) 必须有 docstring。
- 中期：把 `interrogate` 加入 dev extras，设置 `--fail-under=70` 作为 CI 门槛。
- 长期：pre-commit 钩子拒绝新增未文档化的公共函数。
