#!/usr/bin/env python3
"""统计分析：lab_metrics.csv → analysis_results.json + 4张图"""
import json, argparse, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from pathlib import Path
from datetime import datetime

WIKI_ROOT = Path.home() / "wiki"

METRICS = ["WBC", "RBC", "HGB", "HCT", "PLT", "PCT", "P-LCR", "MCV", "MCH", "MCHC",
           "NEUT%", "LYMPH%", "MONO%", "EO%", "BASO%", "NEUT#", "LYMPH#", "MONO#", "EO#",
           "BASO#", "RDW-SD", "RDW-CV", "MPV", "PDW", "CRP", "hs-CRP"]

REFS = {
    "WBC": (3.5, 9.5), "RBC": (4.3, 5.8), "HGB": (130, 175), "HCT": (40, 50),
    "PLT": (125, 350), "PCT": (0.108, 0.272), "NEUT%": (40, 75), "LYMPH%": (20, 50),
    "MONO%": (2, 10), "EO%": (0.4, 8), "BASO%": (0, 1), "NEUT#": (1.8, 6.3),
    "LYMPH#": (1.1, 3.2), "MONO#": (0.1, 0.6), "RDW-SD": (37, 50), "RDW-CV": (0, 15),
    "CRP": (0, 10), "hs-CRP": (0, 1.0),
}
ACUTE, REMISSION = 3.0, 1.0
COLORS = {"急性期": "#e74c3c", "过渡期": "#f39c12", "缓解期": "#27ae60", "未知": "#95a5a6"}


def classify(hs_crp):
    if hs_crp is None: return "未知"
    return "急性期" if hs_crp > ACUTE else "缓解期" if hs_crp < REMISSION else "过渡期"


def regression(series):
    v = series.dropna().values
    if len(v) < 2: return {}
    x, y = np.arange(len(v)), v.astype(float)
    mx, my = x.mean(), y.mean()
    num = np.sum((x - mx) * (y - my))
    den = np.sum((x - mx) ** 2)
    if den == 0: return {}
    slope = num / den
    r2 = 1 - np.sum((y - (slope * x + (my - slope * mx))) ** 2) / np.sum((y - my) ** 2)
    return {"slope": round(slope, 4), "r2": round(float(r2), 3), "trend": "上升" if slope > 0.1 else "下降" if slope < -0.1 else "平稳"}


def stats(series):
    v = series.dropna().astype(float)
    if len(v) == 0: return {}
    return {"mean": round(float(v.mean()), 3), "std": round(float(v.std(ddof=1)), 3) if len(v) > 1 else 0,
            "min": round(float(v.min()), 3), "max": round(float(v.max()), 3), "count": int(len(v))}


def setup():
    plt.rcParams.update({"font.family": ["WenQuanYi Zen Hei"], "axes.unicode_minus": False})


def save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  ✅ {path.name}")


