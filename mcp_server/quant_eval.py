"""mcp_server.quant_eval — run_quant_eval tool"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import mcp


@mcp.tool()
def run_quant_eval(
    id_card: str,
    std_ts: str,
    dspy_ts: str,
    run_gate: bool = True,
    render_visual: bool = True,
    out_dir: str = "",
) -> str:
    """对 std + dspy 两次跑做 7 指标量化评估; 可选自动跑 gate 检查 + 生成可视化产物.

    Args:
        id_card: 脱敏患者 ID, 形如 "846552421134373347"
        std_ts:  std 模式时间戳, 形如 "20260620_175252"
        dspy_ts: dspy 模式时间戳, 形如 "20260620_175730"
        run_gate: True = 调 quant_eval_gate 跑阈值检查 (默认 True)
        render_visual: True = 生成 PNG + HTML 可视化到 out_dir (默认 True)
        out_dir: 可视化产物输出目录 (默认 = data/{id_card}/{dspy_ts}/04_reports)

    Returns:
        JSON 字符串, 含 7 个 metric + 可选 gate_result + 可选 artifacts 路径.
    """
    try:
        from lab_analysis.quant_metrics import (  # noqa: PLC0415
            metric_confidence,
            metric_cross_modality_consistency,
            metric_entity_f1,
            metric_entity_recall_breakdown,
            metric_failure_rate,
            metric_feedback_delta,
            metric_section_coverage,
        )
        from lab_analysis.quant_visualizer import (  # noqa: PLC0415
            render_metrics_chart,
            render_metrics_html,
        )
        from lab_analysis.utils import WORK_ROOT  # noqa: PLC0415

        base = WORK_ROOT / "data" / id_card
        std_md = base / std_ts / "04_reports" / "final_integrated_report.md"
        dspy_json = base / dspy_ts / "04_reports" / "final_integrated_report.json"
        std_scoring_p = base / std_ts / "04_reports" / "scoring_card.json"
        feedback_p = base / "feedback.json"

        # 加载数据
        std_text = std_md.read_text(encoding="utf-8") if std_md.exists() else ""
        dspy_text = dspy_json.read_text(encoding="utf-8") if dspy_json.exists() else ""
        dspy_data = json.loads(dspy_text) if dspy_json.exists() else {}
        std_scoring = (
            json.loads(std_scoring_p.read_text(encoding="utf-8")) if std_scoring_p.exists() else {}
        )
        feedback = json.loads(feedback_p.read_text(encoding="utf-8")) if feedback_p.exists() else {}
        dspy_sections = dspy_data.get("sections", {}) if dspy_data else {}

        metrics = {
            "entity_f1": metric_entity_f1(std_text, dspy_text),
            "section_coverage": metric_section_coverage(dspy_sections),
            "failure_rate": metric_failure_rate(dspy_data, dspy_sections),
            "entity_recall": metric_entity_recall_breakdown(std_text, dspy_text),
            "confidence": metric_confidence(dspy_data, std_scoring),
            "feedback_delta": metric_feedback_delta(feedback),
            "cross_modality_consistency": metric_cross_modality_consistency(
                dspy_sections,
                std_scoring,
            ),
        }

        result: dict = {
            "id_card": id_card,
            "std_ts": std_ts,
            "dspy_ts": dspy_ts,
            "text_lengths": {
                "std": len(std_text),
                "dspy": len(dspy_text),
            },
            "metrics": metrics,
            "gate": None,
            "artifacts": None,
        }

        # 可选: 写 json + 跑 gate + 渲染 visual
        artifact_dir = Path(out_dir) if out_dir else base / dspy_ts / "04_reports"
        artifact_dir.mkdir(parents=True, exist_ok=True)

        json_path = artifact_dir / "quant_eval_report.json"
        full_report = {
            "deid": id_card,
            "std_ts": std_ts,
            "dspy_ts": dspy_ts,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "text_lengths": result["text_lengths"],
            "metrics": metrics,
        }
        json_path.write_text(
            json.dumps(full_report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        png_path = None
        html_path = None
        if render_visual:
            try:
                chart_bytes = render_metrics_chart(metrics)
                png_path = artifact_dir / "quant_eval_chart.png"
                png_path.write_bytes(chart_bytes)
                html_str = render_metrics_html(full_report, chart_bytes=chart_bytes)
                html_path = artifact_dir / "quant_eval_report.html"
                html_path.write_text(html_str, encoding="utf-8")
            except Exception as e:
                png_path = None
                html_path = None
                result["visual_error"] = f"{type(e).__name__}: {e}"

        # 调 gate (subprocess 避免污染当前进程)
        sidecar_path = None
        if run_gate:
            try:
                from scripts.quant_eval_gate import evaluate  # noqa: PLC0415

                # evaluate() 期望 report dict (含 "metrics" key), 不是裸 metrics dict
                report_obj = evaluate({"metrics": metrics})
                gate_dict = report_obj.to_dict()
                sidecar = {
                    "passed": gate_dict["overall_pass"],
                    "n_total": gate_dict["n_total"],
                    "n_passed": gate_dict["n_passed"],
                    "n_failed": gate_dict["n_failed"],
                    "n_skipped": gate_dict["n_skipped"],
                    "details": gate_dict["results"],
                }
                result["gate"] = sidecar
                sidecar_path = artifact_dir / "quant_eval_gate_result.json"
                sidecar_path.write_text(
                    json.dumps(sidecar, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                result["gate_error"] = f"{type(e).__name__}: {e}"

        # U5: 写 .latest.txt marker
        try:
            latest_marker = artifact_dir / ".latest.txt"
            latest_marker.write_text(
                f"{dspy_ts}\n",
                encoding="utf-8",
            )
        except OSError:
            pass

        result["artifacts"] = {
            "json_path": str(json_path),
            "png_path": str(png_path) if png_path else None,
            "html_path": str(html_path) if html_path else None,
            "sidecar_path": str(sidecar_path) if sidecar_path else None,
            "latest_marker": str(artifact_dir / ".latest.txt"),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps(
            {"error": str(e), "type": type(e).__name__},
            ensure_ascii=False,
            indent=2,
        )
