"""lab_analysis.analysis.run — 统计分析编排器 + CLI"""

import argparse
import json
from datetime import datetime

import pandas as pd

from ._base import (
    NUMERIC_METRICS,
    REF_RANGES,
    build_paths,
)
from ._compute import (
    classify_inflammation,
    correlation_matrix_calc,
    cv_stability_analysis,
    descriptive_stats,
    linear_regression_trend,
    moving_average_analysis,
    zscore_outlier_detection,
)
from .charts import (
    plot_abnormal_indicators,
    plot_correlation_heatmap,
    plot_cv_stability_heatmap,
    plot_inflammation_status,
    plot_moving_average,
    plot_trend_regression,
    plot_zscore_distribution,
)


def _compute_stats(df: pd.DataFrame) -> dict:
    """纯计算：从 DataFrame 生成所有统计结果 dict。"""
    results = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_reports": len(df),
        "date_range": {
            "start": df["report_date"].min().strftime("%Y-%m-%d"),
            "end":   df["report_date"].max().strftime("%Y-%m-%d"),
        },
    }

    # ── 1. 炎症状态分类 ──────────────────────────────────────
    inflammation_status = [classify_inflammation(
        row["hs-CRP"] if pd.notna(row.get("hs-CRP")) else None)
        for _, row in df.iterrows()]
    df["inflammation_status"] = inflammation_status
    results["inflammation_classification"] = {
        "labels": inflammation_status,
        "report_dates": df["report_date"].dt.strftime("%Y-%m-%d").tolist(),
    }
    print(f"炎症分类: {dict(zip(df['report_date'].dt.strftime('%m-%d'), inflammation_status, strict=True))}")

    # ── 2. 线性回归趋势 ──────────────────────────────────────
    trend_results = {}
    key_for_trend = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"]
    for metric in key_for_trend:
        if metric not in df.columns:
            continue
        reg = linear_regression_trend(df[metric])
        if reg["slope"] is not None:
            trend_results[metric] = reg
            print(f"  {metric}: slope={reg['slope']:.4f}, R2={reg['r2']:.3f}, trend={reg['trend']}")
    results["linear_regression"] = trend_results

    # ── 3. 相关性矩阵 ────────────────────────────────────────
    corr_metrics = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "PCT", "PLT"]
    corr = correlation_matrix_calc(df, corr_metrics)
    results["correlation_matrix"] = corr
    print(f"相关性显著 pairs: {len(corr)} 个")
    for pair, val in corr.items():
        print(f"  {pair}: r={val:.3f}")

    # ── 4. 描述性统计 ────────────────────────────────────────
    desc_stats = {}
    for metric in NUMERIC_METRICS:
        if metric in df.columns:
            desc = descriptive_stats(df[metric])
            if desc["count"] > 0:
                desc_stats[metric] = desc
    results["descriptive_stats"] = desc_stats

    # ── 5. 异常指标汇总 ──────────────────────────────────────
    abnormal_summary = {}
    for metric, (low, high) in REF_RANGES.items():
        if metric not in df.columns:
            continue
        col = df[metric].dropna()
        if len(col) == 0:
            continue
        abnormal_dates = df.loc[
            df[metric].notna() & ((df[metric] < low) | (df[metric] > high)),
            "report_date"
        ].dt.strftime("%Y-%m-%d").tolist()
        if abnormal_dates:
            abnormal_summary[metric] = {
                "ref_range": f"{low}-{high}",
                "abnormal_dates": abnormal_dates,
                "n_abnormal": len(abnormal_dates),
            }
    results["abnormal_summary"] = abnormal_summary
    print(f"异常指标: {list(abnormal_summary.keys())}")

    # ── 6. 移动平均分析 ──────────────────────────────────────
    ma_results = moving_average_analysis(df, window=2)
    results["moving_average"] = ma_results
    print(f"\n移动平均分析完成: {len(ma_results)} 个指标")
    for metric, ma_d in list(ma_results.items())[:3]:
        print(f"  {metric}: 趋势={ma_d['trend']}, 窗口={ma_d['window']}")

    # ── 7. 变异系数（CV）稳定性分析 ───────────────────────────
    cv_results = cv_stability_analysis(df)
    results["cv_stability"] = cv_results
    print(f"\nCV稳定性分析完成: {len(cv_results)} 个指标")
    high_cv = [(m, d) for m, d in cv_results.items() if d['risk_level'] == '高']
    if high_cv:
        print(f"  [警告] 高变异指标: {', '.join([m for m, _ in high_cv])}")
    else:
        print("  [成功] 所有指标稳定性良好")

    # ── 8. Z-score异常检测 ───────────────────────────────────
    zscore_results = zscore_outlier_detection(df, threshold=2.0)
    results["zscore_outliers"] = zscore_results
    print(f"\nZ-score异常检测完成: {len(zscore_results)} 个指标")
    total_outliers = sum(d['outliers_mild']['count'] for d in zscore_results.values())
    severe_outliers = sum(d['outliers_severe']['count'] for d in zscore_results.values())
    if severe_outliers > 0:
        print(f"  [ALERT] 发现 {severe_outliers} 个严重异常值 (|Z|>3)")
    if total_outliers > 0:
        print(f"  [警告] 发现 {total_outliers} 个轻度异常值 (|Z|>2)")

    return results


