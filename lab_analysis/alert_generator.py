"""alert_generator.py — 结构化异常告警摘要生成

从 _compute_stats() 产出的 analysis_results.json 中提取异常信号，
生成分级告警列表（CRITICAL / WARNING / INFO），输出到 alerts.json 和控制台。

用法:
    from lab_analysis.alert_generator import generate_alerts, print_alerts

    with open("analysis_results.json") as f:
        results = json.load(f)
    alerts = generate_alerts(results)
    print_alerts(alerts)
    # alerts 可序列化为 alerts.json 供外部消费
"""

from __future__ import annotations

from typing import Any

from . import _log

logger = _log.get_logger(__name__)

# ── 告警数据结构 ──────────────────────────────────────────────────────

AlertDict = dict[str, Any]
"""单条告警的 dict 表示，包含:
- level: "CRITICAL" | "WARNING" | "INFO"
- source: "inflammation" | "reference_range" | "zscore" | "variability" | "trend"
- metric: str
- message: str (human-readable, Chinese)
- 各类上下文键 (value, threshold, ref_range, cv, etc.)
"""


# ── 告警级别权重（用于排序） ──────────────────────────────────────────

_LEVEL_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


# ═════════════════════════════════════════════════════════════════════
# 告警生成器
# ═════════════════════════════════════════════════════════════════════


def _alert_inflammation(results: dict) -> list[AlertDict]:
    """hs-CRP 急性/过渡/缓解期告警。"""
    alerts: list[AlertDict] = []
    inflam = results.get("inflammation_classification", {})
    labels = inflam.get("labels", [])
    dates = inflam.get("report_dates", [])
    if not labels:
        return alerts
    if dates and len(labels) != len(dates):
        logger.warning("_alert_inflammation: labels(%d) 和 dates(%d) 长度不一致", len(labels), len(dates))
    # 只看最近一次
    latest_label = labels[-1]
    latest_date = dates[-1] if dates else "?"
    if latest_label == "急性期":
        alerts.append(
            {
                "level": "CRITICAL",
                "source": "inflammation",
                "metric": "hs-CRP",
                "value": 0,  # 调用方可补充
                "threshold": 3.0,
                "date": latest_date,
                "message": f"hs-CRP 急性期（{latest_date}），炎症活跃，超过阈值 3.0",
            }
        )
    elif latest_label == "过渡期":
        alerts.append(
            {
                "level": "WARNING",
                "source": "inflammation",
                "metric": "hs-CRP",
                "value": 0,
                "threshold": (1.0, 3.0),
                "date": latest_date,
                "message": f"hs-CRP 过渡期（{latest_date}），hs-CRP 在 1.0-3.0 之间",
            }
        )
    return alerts


def _alert_reference_range(results: dict) -> list[AlertDict]:
    """指标超出参考范围告警。"""
    alerts: list[AlertDict] = []
    abnormal = results.get("abnormal_summary", {})
    if not isinstance(abnormal, dict):
        return alerts
    for metric, info in abnormal.items():
        ref = info.get("ref_range", "?")
        n = info.get("n_abnormal", 0)
        dates = info.get("abnormal_dates", [])
        dates_str = ", ".join(dates) if dates else f"{n}次"
        level = "CRITICAL" if n >= 3 else "WARNING"
        alerts.append(
            {
                "level": level,
                "source": "reference_range",
                "metric": metric,
                "ref_range": ref,
                "n_abnormal": n,
                "dates": dates,
                "message": f"{metric} 超出参考范围（{ref}），异常 {n} 次（{dates_str}）",
            }
        )
    return alerts


def _alert_zscore(results: dict) -> list[AlertDict]:
    """Z-score 异常值告警。"""
    alerts: list[AlertDict] = []
    zscores = results.get("zscore_outliers", {})
    for metric, info in zscores.items():
        severe = info.get("outliers_severe", {})
        mild = info.get("outliers_mild", {})
        severe_cnt = severe.get("count", 0)
        mild_cnt = mild.get("count", 0)

        if severe_cnt > 0:
            dates = severe.get("dates", [])
            vals = severe.get("values", [])
            details = (
                "; ".join(f"{d}={v}" for d, v in zip(dates, vals, strict=True))
                if dates and vals
                else f"{severe_cnt}次"
            )
            max_dev = info.get("max_deviation", {})
            max_z = max_dev.get("z_score", "?")
            alerts.append(
                {
                    "level": "CRITICAL",
                    "source": "zscore",
                    "metric": metric,
                    "count": severe_cnt,
                    "max_z_score": max_z,
                    "dates": dates,
                    "values": vals,
                    "message": f"{metric} 严重异常值 {severe_cnt}次（|Z|>3），最大 Z={max_z}（{details}）",
                }
            )
        elif mild_cnt > 0:
            dates = mild.get("dates", [])
            alerts.append(
                {
                    "level": "INFO",
                    "source": "zscore",
                    "metric": metric,
                    "count": mild_cnt,
                    "dates": dates,
                    "message": f"{metric} 轻度异常值 {mild_cnt}次（|Z|>2）",
                }
            )
    return alerts


