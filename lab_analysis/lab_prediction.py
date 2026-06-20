"""lab_prediction.py — 检验指标未来值预测

利用已有时间序列数据，用线性回归 + 置信区间预测未来就诊的指标值。

用法:
    from lab_analysis.lab_prediction import predict_metrics
    predictions = predict_metrics(results, df)
    results["predictions"] = predictions
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# 需要预测的关键指标列表
KEY_METRICS = ["hs-CRP", "CRP", "WBC", "NEUT#", "RDW-SD", "RDW-CV", "PCT"]

# 各指标的已知阈值（用于 alert）
_ALERT_THRESHOLDS: dict[str, tuple[float, float | None] | None] = {
    "hs-CRP": (3.0, None),   # 超过 3.0 → 急性期
    "CRP": (10.0, None),
    "WBC": (9.5, 3.5),
    "NEUT#": (6.3, 1.8),
}


def predict_metric(series: pd.Series, metric: str) -> dict:
    """对单个指标进行预测。

    Args:
        series: 按时间排序的指标值序列，index 不重要。
        metric: 指标名（用于阈值告警）。

    Returns:
        预测结果 dict。数据不足时返回空 dict。
    """
    vals = series.dropna().values.astype(float)
    n = len(vals)
    if n < 2:
        return {}

    x = np.arange(n)
    y = vals

    # 线性回归 + 置信区间
    slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, y)
    r2 = r_value ** 2

    # 预测下一个点（x = n）
    x_pred = n
    y_pred = slope * x_pred + intercept

    # 预测区间（95% CI）
    # t 值 = n-2 自由度
    if n > 2:
        t_val = scipy_stats.t.ppf(0.975, n - 2)
        # 预测标准误
        x_mean = x.mean()
        sse = np.sum((y - (slope * x + intercept)) ** 2)
        mse = sse / (n - 2)
        se_pred = np.sqrt(mse * (1 + 1 / n + (x_pred - x_mean) ** 2 / np.sum((x - x_mean) ** 2)))
        ci_half = t_val * se_pred
        ci_lower = y_pred - ci_half
        ci_upper = y_pred + ci_half
    else:
        ci_lower = y_pred
        ci_upper = y_pred
        ci_half = 0.0

    # 趋势判断
    trend = "上升" if slope > 0.1 else "下降" if slope < -0.1 else "平稳"

    # 阈值告警
    alert = None
    thresholds = _ALERT_THRESHOLDS.get(metric)
    if thresholds:
        high_th, low_th = thresholds
        if high_th is not None and y_pred > high_th:
            alert = f"预测值 {y_pred:.1f} 超过阈值 {high_th}"
        elif low_th is not None and y_pred < low_th:
            alert = f"预测值 {y_pred:.1f} 低于阈值 {low_th}"

    # 指数平滑（n >= 3 时作为补充）
    method = "linear_regression"
    if n >= 3 and r2 >= 0.3:
        # 简单一次指数平滑
        alpha = 0.3
        s = vals[0]
        for v in vals[1:]:
            s = alpha * v + (1 - alpha) * s
        method = "linear_regression+exponential_smoothing"

    return {
        "next_value": round(float(y_pred), 3),
        "ci_95_lower": round(float(ci_lower), 3),
        "ci_95_upper": round(float(ci_upper), 3),
        "ci_95_half_width": round(float(ci_half), 3),
        "n_used": n,
        "method": method,
        "slope": round(float(slope), 4),
        "r2": round(float(r2), 4),
        "trend": trend,
        "alert": alert,
    }


def predict_metrics(results: dict, df: pd.DataFrame) -> dict:
    """对 DataFrame 中所有关键指标进行预测。

    Args:
        results: _compute_stats() 产出的 results dict（含 linear_regression）。
        df: 原始 DataFrame（含所有指标的时序数据）。

    Returns:
        ``{metric: prediction_dict, ...}`` 每个指标对应 predict_metric 的输出。
    """
    predictions = {}
    for metric in KEY_METRICS:
        if metric not in df.columns:
            continue
        series = df[metric]
        pred = predict_metric(series, metric)
        if pred:
            predictions[metric] = pred
    return predictions


def print_predictions(predictions: dict):
    """将预测结果打印到控制台。"""
    if not predictions:
        print("  [INFO] 无有效预测数据（至少需要 2 个数据点）")
        return
    print("\n--- 指标预测 ---")
    for metric, p in predictions.items():
        ci = f"[{p['ci_95_lower']:.2f}, {p['ci_95_upper']:.2f}]" if p.get('ci_95_lower') else "N/A"
        alert_str = f" ⚠️ {p['alert']}" if p.get('alert') else ""
        print(f"  {metric}: 下次预测={p['next_value']:.3f}  95%CI={ci}  {p['trend']}{alert_str}")
