"""dashboard.py — Streamlit 趋势看板

启动:
    pip install "lab-analysis[dashboard]"
    streamlit run lab_analysis/dashboard.py

功能:
    - 侧边栏选择患者 + 运行批次
    - 4 个 Tab: 概览 / 图表 / 数据表 / 最终报告
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from lab_analysis.utils import WORK_ROOT

_DATA_DIR = WORK_ROOT / "data"

st.set_page_config(
    page_title="Lab-Analysis 看板",
    page_icon="📊",
    layout="wide",
)

# ── 侧边栏 ──────────────────────────────────────────────────────────

st.sidebar.title("📊 Lab-Analysis")


def _list_patients() -> list[str]:
    if not _DATA_DIR.exists():
        return []
    return sorted(
        d.name for d in _DATA_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def _list_runs(patient_id: str) -> list[str]:
    p = _DATA_DIR / patient_id
    if not p.exists():
        return []
    return sorted(
        d.name for d in p.iterdir()
        if d.is_dir() and d.name[:8].isdigit()
    )


patients = _list_patients()
if not patients:
    st.warning("未找到任何患者数据。请先运行 Pipeline。")
    st.stop()

selected_patient = st.sidebar.selectbox("选择患者", patients)
runs = _list_runs(selected_patient)
if not runs:
    st.warning(f"患者 {selected_patient} 下无有效运行数据。")
    st.stop()

selected_run = st.sidebar.selectbox("选择运行批次", runs, index=0)
run_dir = _DATA_DIR / selected_patient / selected_run
analyzed_dir = run_dir / "02_analyzed"
figures_dir = analyzed_dir / "figures"
lit_dir = run_dir / "03_literature"
reports_dir = run_dir / "04_reports"

st.sidebar.markdown("---")
st.sidebar.caption(f"患者: {selected_patient}")
st.sidebar.caption(f"批次: {selected_run}")
st.sidebar.button("🔄 刷新", on_click=st.rerun)


# ── 数据加载 ────────────────────────────────────────────────────────

@st.cache_data
def _load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


@st.cache_data
def _load_csv_df(path: Path):
    import pandas as pd
    if path.exists():
        return pd.read_csv(path)
    return None


@st.cache_data
def _load_md(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


analysis_results = _load_json(analyzed_dir / "analysis_results.json")
alerts = _load_json(analyzed_dir / "alerts.json")
lab_metrics = _load_csv_df(analyzed_dir / "lab_metrics.csv")
final_report_md = _load_md(reports_dir / "final_integrated_report.md")


# ── Tab 布局 ────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 统计概览", "📈 图表", "📊 检验数据", "📄 最终报告"]
)

# ═════════════════════════════════════════════════════════════════════
# Tab 1: 概览
# ═════════════════════════════════════════════════════════════════════

with tab1:
    st.header("统计概览")

    # 基本信息
    col1, col2, col3 = st.columns(3)
    with col1:
        n = analysis_results.get("n_reports", "?")
        st.metric("报告数", n)
    with col2:
        dr = analysis_results.get("date_range", {})
        st.metric("日期范围", f"{dr.get('start', '?')} ~ {dr.get('end', '?')}")
    with col3:
        n_alerts = len(alerts)
        st.metric("异常告警", n_alerts)

    # 炎症分期 timeline
    inflam = analysis_results.get("inflammation_classification", {})
    labels = inflam.get("labels", [])
    dates = inflam.get("report_dates", [])
    if labels:
        st.subheader("炎症分期时间线")
        color_map = {"急性期": "🔴", "过渡期": "🟡", "缓解期": "🟢", "未知": "⚪"}
        cols = st.columns(len(labels))
        for i, (d, lbl) in enumerate(zip(dates, labels, strict=True)):
            with cols[i]:
                icon = color_map.get(lbl, "⚪")
                st.markdown(f"**{d}**")
                st.markdown(f"<h1 style='text-align:center'>{icon}</h1>",
                            unsafe_allow_html=True)
                st.markdown(f"<p style='text-align:center'>{lbl}</p>",
                            unsafe_allow_html=True)

    # 异常指标
    abnormal = analysis_results.get("abnormal_summary", {})
    if abnormal:
        st.subheader("异常指标")
        ab_data = []
        for metric, info in abnormal.items():
            ab_data.append({
                "指标": metric,
                "参考范围": info.get("ref_range", "?"),
                "异常次数": info.get("n_abnormal", 0),
                "异常日期": ", ".join(info.get("abnormal_dates", [])),
            })
        if ab_data:
            import pandas as pd
            st.dataframe(pd.DataFrame(ab_data), use_container_width=True)

    # 告警摘要
    if alerts:
        st.subheader("告警摘要")
        alert_df = []
        for a in alerts:
            icons = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}
            alert_df.append({
                "级别": f"{icons.get(a['level'], '')} {a['level']}",
                "来源": a.get("source", ""),
                "指标": a.get("metric", ""),
                "消息": a["message"],
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(alert_df), use_container_width=True)


# ═════════════════════════════════════════════════════════════════════
# Tab 2: 图表
# ═════════════════════════════════════════════════════════════════════

with tab2:
    st.header("分析图表")

    fig_names = [
        ("fig_01_trend_regression.png", "趋势回归"),
        ("fig_02_correlation_heatmap.png", "相关性热力图"),
        ("fig_03_inflammation_status.png", "炎症分期"),
        ("fig_04_abnormal_indicators.png", "异常指标标注"),
        ("fig_05_moving_average.png", "移动平均趋势"),
        ("fig_06_cv_stability.png", "CV 稳定性热力"),
        ("fig_07_zscore_distribution.png", "Z-score 分布"),
    ]

    cols = st.columns(2)
    for i, (fname, title) in enumerate(fig_names):
        fig_path = figures_dir / fname
        with cols[i % 2]:
            st.subheader(title)
            if fig_path.exists():
                st.image(str(fig_path), use_container_width=True)
            else:
                st.caption(f"图表未生成: {fname}")


# ═════════════════════════════════════════════════════════════════════
# Tab 3: 检验数据表
# ═════════════════════════════════════════════════════════════════════

with tab3:
    st.header("检验数据")
    if lab_metrics is not None:
        st.dataframe(lab_metrics, use_container_width=True, hide_index=True)
    else:
        st.info("未找到 lab_metrics.csv")

    # CV 稳定性
    cv_data = analysis_results.get("cv_stability", {})
    if cv_data:
        st.subheader("指标稳定性（CV）")
        cv_rows = []
        for metric, info in cv_data.items():
            risk = info.get("risk_level", "")
            icon = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(risk, "⚪")
            cv_rows.append({
                "指标": metric,
                "CV": f"{info.get('cv', 0):.4f}",
                f"{icon} 稳定性": info.get("stability", ""),
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(cv_rows), use_container_width=True)

    # 回归趋势
    trend = analysis_results.get("linear_regression", {})
    if trend:
        st.subheader("关键指标趋势")
        trend_rows = []
        for metric, info in trend.items():
            arrow = "↑" if info.get("slope", 0) > 0 else "↓" if info.get("slope", 0) < 0 else "→"
            trend_rows.append({
                "指标": metric,
                f"{arrow} 趋势": info.get("trend", "?"),
                "斜率": f"{info.get('slope', 0):.4f}",
                "R²": f"{info.get('r2', 0):.3f}",
            })
        import pandas as pd
        st.dataframe(pd.DataFrame(trend_rows), use_container_width=True)


# ═════════════════════════════════════════════════════════════════════
# Tab 4: 最终报告
# ═════════════════════════════════════════════════════════════════════

with tab4:
    st.header("最终综合报告")
    if final_report_md:
        st.markdown(final_report_md)
    else:
        st.info("未生成最终报告。请先运行完整的 Pipeline。")