def plot_trend(df, res, path):
    setup()
    keys = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"]
    n, cols = len(keys), 3
    fig, axs = plt.subplots((n+2)//cols, cols, figsize=(5*cols, 3.5*((n+2)//cols)), facecolor="white")
    axs = axs.flatten() if n > 1 else [axs]
    dates = pd.to_datetime(df["report_date"])

    for i, k in enumerate(keys):
        ax = axs[i]
        if k not in df.columns: ax.axis("off"); continue
        y = df[k].dropna().values.astype(float)
        x = np.arange(len(y))
        ax.plot(x, y, "o-", color="#3498db", lw=2, ms=7)
        if reg := res.get("linear_regression", {}).get(k):
            ax.plot([x.min(), x.max()], [reg["slope"]*x.min()+reg["intercept"], reg["slope"]*x.max()+reg["intercept"]],
                    "--", color="#e74c3c", lw=1.8, label=f"R²={reg['r2']}")
        if ref := REFS.get(k): ax.axhspan(ref[0], ref[1], alpha=0.15, color="green")
        ax.set_xticks(x); ax.set_xticklabels([d.strftime("%m-%d") for d in dates[df[k].notna()]], fontsize=8)
        ax.set_title(k, fontsize=11, fontweight="bold"); ax.grid(True, alpha=0.3)
    [a.axis("off") for a in axs[i+1:]]
    fig.suptitle("关键指标趋势回归", fontsize=14, fontweight="bold")
    plt.tight_layout(); save(fig, path)


def plot_corr(df, path):
    setup()
    keys = ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "PCT", "PLT"]
    cols = [k for k in keys if k in df.columns]
    if len(cols) < 2: return
    corr = df[cols].apply(pd.to_numeric, errors="coerce").corr()
    fig, ax = plt.subplots(figsize=(len(cols)+1, len(cols)), facecolor="white")
    cmap = LinearSegmentedColormap.from_list("rb", ["#e74c3c", "#f8f8f8", "#27ae60"])
    ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(len(cols))); ax.set_yticks(range(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right")
    for xi in range(len(cols)):
        for yi in range(len(cols)):
            v = corr.values[yi, xi]
            ax.text(xi, yi, f"{v:.2f}", ha="center", va="center", fontsize=9,
                    color="white" if abs(v) > 0.5 else "black")
    plt.colorbar(ax.imshow(corr.values, cmap=cmap, vmin=-1, vmax=1), ax=ax, shrink=0.8)
    fig.suptitle("相关性热力图", fontsize=14); plt.tight_layout(); save(fig, path)


def plot_infl(df, res, path):
    setup()
    labels = res.get("inflammation_classification", {}).get("labels", [])
    dates = res.get("inflammation_classification", {}).get("report_dates", [])
    if not labels: return
    fig, ax = plt.subplots(figsize=(len(labels)*1.5+1, 5), facecolor="white")
    colors = [COLORS.get(s, "#95a5a6") for s in labels]
    bars = ax.bar(range(len(labels)), [1]*len(labels), color=colors, width=0.55, edgecolor="white")
    [ax.text(b.get_x()+b.get_width()/2, 0.5, l, ha="center", va="center", fontsize=12, fontweight="bold", color="white")
     for b, l in zip(bars, labels)]
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(dates)
    ax.set_yticks([]); ax.set_xlim(-0.7, len(labels)-0.3); ax.set_ylim(0, 1.3)
    if "hs-CRP" in df.columns:
        [(ax.text(i, 1.1, f"hs-CRP\n{r.get('hs-CRP', ''):.2f}", ha="center", fontsize=8)) for i, (_, r) in enumerate(df.iterrows())]
    ax.legend(handles=[mpatches.Patch(color=c, label=l) for l, c in COLORS.items() if l in labels], loc="upper right")
    fig.suptitle("炎症分期演变", fontsize=14); plt.tight_layout(); save(fig, path)


def plot_abnorm(df, res, path):
    setup()
    abnormal = res.get("abnormal_summary", {})
    if not abnormal: abnormal_metrics = []
    else: abnormal_metrics = sorted(abnormal.keys())
    dates = res.get("inflammation_classification", {}).get("report_dates", [])
    n = len(abnormal_metrics)
    fig, ax = plt.subplots(figsize=(len(dates)*2+2, max(n*0.7+2, 4)), facecolor="white")
    for xi, d in enumerate(dates):
        abnormal_on_date = [m for m in abnormal_metrics if d in abnormal[m].get("abnormal_dates", [])]
        for yi, m in enumerate(abnormal_metrics):
            c = "#e74c3c" if m in abnormal_on_date else "#27ae60"
            ax.scatter(xi, yi, color=c, s=120)
            ax.text(xi+0.12, yi, m, va="center", fontsize=9, color=c)
    ax.set_xticks(range(len(dates))); ax.set_xticklabels(dates)
    ax.set_yticks(range(n)); ax.set_yticklabels([""]*n)
    ax.set_title("异常指标标注（红=异常 绿=正常）", fontsize=13); ax.grid(True, axis="x", alpha=0.3)
    ax.legend(handles=[mpatches.Patch(color=c, label=l) for c, l in [("#e74c3c","异常"),("#27ae60","正常")]], loc="upper right")
    plt.tight_layout(); save(fig, path)


def run(patient_id):
    paths = {"data_dir": WIKI_ROOT / "data" / patient_id,
             "metrics_csv": WIKI_ROOT / "data" / patient_id / "lab_metrics.csv",
             "output_json": WIKI_ROOT / "data" / patient_id / "analysis_results.json",
             "fig_trend": WIKI_ROOT / "data" / patient_id / "fig_01_trend_regression.png",
             "fig_corr": WIKI_ROOT / "data" / patient_id / "fig_02_correlation_heatmap.png",
             "fig_infl": WIKI_ROOT / "data" / patient_id / "fig_03_inflammation_status.png",
             "fig_abnorm": WIKI_ROOT / "data" / patient_id / "fig_04_abnormal_indicators.png"}

    print(f"[{datetime.now().isoformat()}] 分析开始 | 病人: {patient_id}")
    if not paths["metrics_csv"].exists():
        print("❌ 找不到 lab_metrics.csv，请先运行 data_loader.py"); return

    df = pd.read_csv(paths["metrics_csv"])
    df["report_date"] = pd.to_datetime(df["report_date"]).sort_values().reset_index(drop=True)
    print(f"共 {len(df)} 份报告 | {df['report_date'].min().date()} ~ {df['report_date'].max().date()}")

    res = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "n_reports": len(df),
           "date_range": {"start": str(df["report_date"].min().date()), "end": str(df["report_date"].max().date())}}

    # 炎症分类
    infl = [classify(r.get("hs-CRP")) if pd.notna(r.get("hs-CRP")) else "未知" for _, r in df.iterrows()]
    res["inflammation_classification"] = {"labels": infl, "report_dates": df["report_date"].dt.strftime("%Y-%m-%d").tolist()}
    print(f"炎症: {dict(zip(df['report_date'].dt.strftime('%m-%d'), infl))}")

    # 回归趋势
    trend = {k: regression(df[k]) for k in ["hs-CRP", "CRP", "WBC", "NEUT#", "MONO%", "RDW-SD", "RDW-CV"] if k in df.columns}
    res["linear_regression"] = {k: v for k, v in trend.items() if v}
    [print(f"  {k}: slope={v['slope']:.4f}, R²={v['r2']}, trend={v['trend']}") for k, v in res["linear_regression"].items()]

    # 异常指标
    abnormal = {}
    for m, (lo, hi) in REFS.items():
        if m not in df.columns: continue
        dates = df.loc[df[m].notna() & ((df[m] < lo) | (df[m] > hi)), "report_date"].dt.strftime("%Y-%m-%d").tolist()
        if dates: abnormal[m] = {"ref_range": f"{lo}-{hi}", "abnormal_dates": dates}
    res["abnormal_summary"] = abnormal
    print(f"异常指标: {list(abnormal.keys())}")

    # 保存
    paths["data_dir"].mkdir(parents=True, exist_ok=True)
    json.dump(res, open(paths["output_json"], "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("\n📊 绘图...")
    plot_trend(df, res, paths["fig_trend"])
    plot_corr(df, paths["fig_corr"])
    plot_infl(df, res, paths["fig_infl"])
    plot_abnorm(df, res, paths["fig_abnorm"])
    print(f"[{datetime.now().isoformat()}] 完成")


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--patient-id", required=True); args = p.parse_args()
    run(args.patient_id)