def _alert_variability(results: dict) -> list[AlertDict]:
    """CV 稳定性告警。"""
    alerts: list[AlertDict] = []
    cv_data = results.get("cv_stability", {})
    for metric, info in cv_data.items():
        risk = info.get("risk_level", "")
        cv = info.get("cv", 0)
        if risk == "高":
            alerts.append(
                {
                    "level": "WARNING",
                    "source": "variability",
                    "metric": metric,
                    "cv": cv,
                    "risk_level": risk,
                    "message": f"{metric} CV={cv:.4f}（高变异，需关注波动）",
                }
            )
    return alerts


def _alert_trend(results: dict) -> list[AlertDict]:
    """线性回归趋势告警。"""
    alerts: list[AlertDict] = []
    reg = results.get("linear_regression", {})
    for metric, info in reg.items():
        slope = info.get("slope", 0)
        trend = info.get("trend", "平稳")
        r2 = info.get("r2", 0)
        if trend == "上升" and r2 >= 0.7:
            alerts.append(
                {
                    "level": "WARNING",
                    "source": "trend",
                    "metric": metric,
                    "slope": slope,
                    "r2": r2,
                    "trend": trend,
                    "message": f"{metric} 显著上升趋势（slope={slope:.4f}, R²={r2:.3f}）",
                }
            )
        elif trend == "下降" and r2 >= 0.7:
            alerts.append(
                {
                    "level": "INFO",
                    "source": "trend",
                    "metric": metric,
                    "slope": slope,
                    "r2": r2,
                    "trend": trend,
                    "message": f"{metric} 显著下降趋势（slope={slope:.4f}, R²={r2:.3f}）",
                }
            )
    return alerts


# ═════════════════════════════════════════════════════════════════════
# 聚合入口
# ═════════════════════════════════════════════════════════════════════


def generate_alerts(results: dict) -> list[AlertDict]:
    """从 analysis_results dict 生成全量告警列表。

    Args:
        results: _compute_stats() 返回的 analysis_results 字典。

    Returns:
        按 level 降序排列的告警列表（CRITICAL → WARNING → INFO）。
    """
    alerts: list[AlertDict] = []
    alerts.extend(_alert_inflammation(results))
    alerts.extend(_alert_reference_range(results))
    alerts.extend(_alert_zscore(results))
    alerts.extend(_alert_variability(results))
    alerts.extend(_alert_trend(results))
    # 按严重程度排序
    alerts.sort(key=lambda a: (_LEVEL_ORDER.get(a.get("level", "INFO"), 99), a.get("metric", "")))
    return alerts


def print_alerts(alerts: list[AlertDict]):
    """将告警列表打印到控制台。"""
    if not alerts:
        logger.info("  [OK] 无异常告警")
        return
    levels = {"CRITICAL": "[CRITICAL]", "WARNING": "[WARNING]", "INFO": "[INFO]"}
    icons = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}
    for a in alerts:
        icon = icons.get(a["level"], "·")
        label = levels.get(a["level"], "[?]")
        logger.info(f"  {icon} {label} {a['message']}")


def generate_alerts_from_file(json_path: str | Path) -> list[AlertDict]:
    """从 analysis_results.json 文件路径直接生成告警。"""
    import json
    from pathlib import Path

    path = Path(json_path)
    if not path.exists():
        logger.info(f"  [WARNING] 找不到 analysis_results.json: {path}")
        return []
    try:
        results = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(f"  [ERROR] 解析 JSON 失败: {path} — {exc}")
        return []
    return generate_alerts(results)


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="生成结构化异常告警摘要")
    parser.add_argument("--in", dest="inp", required=True, help="analysis_results.json 路径")
    parser.add_argument("--out", default=None, help="alerts.json 输出路径（可选）")
    args = parser.parse_args()

    alerts = generate_alerts_from_file(args.inp)
    logger.info(f"\n=== 异常告警摘要（共 {len(alerts)} 条）===\n")
    print_alerts(alerts)

    if args.out:
        Path(args.out).write_text(
            json.dumps(alerts, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"\n[OK] 已保存: {args.out}")