def _generate_md_report(results: dict, patient_id: str) -> str:
    """从统计结果 dict 生成 Markdown 报告文本。"""
    md_lines = ["# 统计分析报告\n"]
    md_lines.append(
        f"**患者**: {patient_id}  **报告数**: {results['n_reports']}  "
        f"**日期范围**: {results['date_range']}\n"
    )

    # 炎症
    infl = results.get("inflammation_classification", {})
    if isinstance(infl, dict):
        labels = infl.get("labels", [])
        dates = infl.get("report_dates", [])
        emoji_map = {"急性期": "🔴", "过渡期": "🟡", "缓解期": "🟢"}
        md_lines.append("## 炎症分期\n")
        for date, cls in zip(dates, labels, strict=True):
            md_lines.append(f"- {date}: {emoji_map.get(cls, '[GRAY]')} {cls}\n")

    # 异常
    md_lines.append("\n## 异常指标\n")
    for metric, info in results.get("abnormal_summary", {}).items():
        n = info.get("n_abnormal", 0)
        dt_list = info.get("abnormal_dates", [])
        ref = info.get("ref_range", "?")
        md_lines.append(f"- **{metric}**: 异常 {n} 次（{', '.join(dt_list)}），参考区间 {ref}\n")

    # 回归
    md_lines.append("\n## 指标趋势（线性回归）\n")
    for metric, reg in results.get("linear_regression", {}).items():
        slope = reg.get("slope", 0)
        r2 = reg.get("r2", 0)
        trend = reg.get("trend", "平稳")
        arrow = "↑" if slope > 0 else "↓" if slope < 0 else "→"
        md_lines.append(f"- {metric}: slope={slope:.4f}, R²={r2:.3f}, {arrow} {trend}\n")

    # 相关
    md_lines.append("\n## 强相关性（|r| ≥ 0.9）\n")
    corr = results.get("correlation_matrix", {})
    strong = [(p, r) for p, r in corr.items()
              if isinstance(r, (int, float)) and abs(r) >= 0.9]
    for pair, r in sorted(strong, key=lambda x: -abs(x[1])):
        md_lines.append(f"- {pair}: r={r:.3f}（{'正' if r>0 else '负'}相关）\n")

    # 移动平均
    md_lines.append("\n## 移动平均趋势分析\n")
    for metric, ma_info in results.get("moving_average", {}).items():
        trend = ma_info.get("trend", "?")
        window = ma_info.get("window", 2)
        arrow = "↑" if trend == "上升" else "↓" if trend == "下降" else "→"
        md_lines.append(f"- {metric}: {arrow} {trend}（窗口={window}次就诊）\n")

    # CV
    md_lines.append("\n## 指标稳定性分析（变异系数CV）\n")
    cv_data = results.get("cv_stability", {})
    high_risk = [(m, d) for m, d in cv_data.items() if d.get('risk_level') == '高']
    medium_risk = [(m, d) for m, d in cv_data.items() if d.get('risk_level') == '中']
    stable = [(m, d) for m, d in cv_data.items() if d.get('risk_level') == '低']
    if high_risk:
        md_lines.append("### ⚠ 高变异指标（需关注）\n")
        for metric, info in high_risk:
            md_lines.append(f"- **{metric}**: CV={info.get('cv',0):.4f}（波动较大）\n")
    if medium_risk:
        md_lines.append("\n### 中等变异指标\n")
        for metric, info in medium_risk:
            md_lines.append(f"- {metric}: CV={info.get('cv',0):.4f}\n")
    if stable:
        md_lines.append(f"\n### 稳定指标（{len(stable)}个）\n")
        md_lines.append(f"- {', '.join([m for m,_ in stable[:5]])}"
                        f"{' 等'+str(len(stable))+'个' if len(stable)>5 else ''}\n")

    # Z-score
    md_lines.append("\n## Z-score异常检测结果\n")
    severe_items, mild_items = [], []
    for metric, info in results.get("zscore_outliers", {}).items():
        s = info.get('outliers_severe', {})
        m = info.get('outliers_mild', {})
        if s.get('count', 0) > 0:
            severe_items.append((metric, s))
        elif m.get('count', 0) > 0:
            mild_items.append((metric, m))
    if severe_items:
        md_lines.append("### 🚨 严重异常值（|Z| > 3）\n")
        for metric, info in severe_items:
            dt_list = ', '.join(info.get('dates', []))
            val_list = ', '.join([str(v) for v in info.get('values', [])])
            md_lines.append(f"- **{metric}**: {info['count']}次异常\n")
            md_lines.append(f"  - 日期: {dt_list}\n")
            md_lines.append(f"  - 数值: {val_list}\n")
    if mild_items:
        md_lines.append("\n### ⚠ 轻度异常值（|Z| > 2）\n")
        for metric, info in mild_items:
            md_lines.append(f"- {metric}: {info['count']}次异常"
                            f"（{', '.join(info.get('dates', []))}）\n")
    if not severe_items and not mild_items:
        md_lines.append("- ✅ 未发现统计学异常值\n")

    return "".join(md_lines)


