#!/usr/bin/env python3
"""Read-only Streamlit dashboard for locally generated OPC demand snapshots."""

from __future__ import annotations

import html

import streamlit as st

from snapshot_exporter import load_dashboard_snapshot


st.set_page_config(page_title="蓝海机会雷达", page_icon="🌊", layout="wide")


def esc(value) -> str:
    return html.escape(str(value or ""))


def render_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 2.25rem;
            padding-bottom: 4rem;
            max-width: 1180px;
        }
        .hero {
            padding: 34px 0 24px;
        }
        .eyebrow {
            color: #0f766e;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0;
            margin-bottom: 12px;
        }
        .hero h1 {
            color: #111827;
            font-size: 52px;
            line-height: 1.06;
            margin: 0 0 14px;
        }
        .hero p {
            color: #54606f;
            font-size: 18px;
            line-height: 1.65;
            margin: 0;
            max-width: 780px;
        }
        .hero-grid {
            align-items: stretch;
        }
        .radar-panel {
            border: 1px solid #e6e8eb;
            border-radius: 8px;
            background: #ffffff;
            padding: 20px;
            min-height: 230px;
        }
        .radar-title {
            color: #101828;
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 12px;
        }
        .radar-row {
            display: grid;
            grid-template-columns: 92px 1fr 42px;
            gap: 10px;
            align-items: center;
            margin: 12px 0;
            color: #475467;
            font-size: 13px;
        }
        .bar {
            height: 10px;
            border-radius: 999px;
            background: #edf2f7;
            overflow: hidden;
        }
        .bar span {
            display: block;
            height: 10px;
            border-radius: 999px;
            background: #0f766e;
        }
        .bar .orange {
            background: #f97316;
        }
        .bar .blue {
            background: #2563eb;
        }
        .metric-card {
            border: 1px solid #e6e8eb;
            border-radius: 8px;
            padding: 18px;
            background: #ffffff;
            min-height: 112px;
        }
        .metric-label {
            color: #667085;
            font-size: 13px;
            margin-bottom: 8px;
        }
        .metric-value {
            color: #101828;
            font-size: 31px;
            font-weight: 750;
            line-height: 1.1;
        }
        .metric-note {
            color: #98a2b3;
            font-size: 12px;
            margin-top: 8px;
        }
        .idea-card {
            border: 1px solid #e6e8eb;
            border-radius: 8px;
            padding: 18px 18px 14px;
            background: #ffffff;
            margin-bottom: 14px;
        }
        .idea-card h3 {
            color: #111827;
            font-size: 20px;
            line-height: 1.35;
            margin: 12px 0 9px;
        }
        .idea-card p {
            color: #4b5563;
            line-height: 1.6;
            margin: 7px 0;
        }
        .cluster-card {
            border: 1px solid #dfe4ea;
            border-radius: 8px;
            padding: 20px;
            background: #ffffff;
            margin-bottom: 16px;
        }
        .cluster-card h3 {
            color: #101828;
            font-size: 22px;
            line-height: 1.32;
            margin: 12px 0 10px;
        }
        .cluster-card p {
            color: #475467;
            line-height: 1.62;
            margin: 8px 0;
        }
        .cluster-meta {
            display: grid;
            grid-template-columns: repeat(4, minmax(96px, 1fr));
            gap: 10px;
            margin: 14px 0;
        }
        .cluster-meta div {
            border: 1px solid #eef0f3;
            border-radius: 8px;
            padding: 10px;
            background: #fbfcfd;
        }
        .cluster-meta span {
            display: block;
            color: #667085;
            font-size: 12px;
            margin-bottom: 4px;
        }
        .cluster-meta strong {
            color: #101828;
            font-size: 18px;
        }
        .sample-link {
            color: #475467;
            font-size: 13px;
            margin: 4px 0;
        }
        .tag {
            display: inline-block;
            border: 1px solid #d0d5dd;
            border-radius: 999px;
            padding: 3px 9px;
            font-size: 12px;
            color: #344054;
            margin: 0 6px 6px 0;
            background: #ffffff;
        }
        .tag-strong {
            border-color: #99f6e4;
            background: #ecfdf5;
            color: #0f766e;
        }
        .tag-warm {
            border-color: #fed7aa;
            background: #fff7ed;
            color: #c2410c;
        }
        .quiet-box {
            border: 1px solid #e6e8eb;
            border-radius: 8px;
            padding: 18px;
            background: #ffffff;
            margin-bottom: 16px;
        }
        .quiet-box h3 {
            font-size: 17px;
            margin: 0 0 8px;
        }
        .quiet-box p {
            color: #5b6472;
            margin: 0;
            line-height: 1.6;
        }
        @media (max-width: 760px) {
            .hero h1 {
                font-size: 38px;
            }
            .hero p {
                font-size: 16px;
            }
            .radar-row {
                grid-template-columns: 76px 1fr 34px;
            }
            .cluster-meta {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric(label: str, value, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{esc(label)}</div>
            <div class="metric-value">{esc(value)}</div>
            <div class="metric-note">{esc(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state() -> None:
    st.markdown(
        """
        <section class="hero">
            <div class="eyebrow">LOCAL-FIRST DEMAND RADAR</div>
            <h1>蓝海机会雷达</h1>
            <p>线上页面只负责展示。本地扫描完成并提交快照后，这里会展示最新机会看板。</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.info("还没有找到 `data/dashboard_snapshot.json`。请在本地运行：`python3 local_runner.py`。")


def render_radar_panel(summary: dict, decision_summary: dict, repeated_count: int) -> None:
    candidate_count = int(summary.get("candidate_count", 0) or 0)
    monitor_count = int(decision_summary.get("monitor_count", summary.get("monitor_count", 0)) or 0)
    build_now_count = int(decision_summary.get("build_now_count", summary.get("build_now_count", 0)) or 0)
    raw_count = max(int(summary.get("raw_count", 0) or 0), 1)

    candidate_pct = min(100, round(candidate_count / raw_count * 100))
    monitor_pct = min(100, round(monitor_count / max(candidate_count, 1) * 100))
    build_pct = min(100, round(build_now_count / max(candidate_count, 1) * 100))
    repeat_pct = min(100, repeated_count * 20)

    st.markdown(
        f"""
        <div class="radar-panel">
            <div class="radar-title">机会雷达快照</div>
            <div class="radar-row">
                <span>候选率</span><div class="bar"><span style="width:{candidate_pct}%"></span></div><span>{candidate_pct}%</span>
            </div>
            <div class="radar-row">
                <span>可观察</span><div class="bar"><span class="blue" style="width:{monitor_pct}%"></span></div><span>{monitor_pct}%</span>
            </div>
            <div class="radar-row">
                <span>可行动</span><div class="bar"><span class="orange" style="width:{build_pct}%"></span></div><span>{build_pct}%</span>
            </div>
            <div class="radar-row">
                <span>重复信号</span><div class="bar"><span style="width:{repeat_pct}%"></span></div><span>{repeated_count}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_idea_card(idea: dict) -> None:
    verdict = idea.get("verdict", "Monitor")
    verdict_class = "tag-strong" if verdict == "Build Now" else "tag-warm" if verdict == "Monitor" else ""
    st.markdown(
        f"""
        <div class="idea-card">
            <span class="tag">{esc(idea.get("category", "其他/待判定"))}</span>
            <span class="tag {verdict_class}">{esc(verdict)}</span>
            <span class="tag">Score {esc(idea.get("total_score", 0))}</span>
            <span class="tag">7天重复 {esc(idea.get("repeat_7d", 1))}</span>
            <h3>{esc(idea.get("mvp_concept", ""))}</h3>
            <p>{esc(idea.get("pain_summary", ""))}</p>
            <p><strong>下一步：</strong>{esc(idea.get("validation_step", ""))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if idea.get("source_url"):
        st.markdown(f"[来源：{esc(idea.get('source', ''))} - {esc(idea.get('title', ''))}]({idea.get('source_url')})")


def render_cluster_card(cluster: dict) -> None:
    verdict = cluster.get("decision_verdict", "Monitor")
    verdict_class = "tag-strong" if verdict == "Build Now" else "tag-warm" if verdict == "Monitor" else ""
    st.markdown(
        f"""
        <div class="cluster-card">
            <span class="tag">{esc(cluster.get("category", "其他/待判定"))}</span>
            <span class="tag {verdict_class}">{esc(verdict)}</span>
            <span class="tag">Decision {esc(cluster.get("decision_score", 0))}</span>
            <h3>{esc(cluster.get("title", "待验证机会"))}</h3>
            <div class="cluster-meta">
                <div><span>7天重复</span><strong>{esc(cluster.get("count_7d", 0))}</strong></div>
                <div><span>来源数</span><strong>{esc(cluster.get("source_count", 0))}</strong></div>
                <div><span>最高原始分</span><strong>{esc(cluster.get("top_score", 0))}</strong></div>
                <div><span>平均分</span><strong>{esc(cluster.get("avg_score", 0))}</strong></div>
            </div>
            <p>{esc(cluster.get("evidence_summary", ""))}</p>
            <p><strong>判断：</strong>{esc(cluster.get("decision_reason", ""))}</p>
            <p><strong>下一步：</strong>{esc(cluster.get("recommended_action", ""))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    samples = cluster.get("sample_ideas", []) or []
    if samples:
        with st.expander("代表样本", expanded=False):
            for sample in samples:
                title = esc(sample.get("title", "Untitled"))
                source = esc(sample.get("source", ""))
                score = esc(sample.get("total_score", 0))
                if sample.get("source_url"):
                    st.markdown(f"- [{title}]({sample.get('source_url')}) · {source} · Score {score}")
                else:
                    st.markdown(f"- {title} · {source} · Score {score}")


def render_counts_table(title: str, counts: dict, key_name: str) -> None:
    st.subheader(title)
    if counts:
        rows = [
            {key_name: key, "数量": value}
            for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        ]
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info(f"暂无{title}。")


render_styles()
snapshot = load_dashboard_snapshot()

if snapshot is None:
    render_empty_state()
    st.stop()

summary = snapshot.get("summary", {})
decision_summary = snapshot.get("decision_summary", {})
source_health = snapshot.get("source_health", {})
opportunity_clusters = snapshot.get("opportunity_clusters", [])
top_ideas = snapshot.get("top_ideas", [])
repeated = snapshot.get("repeated_signals_7d", [])
generated_at = snapshot.get("generated_at", "未生成")

hero_left, hero_right = st.columns([1.55, 1], gap="large")
with hero_left:
    st.markdown(
        f"""
        <section class="hero">
            <div class="eyebrow">LOCAL-FIRST DEMAND RADAR</div>
            <h1>蓝海机会雷达</h1>
            <p>本地扫描公开信号，GitHub 保存结果快照，Streamlit 只展示机会看板。最近更新：{esc(generated_at)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
with hero_right:
    render_radar_panel(summary, decision_summary, len(repeated))

metric_cols = st.columns(4)
with metric_cols[0]:
    render_metric("候选机会", summary.get("candidate_count", 0), f"原始信号 {summary.get('raw_count', 0)}")
with metric_cols[1]:
    render_metric("Build Now", decision_summary.get("build_now_count", summary.get("build_now_count", 0)), "按需求簇判断")
with metric_cols[2]:
    render_metric("Monitor", decision_summary.get("monitor_count", summary.get("monitor_count", 0)), "继续观察")
with metric_cols[3]:
    render_metric("需求簇", decision_summary.get("total_clusters", len(opportunity_clusters)), f"重复信号 {len(repeated)}")

if summary.get("errors"):
    with st.expander("本地扫描记录的抓取错误", expanded=False):
        for error in summary.get("errors", []):
            st.warning(error)

st.divider()
left, right = st.columns([1.15, 0.85], gap="large")

with left:
    if opportunity_clusters:
        st.subheader("Top 需求簇")
        for cluster in opportunity_clusters:
            render_cluster_card(cluster)
    else:
        st.subheader("Top 机会")
        if not top_ideas:
            st.info("当前快照没有候选机会。")
        for idea in top_ideas:
            render_idea_card(idea)

with right:
    render_counts_table("分类分布", snapshot.get("category_counts", {}), "分类")
    render_counts_table("人工标注", snapshot.get("label_counts", {}), "标注")
    if source_health:
        st.subheader("数据源健康")
        st.markdown(
            f"""
            <div class="quiet-box">
                <h3>{esc(source_health.get("status", "unknown"))} · 错误 {esc(source_health.get("error_count", 0))}</h3>
                <p>原始 {esc(source_health.get("raw_count", 0))} · 去重 {esc(source_health.get("unique_count", 0))} · 候选 {esc(source_health.get("candidate_count", 0))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        counts = source_health.get("source_counts", {})
        if counts:
            render_counts_table("候选来源", counts, "来源")

st.subheader("7 天重复信号")
if repeated:
    for signal in repeated:
        st.markdown(
            f"""
            <div class="quiet-box">
                <h3>{esc(signal.get("category", "其他/待判定"))} · 出现 {esc(signal.get("count", 0))} 次 · 最高分 {esc(signal.get("top_score", 0))}</h3>
                <p>{esc(signal.get("sample_concept", ""))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if signal.get("sample_url"):
            st.markdown(f"[查看样本]({signal.get('sample_url')})")
else:
    st.info("最近 7 天还没有出现 2 次以上的重复信号。")

report = snapshot.get("markdown_report", "")
if report:
    st.subheader("Markdown 日报")
    st.download_button(
        "下载 Markdown 日报",
        data=report,
        file_name=f"demand-report-{generated_at.split(' ')[0]}.md",
        mime="text/markdown",
        width="stretch",
    )
    with st.expander("预览日报", expanded=False):
        st.code(report, language="markdown")
