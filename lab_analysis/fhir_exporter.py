"""fhir_exporter.py — HL7 FHIR R4 Bundle 输出

将 Pipeline 分析结果映射为 FHIR R4 Bundle（type=collection），
包含 Patient / Observation / RiskAssessment / DiagnosticReport 资源。

用法:
    python -m lab_analysis.fhir_exporter --id-card <deid>
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path

from lab_analysis.utils import WORK_ROOT

from . import _log
from ._phi_filter import strip_phi

logger = _log.get_logger(__name__)

# LOINC 编码映射（常用检验指标 → LOINC code + display）
_LOINC_MAP: dict[str, tuple[str, str]] = {
    "WBC": ("6690-2", "Leukocytes [Volume] in Blood"),
    "RBC": ("789-8", "Erythrocytes [Volume] in Blood"),
    "HGB": ("718-7", "Hemoglobin [Mass/Volume] in Blood"),
    "HCT": ("4544-3", "Hematocrit [Volume Fraction] of Blood"),
    "PLT": ("777-3", "Platelets [Volume] in Blood"),
    "MCV": ("787-2", "MCV [Volume] in Red Blood Cells"),
    "MCH": ("785-6", "MCH [Mass] in Red Blood Cells"),
    "MCHC": ("786-4", "MCHC [Mass/Volume] in Red Blood Cells"),
    "RDW-SD": ("788-0", "RBC Distribution Width [Entitic volume]"),
    "RDW-CV": ("21000-5", "RBC Distribution Width [Ratio]"),
    "NEUT#": ("751-8", "Neutrophils [Cells/Volume] in Blood"),
    "LYMPH#": ("731-0", "Lymphocytes [Cells/Volume] in Blood"),
    "MONO#": ("742-7", "Monocytes [Cells/Volume] in Blood"),
    "EO#": ("711-2", "Eosinophils [Cells/Volume] in Blood"),
    "BASO#": ("706-1", "Basophils [Cells/Volume] in Blood"),
    "CRP": ("1988-5", "C reactive protein [Mass/Volume] in Serum or Plasma"),
    "hs-CRP": (
        "30522-7",
        "C reactive protein [Mass/Volume] in Serum or Plasma by High sensitivity method",
    ),
    "PCT": ("33914-3", "Procalcitonin [Mass/Volume] in Serum or Plasma"),
    "MPV": ("32604-5", "Platelet mean volume [Volume]"),
    "PDW": ("777-3", "Platelet distribution width [Entitic volume]"),  # TODO: 确认正确 LOINC 码
}


def _build_patient(deid: str) -> dict:
    return {
        "resourceType": "Patient",
        "id": deid,
        "identifier": [
            {
                "system": "urn:lab-analysis:deid",
                "value": deid,
            }
        ],
        "meta": {
            "security": [
                {
                    "code": "DEID",
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                    "display": "de-identified",
                }
            ]
        },
    }


_SLUG_KEEP = "-_"


def _slugify(text: str) -> str:
    """把指标名/日期压成 FHIR id 可用的安全片段 (FHIR id 限 ``[A-Za-z0-9\\-.]{1,64}``)。

    ⚠️ 必须限 ASCII: ``str.isalnum()`` 对中文也返回 True, 直接用会生成
    ``白细胞计数`` 这种非法 id。
    """
    out = []
    for ch in str(text):
        if (ch.isascii() and ch.isalnum()) or ch in _SLUG_KEEP:
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "x"


def _observation_id(deid: str, metric: str, date: str) -> str:
    """构造唯一且长度合规的 Observation.id。

    不能只用指标名: ``data_loader`` 对每份报告会同时写 ``NEUT%`` 与 ``NEUT#``
    (以及 LYMPH/MONO/EO/BASO 的 % 与 # 两列), 同一 report_date 下二者若都被
    slug 成 ``NEUT`` 就会在同一个 Bundle 里产生重复 id。而 slug 化本身是有损的
    (``%``/``#`` 都会被替换掉), 所以额外拼一个短哈希保证唯一。

    deid 本身就有 62 字符, 直接和 slug + 日期拼接会超出 64 上限, 故 deid 截断。
    """
    stamp = _slugify(date) if date else "na"
    key = f"{metric}|{date}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]
    return f"{_slugify(deid)[:20]}-{_slugify(metric)[:20]}-{_slugify(stamp)[:12]}-{digest}"


# 宽表行里的非指标列 (data_loader.to_csv/to_json 的 fixed_cols)
_REPORT_META_KEYS = frozenset(
    {
        "report_id",
        "report_date",
        "diagnosis",
        "department",
        "physician",
        "visit_type",
        "is_inpatient",
    }
)


def _pivot_lab_metrics(rows: list[dict] | None) -> list[dict]:
    """把检验指标统一成窄表 ``[{metric, value, unit, date}]``。

    生产侧 ``data_loader.to_json()`` 写出的 ``reports`` 是**宽表**: 每行一份报告,
    指标各占一列 (WBC / CRP / hs-CRP ... , 另有一列 ``<指标>_status``)。
    若按窄表解析, 每行都取不到 ``metric``/``value``, 导致 FHIR Bundle 里
    一条有效检验数据都没有, 而单测用的是窄表假数据所以一直发现不了。

    同时兼容本来就是窄表的输入 (含 ``metric`` / ``name`` 键)。
    """
    out: list[dict] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("metric") or row.get("name"):
            out.append(
                {
                    "metric": row.get("metric") or row.get("name", ""),
                    "value": row.get("value")
                    if row.get("value") is not None
                    else row.get("latest_value"),
                    "unit": row.get("unit") or "",
                    "date": row.get("date") or row.get("report_date") or "",
                }
            )
            continue
        date = row.get("report_date", "")
        for key, value in row.items():
            if key in _REPORT_META_KEYS or key.endswith("_status"):
                continue
            if value is None or value == "":
                continue
            out.append({"metric": key, "value": value, "unit": "", "date": date})
    return out


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
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": loinc[0] or "unknown",
                    "display": loinc[1],
                }
            ],
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
            obs["interpretation"] = [{"coding": [{"code": "H", "display": "High"}]}]
        elif value < ref_low:
            obs["interpretation"] = [{"coding": [{"code": "L", "display": "Low"}]}]
    return obs


def _build_inflammation_observation(deid: str, labels: list[str], dates: list[str]) -> dict:
    """将炎症分期映射为 Observation。"""
    if not labels:
        return None
    latest_label = labels[-1]
    latest_date = dates[-1] if dates else None
    status_map = {
        "急性期": "acute",
        "过渡期": "transitional",
        "缓解期": "remission",
        "未知": "unknown",
    }
    obs: dict = {
        "resourceType": "Observation",
        "id": f"{deid}-inflammation-status",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "76437-3",
                    "display": "Inflammation status",
                }
            ],
            "text": "炎症分期",
        },
        "valueCodeableConcept": {
            "coding": [
                {
                    "system": "urn:lab-analysis:inflammation-status",
                    "code": status_map.get(latest_label, "unknown"),
                    "display": latest_label,
                }
            ],
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
        predictions.append(
            {
                "outcome": {"text": h["hypothesis"]},
                "probabilityDecimal": h["confidence"],
            }
        )
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


def _build_diagnostic_report(
    deid: str, obs_ids: list[str], scoring_card: dict, report_md: str
) -> dict:
    dr: dict = {
        "resourceType": "DiagnosticReport",
        "id": f"{deid}-integrated-report",
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": "http://loinc.org",
                    "code": "11536-0",
                    "display": "Integrated clinical report",
                }
            ],
            "text": "综合临床诊断报告",
        },
        "result": [{"reference": f"Observation/{oid}"} for oid in obs_ids],
    }
    top_hypotheses = scoring_card.get("top_hypotheses") or []
    if top_hypotheses:
        top = top_hypotheses[0]
        dr["conclusion"] = f"{top['hypothesis']}（置信度 {top['confidence']:.0%}）"
        dr["conclusionCodeableConcept"] = {
            "coding": [
                {
                    "system": "urn:lab-analysis:hypothesis",
                    "code": top["hypothesis"][:50],
                    "display": top["hypothesis"],
                }
            ],
        }
    if report_md:
        dr["presentedForm"] = [
            {
                "contentType": "text/markdown",
                "data": base64.b64encode(strip_phi(report_md).encode()).decode(),
            }
        ]
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
        lab_metrics: 检验指标。**两种形状都接受**:
            - 窄表 ``[{"metric": "CRP", "value": 12.3, "unit": "mg/L", "date": ...}]``
            - 宽表 ``[{"report_id": ..., "report_date": ..., "WBC": 6.1, "CRP": 12.3}]``
              (生产侧 ``lab_metrics.json`` 的 ``reports`` 就是这种, 每行一份报告)
            宽表会由 ``_pivot_lab_metrics()`` 自动转成窄表。

            ⚠️ 已知限制: 宽表不含单位列, 导出的 ``valueQuantity.unit`` 只能留 "?"。
            补 UCUM ``system``/``code`` 需要一份经核验的指标→单位编码映射,
            不应凭空生成医学编码。

    Returns:
        FHIR R4 Bundle dict，可序列化为 JSON。
    """

    from lab_analysis.analysis._base import REF_RANGES

    entry: list[dict] = []
    obs_ids = []

    # 1. Patient
    entry.append({"resource": _build_patient(deid)})

    # 2. Observations（来自 REF_RANGES 的指标）
    # ⚠️ 必须先归一化: 生产侧 data_loader.to_json() 写出的 reports 是**宽表**
    # (每行一份报告, 指标各占一列), 直接按窄表解析会得到 metric="" / value=None,
    # 结果是 Bundle 里一条有效检验数据都没有。
    for lm in _pivot_lab_metrics(lab_metrics):
        metric = lm["metric"]
        value = lm["value"]
        if not metric or value is None:
            continue
        unit = lm["unit"] or "?"
        date = lm["date"] or None
        ref = REF_RANGES.get(metric)
        ref_low, ref_high = ref if ref else (None, None)
        # id 必须保证唯一: 同一 report_date 下 NEUT% 与 NEUT# 都会出现,
        # 单纯 slug 化会把两者都压成 NEUT 而撞 id
        obs_id = _observation_id(deid, metric, lm["date"])
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
                "coding": [
                    {
                        "system": "urn:lab-analysis:alert",
                        "code": alert.get("level", "INFO"),
                        "display": alert.get("source", "alert"),
                    }
                ],
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
        # Bundle.timestamp 是 FHIR instant, 必须带时区偏移; naive 时间会被真实
        # 校验器拒收
        "timestamp": datetime.now().astimezone().isoformat(),
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

    analysis_results = (
        json.loads((analyzed_dir / "analysis_results.json").read_text(encoding="utf-8"))
        if (analyzed_dir / "analysis_results.json").exists()
        else {}
    )

    scoring_card = (
        json.loads((reports_dir / "scoring_card.json").read_text(encoding="utf-8"))
        if (reports_dir / "scoring_card.json").exists()
        else {}
    )

    alerts = (
        json.loads((analyzed_dir / "alerts.json").read_text(encoding="utf-8"))
        if (analyzed_dir / "alerts.json").exists()
        else []
    )

    report_md = (
        (reports_dir / "final_integrated_report.md").read_text(encoding="utf-8")
        if (reports_dir / "final_integrated_report.md").exists()
        else ""
    )

    # 从 lab_metrics.json 读取检验数据
    lab_metrics = []
    lm_path = analyzed_dir / "lab_metrics.json"
    if lm_path.exists():
        lm_data = json.loads(lm_path.read_text(encoding="utf-8"))
        lab_metrics = lm_data.get("reports", lm_data.get("records", []))

    bundle = build_fhir_bundle(
        args.id_card,
        analysis_results,
        scoring_card,
        alerts,
        report_md,
        lab_metrics,
    )

    out_path = args.out or str(reports_dir / "fhir_bundle.json")
    # 独立运行时 04_reports/ 可能还不存在(pipeline 里由评分卡步骤创建),
    # 不建目录会直接 FileNotFoundError 崩掉, 与 scoring_card 的行为保持一致
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"[OK] FHIR Bundle 已保存: {out_path}")


if __name__ == "__main__":
    _cli()
