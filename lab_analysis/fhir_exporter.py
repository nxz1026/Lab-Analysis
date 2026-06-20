"""fhir_exporter.py — HL7 FHIR R4 Bundle 输出

将 Pipeline 分析结果映射为 FHIR R4 Bundle（type=collection），
包含 Patient / Observation / RiskAssessment / DiagnosticReport 资源。

用法:
    python -m lab_analysis.fhir_exporter --id-card <deid>
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path

from lab_analysis.utils import WORK_ROOT

# LOINC 编码映射（常用检验指标 → LOINC code + display）
_LOINC_MAP: dict[str, tuple[str, str]] = {
    "WBC":       ("6690-2",  "Leukocytes [Volume] in Blood"),
    "RBC":       ("789-8",   "Erythrocytes [Volume] in Blood"),
    "HGB":       ("718-7",   "Hemoglobin [Mass/Volume] in Blood"),
    "HCT":       ("4544-3",  "Hematocrit [Volume Fraction] of Blood"),
    "PLT":       ("777-3",   "Platelets [Volume] in Blood"),
    "MCV":       ("787-2",   "MCV [Volume] in Red Blood Cells"),
    "MCH":       ("785-6",   "MCH [Mass] in Red Blood Cells"),
    "MCHC":      ("786-4",   "MCHC [Mass/Volume] in Red Blood Cells"),
    "RDW-SD":    ("788-0",   "RBC Distribution Width [Entitic volume]"),
    "RDW-CV":    ("21000-5", "RBC Distribution Width [Ratio]"),
    "NEUT#":     ("751-8",   "Neutrophils [Cells/Volume] in Blood"),
    "LYMPH#":    ("731-0",   "Lymphocytes [Cells/Volume] in Blood"),
    "MONO#":     ("742-7",   "Monocytes [Cells/Volume] in Blood"),
    "EO#":       ("711-2",   "Eosinophils [Cells/Volume] in Blood"),
    "BASO#":     ("706-1",   "Basophils [Cells/Volume] in Blood"),
    "CRP":       ("1988-5",  "C reactive protein [Mass/Volume] in Serum or Plasma"),
    "hs-CRP":    ("30522-7", "C reactive protein [Mass/Volume] in Serum or Plasma by High sensitivity method"),
    "PCT":       ("33914-3", "Procalcitonin [Mass/Volume] in Serum or Plasma"),
    "MPV":       ("32604-5", "Platelet mean volume [Volume]"),
    "PDW":       ("777-3",   "Platelet distribution width"),
}


def _build_patient(deid: str) -> dict:
    return {
        "resourceType": "Patient",
        "id": deid,
        "identifier": [{
            "system": "urn:lab-analysis:deid",
            "value": deid,
        }],
        "meta": {"security": [{
            "code": "DEID",
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
            "display": "de-identified",
        }]},
    }


def _build_observation(
    obs_id: str,
    metric: str,
    value: float | None,
    unit: str,
    ref_low: float | None,
    ref_high: float | None,
    date: str | None = None,
) -> dict:
    loinc = _LOINC_MAP.get(metric, (None, metric))
    obs: dict = {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": loinc[0] or "unknown",
                "display": loinc[1],
            }],
            "text": metric,
        },
    }
    if value is not None:
        obs["valueQuantity"] = {
            "value": value,
            "unit": unit,
        }
    if ref_low is not None or ref_high is not None:
        rr: dict = {}
        if ref_low is not None:
            rr["low"] = {"value": ref_low}
        if ref_high is not None:
            rr["high"] = {"value": ref_high}
        obs["referenceRange"] = [rr]
    if date:
        obs["effectiveDateTime"] = date
    # 异常判断
    if value is not None and ref_low is not None and ref_high is not None:
        if value > ref_high:
            obs["interpretation"] = [{
                "coding": [{"code": "H", "display": "High"}]
            }]
        elif value < ref_low:
            obs["interpretation"] = [{
                "coding": [{"code": "L", "display": "Low"}]
            }]
    return obs


def _build_inflammation_observation(deid: str, labels: list[str], dates: list[str]) -> dict:
    """将炎症分期映射为 Observation。"""
    if not labels:
        return None
    latest_label = labels[-1]
    latest_date = dates[-1] if dates else None
    status_map = {"急性期": "acute", "过渡期": "transitional", "缓解期": "remission", "未知": "unknown"}
    obs: dict = {
        "resourceType": "Observation",
        "id": f"{deid}-inflammation-status",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "76437-3",
                "display": "Inflammation status",
            }],
            "text": "炎症分期",
        },
        "valueCodeableConcept": {
            "coding": [{
                "system": "urn:lab-analysis:inflammation-status",
                "code": status_map.get(latest_label, "unknown"),
                "display": latest_label,
            }],
            "text": latest_label,
        },
    }
    if latest_date:
        obs["effectiveDateTime"] = latest_date
    return obs


def _build_risk_assessment(deid: str, scoring_card: dict) -> dict:
    """将评分卡 top 假设映射为 RiskAssessment。"""
    hypotheses = scoring_card.get("top_hypotheses", [])
    predictions = []
    for h in hypotheses:
        predictions.append({
            "outcome": {"text": h["hypothesis"]},
            "probabilityDecimal": h["confidence"],
        })
    ra: dict = {
        "resourceType": "RiskAssessment",
        "id": f"{deid}-scoring-card",
        "status": "final",
        "prediction": predictions or [{"outcome": {"text": "无诊断假设"}, "probabilityDecimal": 0}],
    }
    dims = scoring_card.get("dimension_scores", {})
    if dims:
        ra["note"] = [{"text": "; ".join(f"{k}={v}" for k, v in dims.items())}]
    return ra


def _build_diagnostic_report(deid: str, obs_ids: list[str], scoring_card: dict,
                              report_md: str) -> dict:
    dr: dict = {
        "resourceType": "DiagnosticReport",
        "id": f"{deid}-integrated-report",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "11536-0",
                "display": "Integrated clinical report",
            }],
            "text": "综合临床诊断报告",
        },
        "result": [{"reference": f"Observation/{oid}"} for oid in obs_ids],
    }
    if scoring_card.get("top_hypotheses"):
        top = scoring_card["top_hypotheses"][0]
        dr["conclusion"] = f"{top['hypothesis']}（置信度 {top['confidence']:.0%}）"
        dr["conclusionCodeableConcept"] = {
            "coding": [{
                "system": "urn:lab-analysis:hypothesis",
                "code": top["hypothesis"][:50],
                "display": top["hypothesis"],
            }],
        }
    if report_md:
        dr["presentedForm"] = [{
            "contentType": "text/markdown",
            "data": base64.b64encode(report_md.encode()).decode(),
        }]
    return dr


def build_fhir_bundle(
    deid: str,
    analysis_results: dict,
    scoring_card: dict,
    alerts: list[dict],
    report_md: str = "",
    lab_metrics: list[dict] | None = None,
) -> dict:
    """构建 FHIR R4 Bundle（type=collection）。

    Args:
        deid: 脱敏患者 ID。
        analysis_results: _compute_stats() 输出的 results dict。
        scoring_card: build_scoring_card() 输出的评分卡。
        alerts: generate_alerts() 输出的告警列表。
        report_md: 最终报告 Markdown 文本。
        lab_metrics: 检验指标的 [{metric, value, unit, date}, ...] 列表。

    Returns:
        FHIR R4 Bundle dict，可序列化为 JSON。
    """
    from lab_analysis.analysis._base import REF_RANGES

    entry: list[dict] = []
    obs_ids = []

    # 1. Patient
    entry.append({"resource": _build_patient(deid)})

    # 2. Observations（来自 REF_RANGES 的指标）
    if lab_metrics:
        for lm in lab_metrics:
            metric = lm.get("metric", lm.get("name", ""))
            value = lm.get("value") if lm.get("value") is not None else lm.get("latest_value")
            unit = lm.get("unit") or "?"
            date = lm.get("date") or lm.get("report_date")
            ref = REF_RANGES.get(metric)
            ref_low, ref_high = ref if ref else (None, None)
            obs_id = f"{deid}-{metric.lower().replace('#', 'n').replace('_', '-')}"
            obs = _build_observation(obs_id, metric, value, unit, ref_low, ref_high, date)
            entry.append({"resource": obs})
            obs_ids.append(obs_id)

    # 2b. Alert Observations
    for i, alert in enumerate(alerts):
        alert_obs_id = f"{deid}-alert-{i}"
        alert_obs: dict = {
            "resourceType": "Observation",
            "id": alert_obs_id,
            "status": "final",
            "code": {
                "coding": [{
                    "system": "urn:lab-analysis:alert",
                    "code": alert.get("level", "INFO"),
                    "display": alert.get("source", "alert"),
                }],
                "text": f"Alert: {alert.get('level', '')} - {alert.get('metric', '')}",
            },
            "valueString": alert.get("message", ""),
        }
        entry.append({"resource": alert_obs})
        obs_ids.append(alert_obs_id)

    # 3. Inflammation Observation
    infl_obs = _build_inflammation_observation(
        deid,
        analysis_results.get("inflammation_classification", {}).get("labels", []),
        analysis_results.get("inflammation_classification", {}).get("report_dates", []),
    )
    if infl_obs:
        entry.append({"resource": infl_obs})
        obs_ids.append(infl_obs["id"])

    # 4. RiskAssessment
    if scoring_card:
        entry.append({"resource": _build_risk_assessment(deid, scoring_card)})

    # 5. DiagnosticReport
    if obs_ids or scoring_card:
        dr = _build_diagnostic_report(deid, obs_ids, scoring_card, report_md)
        entry.append({"resource": dr})

    bundle: dict = {
        "resourceType": "Bundle",
        "id": f"lab-analysis-{deid}",
        "type": "collection",
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "entry": entry,
    }
    return bundle


def _cli():
    import argparse

    parser = argparse.ArgumentParser(description="FHIR R4 Bundle 输出")
    parser.add_argument("--id-card", required=True, help="脱敏 ID")
    parser.add_argument("--out", default=None, help="输出 JSON 路径")
    args = parser.parse_args()

    import os
    raw_ts = os.environ.get("ANALYSIS_TS", "")
    ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or args.id_card)
    data_dir = WORK_ROOT / "data" / args.id_card / ts

    analyzed_dir = data_dir / "02_analyzed"
    reports_dir = data_dir / "04_reports"

    analysis_results = json.loads(
        (analyzed_dir / "analysis_results.json").read_text(encoding="utf-8")
    ) if (analyzed_dir / "analysis_results.json").exists() else {}

    scoring_card = json.loads(
        (reports_dir / "scoring_card.json").read_text(encoding="utf-8")
    ) if (reports_dir / "scoring_card.json").exists() else {}

    alerts = json.loads(
        (analyzed_dir / "alerts.json").read_text(encoding="utf-8")
    ) if (analyzed_dir / "alerts.json").exists() else []

    report_md = (reports_dir / "final_integrated_report.md").read_text(encoding="utf-8") \
        if (reports_dir / "final_integrated_report.md").exists() else ""

    # 从 lab_metrics.json 读取检验数据
    lab_metrics = []
    lm_path = analyzed_dir / "lab_metrics.json"
    if lm_path.exists():
        lm_data = json.loads(lm_path.read_text(encoding="utf-8"))
        lab_metrics = lm_data.get("reports", lm_data.get("records", []))

    bundle = build_fhir_bundle(
        args.id_card, analysis_results, scoring_card, alerts, report_md, lab_metrics,
    )

    out_path = args.out or str(reports_dir / "fhir_bundle.json")
    Path(out_path).write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] FHIR Bundle 已保存: {out_path}")


if __name__ == "__main__":
    _cli()
