"""mcp_server.patient — list_patients + get_pipeline_status tools"""

from __future__ import annotations

import json
import re
import time

from lab_analysis.dspy_modules import multi_patient as mp

from . import mcp


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
    _PATIENT_RE = re.compile(r"^[A-Za-z0-9_-]{15,50}$")
    _TEMPLATE_KEYWORDS = re.compile(r"(dspy|prompts?|template|test)", re.IGNORECASE)
    try:
        # 过滤: 匹配 base64url 脱敏 ID 模式 (字母数字+下划线+连字符, 15-50 字符)
        # 并排除包含已知模板关键词的目录名
        all_pids = mp.list_patients()
        pids = [p for p in all_pids if _PATIENT_RE.match(p) and not _TEMPLATE_KEYWORDS.search(p)]
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
            _TS_RE = re.compile(r"^\d{8}_\d{6}$")
            timestamps = [t for t in mp.list_timestamps(patient_id) if _TS_RE.match(t)]
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
                {
                    "patient_id": patient_id,
                    "timestamp": timestamp,
                    "available": False,
                    "error": "ts_dir 不存在",
                },
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

        std_md_length = md.stat().st_size if md.exists() else None
        dspy_json_length = js.stat().st_size if js.exists() else None

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

        sample = mp.build_sample(patient_id, timestamp)

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