def _generate_charts(df: pd.DataFrame, results: dict, paths: dict):
    """生成所有统计图表。"""
    print("\n[CHARTS] 开始绘图...")
    plot_trend_regression(df, results, paths["fig_trend"])
    plot_correlation_heatmap(df, paths["fig_corr"])
    plot_inflammation_status(df, results, paths["fig_infl"])
    plot_abnormal_indicators(df, results, paths["fig_abnorm"])
    print("\n[ADVANCED CHARTS] 绘制高级分析图表...")
    plot_moving_average(df, results, paths["fig_ma"])
    plot_cv_stability_heatmap(df, results, paths["fig_cv"])
    plot_zscore_distribution(df, results, paths["fig_zscore"])


def run(patient_id: str) -> dict:
    """统计分析入口：加载数据 → 计算 → JSON → Markdown → 图表。"""
    paths = build_paths(patient_id)
    print(f"[{datetime.now().isoformat()}] 开始数据分析...")
    print(f"  病人: {patient_id}")

    if not paths["metrics_csv"].exists():
        raise FileNotFoundError(
            f"找不到前置文件: {paths['metrics_csv']}\n"
            f"   请先运行 data_loader.py --id-card {patient_id}"
        )

    df = pd.read_csv(paths["metrics_csv"])
    df["report_date"] = pd.to_datetime(df["report_date"])
    df = df.sort_values("report_date").reset_index(drop=True)

    print(f"数据范围: {df['report_date'].min().date()} ~ {df['report_date'].max().date()}")
    print(f"共 {len(df)} 份报告")

    # 1. 纯计算
    results = _compute_stats(df)

    # 2. 保存 JSON
    paths["analyzed_dir"].mkdir(parents=True, exist_ok=True)
    paths["reports_dir"].mkdir(parents=True, exist_ok=True)
    with open(paths["output_json"], "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"JSON 已保存: {paths['output_json']}")

    # 3. 生成 & 保存 Markdown 报告
    md_report = _generate_md_report(results, patient_id)
    with open(paths["report_md"], "w", encoding="utf-8") as f:
        f.write(md_report)
    print(f"Markdown 已保存: {paths['report_md']}")

    # 4. 绘图
    _generate_charts(df, results, paths)

    print(f"[{datetime.now().isoformat()}] 数据分析完成")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="统计分析：生成分析结果 + 7 张图表")
    parser.add_argument("--id-card", required=True, help="脱敏ID(由 pipeline 传入)")
    args = parser.parse_args()
    run(args.id_card)
