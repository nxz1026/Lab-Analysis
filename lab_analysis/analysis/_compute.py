"""lab_analysis.analysis._compute — 统计数据计算函数"""

import numpy as np
import pandas as pd

from ._base import NUMERIC_METRICS, ACUTE_THRESHOLD, REMISSION_THRESHOLD


def classify_inflammation(hs_crp):
    if hs_crp is None:
        return "未知"
    if hs_crp > ACUTE_THRESHOLD:
        return "急性期"
    elif hs_crp < REMISSION_THRESHOLD:
        return "缓解期"
    else:
        return "过渡期"


def linear_regression_trend(series: pd.Series) -> dict:
    valid = series.dropna()
    if len(valid) < 2:
        return {"slope": None, "intercept": None, "r2": None,
                "trend": "数据不足", "slope_per_day": None}

    x = np.arange(len(valid))
    y = valid.values.astype(float)
    x_mean, y_mean = x.mean(), y.mean()

    numerator   = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)

    if denominator == 0:
        return {"slope": 0, "intercept": y_mean, "r2": 0,
                "trend": "无变化", "slope_per_day": 0}

    slope     = numerator / denominator
    intercept = y_mean - slope * x_mean
    ss_res    = np.sum((y - (slope * x + intercept)) ** 2)
    ss_tot    = np.sum((y - y_mean) ** 2)
    r2        = 1 - ss_res / ss_tot if ss_tot != 0 else 0

    trend = "上升" if slope > 0.1 else "下降" if slope < -0.1 else "平稳"

    return {
        "slope": round(float(slope), 4),
        "intercept": round(float(intercept), 4),
        "r2": round(float(r2), 4),
        "trend": trend,
        "slope_per_day": round(float(slope), 4),
        "n_points": int(len(valid)),
    }


def correlation_matrix_calc(df: pd.DataFrame, metrics: list) -> dict:
    cols = [m for m in metrics if m in df.columns]
    sub  = df[cols].apply(pd.to_numeric, errors="coerce")
    corr = sub.corr(method="pearson")
    result = {}
    for col in cols:
        for row in cols:
            if col == row:
                continue
            val = corr.loc[row, col]
            if pd.notna(val) and abs(val) >= 0.1:
                result[f"{row}~{col}"] = round(float(val), 3)
    return result


def descriptive_stats(series: pd.Series) -> dict:
    valid = series.dropna().astype(float)
    if len(valid) == 0:
        return {"count": 0, "mean": None, "std": None,
                "min": None, "max": None, "cv": None}
    mean = float(valid.mean())
    std  = float(valid.std(ddof=1)) if len(valid) > 1 else 0
    cv   = round(std / mean, 4) if mean != 0 else None
    return {
        "count": int(len(valid)),
        "mean": round(mean, 3),
        "std": round(std, 3),
        "min": round(float(valid.min()), 3),
        "max": round(float(valid.max()), 3),
        "cv": cv,
    }


def moving_average_analysis(df: pd.DataFrame, window: int = 2) -> dict:
    results = {}
    key_metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"]

    for metric in key_metrics:
        if metric not in df.columns:
            continue
        series = df[metric].dropna()
        if len(series) < window:
            continue

        ma      = series.rolling(window=window, min_periods=1).mean()
        std_r   = series.rolling(window=window, min_periods=1).std().fillna(0)

        if len(ma) >= 2:
            ma_vals = ma.values
            trend = "上升" if ma_vals[-1] > ma_vals[0] * 1.05 else \
                    "下降" if ma_vals[-1] < ma_vals[0] * 0.95 else "平稳"
        else:
            trend = "数据不足"

        results[metric] = {
            "moving_avg":  [round(v, 3) if pd.notna(v) else None for v in ma],
            "rolling_std": [round(v, 3) if pd.notna(v) else None for v in std_r],
            "trend": trend,
            "window": window,
        }
    return results


def cv_stability_analysis(df: pd.DataFrame) -> dict:
    results = {}
    for metric in NUMERIC_METRICS:
        if metric not in df.columns:
            continue
        series = df[metric].dropna().astype(float)
        if len(series) < 3:
            continue
        mean = series.mean()
        std  = series.std(ddof=1)
        if mean == 0:
            continue
        cv = std / mean

        if cv < 0.1:
            stability, risk_level = "稳定", "低"
        elif cv < 0.2:
            stability, risk_level = "中等变异", "中"
        else:
            stability, risk_level = "高变异", "高"

        rolling_cv = series.rolling(window=3, min_periods=2).apply(
            lambda x: x.std() / x.mean() if x.mean() != 0 and len(x) >= 2 else np.nan
        )
        results[metric] = {
            "cv": round(cv, 4), "mean": round(mean, 3), "std": round(std, 3),
            "stability": stability, "risk_level": risk_level,
            "n_points": len(series),
            "rolling_cv": [round(v, 4) if pd.notna(v) else None for v in rolling_cv],
        }
    return results


def zscore_outlier_detection(df: pd.DataFrame, threshold: float = 2.0) -> dict:
    results = {}
    for metric in NUMERIC_METRICS:
        if metric not in df.columns:
            continue
        series = df[metric].dropna().astype(float)
        if len(series) < 3:
            continue
        mean = series.mean()
        std  = series.std(ddof=1)
        if std == 0:
            continue

        zscores = (series - mean) / std
        outliers_mild   = zscores[zscores.abs() > threshold]
        outliers_severe = zscores[zscores.abs() > 3.0]

        outlier_dates_mild   = df.loc[outliers_mild.index, "report_date"] \
                                 .dt.strftime("%Y-%m-%d").tolist() if len(outliers_mild) else []
        outlier_dates_severe = df.loc[outliers_severe.index, "report_date"] \
                                 .dt.strftime("%Y-%m-%d").tolist() if len(outliers_severe) else []

        max_dev_idx = zscores.abs().idxmax()
        results[metric] = {
            "z_scores": [round(v, 3) if pd.notna(v) else None for v in zscores],
            "outliers_mild": {
                "count": len(outliers_mild),
                "dates": outlier_dates_mild,
                "values": [round(float(series[idx]), 3) for idx in outliers_mild.index],
            },
            "outliers_severe": {
                "count": len(outliers_severe),
                "dates": outlier_dates_severe,
                "values": [round(float(series[idx]), 3) for idx in outliers_severe.index],
            },
            "max_deviation": {
                "date": df.loc[max_dev_idx, "report_date"].strftime("%Y-%m-%d"),
                "value": round(float(series[max_dev_idx]), 3),
                "z_score": round(float(zscores[max_dev_idx]), 3),
            },
            "threshold": threshold,
        }
    return results
