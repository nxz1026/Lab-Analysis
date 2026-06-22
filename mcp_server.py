"""MCP server for Lab-Analysis — 暴露 6 个 tool 给 LLM agent 调用。

启动:
    # stdio 模式 (默认, 用于 Claude Desktop / Cursor / IDE)
    python mcp_server.py

Tool 列表:
    1. audit_dspy_models()        — 检查 4 个 DSPy compiled JSON 是否 STALE
    2. run_quant_eval(...)        — 跑 6 指标量化评估 (std vs dspy)
    3. list_patients()            — 列出 data/ 下所有 patient + 样本统计
    4. get_pipeline_status(...)   — 看指定 patient (可选 timestamp) 的 pipeline 运行状态
    5. trigger_dspy_recompile(...) — 触发增量/全量 DSPy 4 module recompile (subprocess)
    6. render_quant_trend(...)    — 用所有 quant_eval_report.json 渲染多 run trend PNG

依赖:
    pip install mcp  (>= 1.0)

客户端配置 (Claude Desktop):
    {
      "mcpServers": {
        "lab-analysis": {
          "command": "python",
          "args": ["e:/2026Workplace/Code/Lab-Analysis/mcp_server.py"]
        }
      }
    }
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

# 让 import 走项目根
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

# 业务模块 (项目内)
from lab_analysis.dspy_modules import multi_patient as mp  # noqa: E402
from lab_analysis.quant_metrics import (  # noqa: E402
    metric_confidence,
    metric_entity_f1,
    metric_entity_recall_breakdown,
    metric_failure_rate,
    metric_feedback_delta,
    metric_section_coverage,
)
from scripts import audit_dspy_models as audit_mod  # noqa: E402

mcp = FastMCP("lab-analysis")


# ============== Tool 1: audit_dspy_models ==============


@mcp.tool()
def audit_dspy_models() -> str:
    """检查 4 个 DSPy compiled JSON 是否 STALE (与源代码不同步)。

    返回 JSON 字符串:
        {
          "overall_up_to_date": bool,
          "stale_modules": [str, ...],
          "details": [
            {"module": str, "compiled_at": str, "source_commit": str,
             "is_up_to_date": bool, "reason": str}
          ]
        }
    """
    try:
        results = audit_mod.main()  # 不传 argv
        return json.dumps(results, ensure_ascii=False, indent=2)
    except SystemExit as e:
        # --ci 模式下 audit 失败会 sys.exit(1), 这里捕获
        return json.dumps(
            {
                "overall_up_to_date": False,
                "stale_modules": ["(see CLI exit)"],
                "details": [],
                "error": f"audit exit code = {e.code}",
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"overall_up_to_date": False, "error": str(e)},
            ensure_ascii=False,
            indent=2,
        )


# ============== Tool 2: run_quant_eval ==============


@mcp.tool()
def run_quant_eval(
    id_card: str,
    std_ts: str,
    dspy_ts: str,
    run_gate: bool = True,
    render_visual: bool = True,
    out_dir: str = "",
) -> str:
    """对 std + dspy 两次跑做 6 指标量化评估; 可选自动跑 gate 检查 + 生成可视化产物.

    Args:
        id_card: 脱敏患者 ID, 形如 "846552421134373347"
        std_ts:  std 模式时间戳, 形如 "20260620_175252"
        dspy_ts: dspy 模式时间戳, 形如 "20260620_175730"
        run_gate: True = 调 quant_eval_gate 跑阈值检查 (默认 True)
        render_visual: True = 生成 PNG + HTML 可视化到 out_dir (默认 True)
        out_dir: 可视化产物输出目录 (默认 = data/{id_card}/{dspy_ts}/04_reports)

    Returns:
        JSON 字符串, 含 6 个 metric + 可选 gate_result + 可选 artifacts 路径:
        {
          "id_card": str,
          "std_ts": str,
          "dspy_ts": str,
          "metrics": { ... 6 metrics ... },
          "gate": {
            "passed": bool,
            "n_passed": int,
            "n_failed": int,
            "n_skipped": int,
            "details": [...],
          } | None,
          "artifacts": {
            "json_path": str,
            "png_path": str | None,
            "html_path": str | None,
            "sidecar_path": str | None,
          }
        }
    """
    try:
        from lab_analysis.utils import WORK_ROOT  # noqa: PLC0415
        from lab_analysis.quant_metrics import (  # noqa: PLC0415
            metric_confidence,
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

        base = WORK_ROOT / "data" / id_card
        std_md = base / std_ts / "04_reports" / "final_integrated_report.md"
        dspy_json = base / dspy_ts / "04_reports" / "final_integrated_report.json"
        std_scoring_p = base / std_ts / "04_reports" / "scoring_card.json"
        feedback_p = base / "feedback.json"

        # 加载数据
        std_text = std_md.read_text(encoding="utf-8") if std_md.exists() else ""
        dspy_text = dspy_json.read_text(encoding="utf-8") if dspy_json.exists() else ""
        if dspy_json.exists():
            dspy_data = json.loads(dspy_text)
        else:
            dspy_data = {}
        std_scoring = (
            json.loads(std_scoring_p.read_text(encoding="utf-8"))
            if std_scoring_p.exists()
            else {}
        )
        feedback = (
            json.loads(feedback_p.read_text(encoding="utf-8"))
            if feedback_p.exists()
            else {}
        )
        dspy_sections = dspy_data.get("sections", {}) if dspy_data else {}

        metrics = {
            "entity_f1": metric_entity_f1(std_text, dspy_text),
            "section_coverage": metric_section_coverage(dspy_sections),
            "failure_rate": metric_failure_rate(dspy_data, dspy_sections),
            "entity_recall": metric_entity_recall_breakdown(std_text, dspy_text),
            "confidence": metric_confidence(dspy_data, std_scoring),
            "feedback_delta": metric_feedback_delta(feedback),
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
        if out_dir:
            artifact_dir = Path(out_dir)
        else:
            artifact_dir = base / dspy_ts / "04_reports"
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
                # evaluate() 返回 GateReport, n_passed/n_failed/n_skipped 只在 to_dict() 里
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

        # U5: 写 .latest.txt marker (Windows 不支持 symlink, 用文本占位指向最新 timestamp)
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


# ============== Tool 3: list_patients ==============


@mcp.tool()
def list_patients() -> str:
    """列出 data/ 下所有 patient + 样本统计 + std/dspy 配对。

    返回 JSON 字符串:
        {
          "n_patients": int,
          "n_total_samples": int,
          "n_dspy_samples": int,
          "n_std_samples": int,
          "per_patient": {patient_id: {"total": n, "dspy": n, "std": n}},
          "pairs": {patient_id: [[std_ts, dspy_ts], ...]}
        }
    """
    try:
        # 过滤: 只保留看起来像身份证号的 patient_id (15-18 位数字)
        # 防止 mri_dspy_prompts 这种模板目录被误当 patient
        all_pids = mp.list_patients()
        pids = [p for p in all_pids if p.isdigit() and 15 <= len(p) <= 18]
        s = mp.stats()
        # 从 stats 里只保留过滤后的 patient
        s["per_patient"] = {k: v for k, v in s["per_patient"].items() if k in pids}
        s["n_patients"] = len(pids)
        # 重计 n_total/n_dspy/n_std
        s["n_total_samples"] = sum(v["total"] for v in s["per_patient"].values())
        s["n_dspy_samples"] = sum(v["dspy"] for v in s["per_patient"].values())
        s["n_std_samples"] = sum(v["std"] for v in s["per_patient"].values())
        pairs: dict[str, list[list[str]]] = {}
        for pid in pids:
            pairs[pid] = [list(p) for p in mp.find_pairs(pid)]
        s["pairs"] = pairs
        s["filtered_out"] = [p for p in all_pids if p not in pids]
        return json.dumps(s, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps(
            {"error": str(e), "type": type(e).__name__},
            ensure_ascii=False,
            indent=2,
        )


# ============== Tool 4: get_pipeline_status ==============


@mcp.tool()
def get_pipeline_status(patient_id: str, timestamp: str = "") -> str:
    """看某 patient (可选 timestamp) 的 pipeline 运行状态。

    Args:
        patient_id: 脱敏身份证号, 形如 "846552421134373347"
        timestamp:  可选, 不传则看该 patient 最新一次 run;
                    传则看指定 ts 目录的详细状态.

    Returns:
        JSON 字符串, 描述各阶段产物存在性 + 报告长度 + confidence:
        {
          "patient_id": str,
          "timestamp": str | null,
          "available": bool,
          "stages": {
            "02_analyzed": bool,
            "03_literature": bool,
            "04_reports": bool,
            "final_report_md": bool,
            "final_report_json": bool,
            "scoring_card": bool,
            "dspy_prompts": bool,
          },
          "metrics": {
            "std_md_length": int | null,
            "dspy_json_length": int | null,
            "dspy_confidence": float | null,
            "n_sections": int | null,
          },
          "is_dspy_run": bool,
          "checked_at": str
        }
    """
    try:
        from lab_analysis.utils import WORK_ROOT  # noqa: PLC0415

        base = WORK_ROOT / "data" / patient_id
        if not base.is_dir():
            return json.dumps(
                {"patient_id": patient_id, "available": False, "error": "patient dir 不存在"},
                ensure_ascii=False,
                indent=2,
            )

        # 选 timestamp
        if not timestamp:
            timestamps = mp.list_timestamps(patient_id)
            if not timestamps:
                return json.dumps(
                    {
                        "patient_id": patient_id,
                        "timestamp": None,
                        "available": False,
                        "error": "该 patient 下没有 timestamp 目录",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            timestamp = timestamps[-1]  # 最新

        ts_dir = base / timestamp
        if not ts_dir.is_dir():
            return json.dumps(
                {"patient_id": patient_id, "timestamp": timestamp, "available": False, "error": "ts_dir 不存在"},
                ensure_ascii=False,
                indent=2,
            )

        rep = ts_dir / "04_reports"
        an = ts_dir / "02_analyzed"
        lit = ts_dir / "03_literature"

        md = rep / "final_integrated_report.md"
        js = rep / "final_integrated_report.json"
        sc = rep / "scoring_card.json"
        dp = rep / "dspy_prompts"

        std_md_length = len(md.read_text(encoding="utf-8")) if md.exists() else None
        dspy_json_length = len(js.read_text(encoding="utf-8")) if js.exists() else None

        dspy_confidence = None
        n_sections = None
        if js.exists():
            try:
                d = json.loads(js.read_text(encoding="utf-8"))
                dspy_confidence = d.get("confidence")
                sections = d.get("sections") or {}
                n_sections = len(sections)
            except (json.JSONDecodeError, AttributeError):
                pass

        sample = mp._build_sample(patient_id, timestamp)  # noqa: SLF001

        return json.dumps(
            {
                "patient_id": patient_id,
                "timestamp": timestamp,
                "available": True,
                "stages": {
                    "02_analyzed": an.is_dir(),
                    "03_literature": lit.is_dir(),
                    "04_reports": rep.is_dir(),
                    "final_report_md": md.exists(),
                    "final_report_json": js.exists(),
                    "scoring_card": sc.exists(),
                    "dspy_prompts": dp.is_dir(),
                },
                "metrics": {
                    "std_md_length": std_md_length,
                    "dspy_json_length": dspy_json_length,
                    "dspy_confidence": dspy_confidence,
                    "n_sections": n_sections,
                },
                "is_dspy_run": sample.is_dspy,
                "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"error": str(e), "type": type(e).__name__},
            ensure_ascii=False,
            indent=2,
        )


# ============== Tool 5: trigger_dspy_recompile ==============


@mcp.tool()
def trigger_dspy_recompile(force: bool = False, timeout_sec: int = 600) -> str:
    """触发 DSPy 4 module recompile (subprocess 调 examples/compile_all_dspy_modules_v2.py).

    Args:
        force: True = 强制全量重 compile (跳过 mtime 检测); False = 增量 (默认).
        timeout_sec: subprocess 超时秒数, 默认 600s (10 min).

    Returns:
        JSON 字符串:
        {
          "started_at": str,
          "finished_at": str,
          "elapsed_sec": float,
          "returncode": int,
          "force": bool,
          "stdout_tail": str (最后 50 行),
          "stderr_tail": str (最后 20 行),
          "ok": bool
        }
    """
    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    t0 = time.time()
    try:
        cmd = [sys.executable, str(PROJECT_ROOT / "examples" / "compile_all_dspy_modules_v2.py")]
        if force:
            cmd.append("--force")
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(PROJECT_ROOT),
            check=False,
            env={**__import__("os").environ},  # 传递当前 env (含 DEEPSEEK_API_KEY)
        )
        elapsed = round(time.time() - t0, 2)
        return json.dumps(
            {
                "started_at": started,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "elapsed_sec": elapsed,
                "returncode": proc.returncode,
                "force": force,
                "ok": proc.returncode == 0,
                "stdout_tail": "\n".join(proc.stdout.splitlines()[-50:]),
                "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
            },
            ensure_ascii=False,
            indent=2,
        )
    except subprocess.TimeoutExpired as e:
        elapsed = round(time.time() - t0, 2)
        return json.dumps(
            {
                "started_at": started,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "elapsed_sec": elapsed,
                "returncode": -1,
                "ok": False,
                "error": f"timeout after {timeout_sec}s",
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        elapsed = round(time.time() - t0, 2)
        return json.dumps(
            {
                "started_at": started,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "elapsed_sec": elapsed,
                "returncode": -1,
                "ok": False,
                "error": str(e),
                "type": type(e).__name__,
            },
            ensure_ascii=False,
            indent=2,
        )


# ============== Tool 6: render_quant_trend ==============


@mcp.tool()
def render_quant_trend(patient_id: str = "", out_dir: str = "", x_key: str = "std_ts") -> str:
    """把所有 quant_eval_report.json (1+ 个) 串成多 run trend PNG.

    Args:
        patient_id: 不传则全 patient 混排; 传则只取该 patient.
        out_dir: PNG 输出目录 (默认 = data/{patient_id or '_all'}/trend/).
        x_key: X 轴 label 来源 (std_ts / dspy_ts / deid).

    Returns:
        JSON 字符串:
        {
          "n_reports": int,
          "x_key": str,
          "png_path": str | None,
          "report_ids": [str, ...]
        }
    """
    try:
        from lab_analysis.utils import WORK_ROOT  # noqa: PLC0415
        from lab_analysis.quant_visualizer import render_trend_chart  # noqa: PLC0415

        base = WORK_ROOT / "data"
        reports: list[dict] = []
        report_ids: list[str] = []
        if base.is_dir():
            for pdir in sorted(base.iterdir()):
                if not pdir.is_dir() or not pdir.name.isdigit():
                    continue
                if patient_id and pdir.name != patient_id:
                    continue
                for ts in sorted(pdir.iterdir()):
                    if not ts.is_dir():
                        continue
                    rj = ts / "04_reports" / "quant_eval_report.json"
                    if not rj.exists():
                        continue
                    try:
                        rep = json.loads(rj.read_text(encoding="utf-8"))
                        reports.append(rep)
                        report_ids.append(f"{pdir.name}/{ts.name}")
                    except (json.JSONDecodeError, OSError):
                        continue

        if not reports:
            return json.dumps(
                {"n_reports": 0, "x_key": x_key, "png_path": None,
                 "report_ids": [], "error": "no quant_eval_report.json found"},
                ensure_ascii=False, indent=2,
            )

        png_bytes = render_trend_chart(reports, x_key=x_key)
        out_base = Path(out_dir) if out_dir else (
            base / (patient_id or "_all") / "trend"
        )
        out_base.mkdir(parents=True, exist_ok=True)
        png_path = out_base / "quant_eval_trend.png"
        png_path.write_bytes(png_bytes)
        return json.dumps(
            {"n_reports": len(reports), "x_key": x_key,
             "png_path": str(png_path), "report_ids": report_ids},
            ensure_ascii=False, indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"error": str(e), "type": type(e).__name__},
            ensure_ascii=False, indent=2,
        )


# ============== Entry ==============


if __name__ == "__main__":
    mcp.run()  # stdio transport 默认
