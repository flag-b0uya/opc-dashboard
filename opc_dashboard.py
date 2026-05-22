#!/usr/bin/env python3
"""Read-only Streamlit dashboard for locally generated OPC demand snapshots."""

from __future__ import annotations

import html

import streamlit as st

from dashboard_presenter import (
    build_action_view,
    build_artifact_summary_rows,
    build_quality_notices,
    build_source_metric_rows,
    evidence_chain_summary,
)
from snapshot_exporter import load_dashboard_snapshot


st.set_page_config(page_title="蓝海机会雷达", page_icon="🌊", layout="wide")


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def render_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --opc-ink: #101828;
            --opc-body: #475467;
            --opc-muted: #667085;
            --opc-faint: #98a2b3;
            --opc-border: #dfe4ea;
            --opc-border-soft: #eef0f3;
            --opc-surface: #ffffff;
            --opc-surface-soft: #f8fafc;
            --opc-surface-glass: rgba(255, 255, 255, 0.84);
            --opc-canvas: #f4f7f8;
            --opc-rail: #d8ebe7;
            --opc-green: #0f766e;
            --opc-blue: #2563eb;
            --opc-amber: #b45309;
            --opc-red: #b42318;
            --opc-coral: #e11d48;
            --opc-shadow: 0 18px 55px rgba(15, 23, 42, 0.08);
        }
        html, body, [data-testid="stAppViewContainer"] {
            font-family: "Source Sans 3", "Noto Sans SC", "PingFang SC", sans-serif;
            color: var(--opc-body);
            background:
                linear-gradient(90deg, rgba(15, 118, 110, 0.055) 1px, transparent 1px),
                linear-gradient(180deg, rgba(37, 99, 235, 0.045) 1px, transparent 1px),
                linear-gradient(180deg, #fbfcfd 0%, var(--opc-canvas) 44%, #ffffff 100%);
            background-size: 44px 44px, 44px 44px, auto;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stToolbar"] {
            right: 1.25rem;
        }
        .block-container {
            padding-top: 1.7rem;
            padding-bottom: 4rem;
            max-width: 1220px;
        }
        .dashboard-shell {
            border: 1px solid rgba(15, 118, 110, 0.16);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.94), rgba(248,250,252,0.86)),
                repeating-linear-gradient(90deg, transparent 0 68px, rgba(15,118,110,0.035) 68px 69px);
            box-shadow: var(--opc-shadow);
            padding: 22px;
            margin-bottom: 18px;
            position: relative;
            overflow: hidden;
        }
        .dashboard-shell:before {
            content: "";
            position: absolute;
            inset: 0;
            border-top: 3px solid var(--opc-green);
            pointer-events: none;
        }
        .dashboard-shell:after {
            content: "";
            position: absolute;
            left: 22px;
            right: 22px;
            bottom: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--opc-green), var(--opc-blue), var(--opc-amber), var(--opc-coral));
            opacity: 0.85;
        }
        .signal-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 12px 0 0;
        }
        .signal-pill {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            border: 1px solid rgba(15, 118, 110, 0.18);
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.72);
            color: var(--opc-body);
            font-size: 13px;
            padding: 7px 11px;
            min-height: 34px;
        }
        .signal-pill b {
            color: var(--opc-ink);
            font-weight: 750;
        }
        .signal-dot {
            width: 7px;
            height: 7px;
            border-radius: 999px;
            background: var(--opc-green);
            box-shadow: 0 0 0 4px rgba(15,118,110,0.12);
        }
        .hero {
            padding: 4px 0 12px;
        }
        .eyebrow {
            color: var(--opc-green);
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0;
            margin-bottom: 12px;
        }
        .hero h1 {
            color: var(--opc-ink);
            font-size: 54px;
            line-height: 1.06;
            margin: 0 0 14px;
            max-width: 820px;
        }
        .hero p {
            color: var(--opc-body);
            font-size: 18px;
            line-height: 1.65;
            margin: 0;
            max-width: 780px;
        }
        .hero-grid {
            align-items: stretch;
        }
        .radar-panel {
            border: 1px solid rgba(15, 118, 110, 0.18);
            border-radius: 8px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.92), rgba(248,250,252,0.92)),
                repeating-linear-gradient(135deg, transparent 0 14px, rgba(15,118,110,0.035) 14px 15px);
            padding: 20px;
            min-height: 230px;
            box-shadow: 0 14px 38px rgba(15, 23, 42, 0.07);
        }
        .radar-title {
            color: var(--opc-ink);
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
            color: var(--opc-body);
            font-size: 13px;
        }
        .bar {
            height: 10px;
            border-radius: 999px;
            background: #e6edf2;
            overflow: hidden;
            position: relative;
        }
        .bar span {
            display: block;
            height: 10px;
            border-radius: 999px;
            background: linear-gradient(90deg, var(--opc-green), #14b8a6);
        }
        .bar .orange {
            background: linear-gradient(90deg, #f97316, var(--opc-amber));
        }
        .bar .blue {
            background: linear-gradient(90deg, var(--opc-blue), #38bdf8);
        }
        .metric-card {
            border: 1px solid rgba(16, 24, 40, 0.09);
            border-radius: 8px;
            padding: 18px;
            background: var(--opc-surface-glass);
            min-height: 112px;
            box-shadow: 0 12px 32px rgba(15, 23, 42, 0.055);
        }
        .metric-label {
            color: var(--opc-muted);
            font-size: 13px;
            margin-bottom: 8px;
        }
        .metric-value {
            color: var(--opc-ink);
            font-size: 31px;
            font-weight: 750;
            line-height: 1.1;
        }
        .metric-note {
            color: var(--opc-faint);
            font-size: 12px;
            margin-top: 8px;
        }
        .summary-box {
            border: 1px solid rgba(15, 118, 110, 0.16);
            border-radius: 8px;
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(248,250,252,0.88));
            padding: 20px;
            margin: 8px 0 20px;
            box-shadow: 0 12px 30px rgba(15, 23, 42, 0.045);
        }
        .summary-box h2 {
            color: var(--opc-ink);
            font-size: 24px;
            line-height: 1.35;
            margin: 0 0 10px;
        }
        .summary-box p {
            color: var(--opc-body);
            line-height: 1.7;
            margin: 7px 0;
        }
        .idea-card {
            border: 1px solid var(--opc-border);
            border-radius: 8px;
            padding: 18px 18px 14px;
            background: var(--opc-surface-glass);
            margin-bottom: 14px;
        }
        .idea-card h3 {
            color: var(--opc-ink);
            font-size: 20px;
            line-height: 1.35;
            margin: 12px 0 9px;
        }
        .idea-card p {
            color: var(--opc-body);
            line-height: 1.6;
            margin: 7px 0;
        }
        .cluster-card {
            border: 1px solid rgba(16, 24, 40, 0.10);
            border-radius: 8px;
            padding: 22px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.97), rgba(252,253,254,0.96)),
                linear-gradient(90deg, rgba(15,118,110,0.09), transparent 28%);
            margin-bottom: 20px;
            box-shadow: var(--opc-shadow);
            position: relative;
            overflow: hidden;
        }
        .cluster-card:before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            width: 4px;
            background: linear-gradient(180deg, var(--opc-green), var(--opc-blue));
        }
        .section-band {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            margin: 22px 0 14px;
            padding: 12px 14px;
            border: 1px solid rgba(15,118,110,0.14);
            border-radius: 8px;
            background: rgba(255,255,255,0.74);
        }
        .section-band h2 {
            color: var(--opc-ink);
            font-size: 20px;
            margin: 0;
        }
        .section-band span {
            color: var(--opc-muted);
            font-size: 13px;
        }
        .cluster-kicker {
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 6px;
            margin-bottom: 6px;
        }
        .cluster-card h3 {
            color: var(--opc-ink);
            font-size: 24px;
            line-height: 1.32;
            margin: 8px 0 12px;
        }
        .cluster-card p {
            color: var(--opc-body);
            line-height: 1.68;
            margin: 8px 0;
            font-size: 16px;
        }
        .cluster-meta {
            display: grid;
            grid-template-columns: repeat(4, minmax(96px, 1fr));
            gap: 10px;
            margin: 14px 0;
        }
        .cluster-meta div {
            border: 1px solid var(--opc-border-soft);
            border-radius: 8px;
            padding: 10px;
            background: rgba(248,250,252,0.82);
        }
        .cluster-meta span {
            display: block;
            color: var(--opc-muted);
            font-size: 12px;
            margin-bottom: 4px;
        }
        .cluster-meta strong {
            color: var(--opc-ink);
            font-size: 18px;
        }
        .analysis-section {
            margin: 12px 0;
        }
        .analysis-section strong {
            color: var(--opc-ink);
        }
        .anti-list {
            color: var(--opc-body);
            line-height: 1.58;
            margin: 6px 0 10px 18px;
            padding: 0;
        }
        .anti-list li {
            margin: 4px 0;
        }
        .evidence-chain {
            border: 1px solid rgba(15,118,110,0.13);
            border-radius: 8px;
            margin: 14px 0;
            padding: 12px;
            background: linear-gradient(180deg, rgba(248,250,252,0.94), rgba(255,255,255,0.88));
        }
        .evidence-chain h4 {
            color: var(--opc-ink);
            font-size: 16px;
            margin: 0 0 10px;
        }
        .evidence-row {
            display: grid;
            grid-template-columns: 64px 180px 1fr;
            gap: 10px;
            align-items: start;
            padding: 8px 0;
            color: var(--opc-body);
            font-size: 14px;
            border-top: 1px solid #f3f4f6;
        }
        .evidence-row:first-of-type {
            border-top: none;
        }
        .evidence-pass {
            color: var(--opc-green);
            font-weight: 700;
        }
        .evidence-miss {
            color: var(--opc-amber);
            font-weight: 700;
        }
        .evidence-label {
            color: var(--opc-ink);
            font-weight: 650;
        }
        .quality-notice {
            border: 1px solid var(--opc-border);
            border-radius: 8px;
            padding: 14px 16px;
            margin: 10px 0;
            background: rgba(255,255,255,0.82);
        }
        .quality-notice h3 {
            color: var(--opc-ink);
            font-size: 16px;
            margin: 0 0 4px;
        }
        .quality-notice p {
            color: var(--opc-body);
            margin: 0;
            line-height: 1.55;
        }
        .quality-warning {
            border-color: #fed7aa;
            background: #fffbeb;
        }
        .quality-success {
            border-color: #99f6e4;
            background: #ecfdf5;
        }
        .sample-link {
            color: var(--opc-body);
            font-size: 13px;
            margin: 4px 0;
        }
        .source-row {
            display: grid;
            grid-template-columns: minmax(120px, 1fr) 46px;
            gap: 10px;
            align-items: center;
            margin: 10px 0;
        }
        .source-name {
            color: #344054;
            font-size: 13px;
            margin-bottom: 5px;
        }
        .source-bar {
            height: 8px;
            border-radius: 999px;
            background: #edf2f7;
            overflow: hidden;
        }
        .source-bar span {
            display: block;
            height: 8px;
            border-radius: 999px;
            background: var(--opc-green);
        }
        .source-count {
            color: var(--opc-muted);
            font-size: 13px;
            text-align: right;
        }
        .tag {
            display: inline-block;
            border: 1px solid #d0d5dd;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 12px;
            color: #344054;
            margin: 0 6px 6px 0;
            background: rgba(255,255,255,0.82);
        }
        .tag-strong {
            border-color: #99f6e4;
            background: #ecfdf5;
            color: var(--opc-green);
        }
        .tag-warm {
            border-color: #fed7aa;
            background: #fff7ed;
            color: #c2410c;
        }
        .quiet-box {
            border: 1px solid var(--opc-border);
            border-radius: 8px;
            padding: 18px;
            background: var(--opc-surface);
            margin-bottom: 16px;
        }
        .quiet-box h3 {
            font-size: 17px;
            margin: 0 0 8px;
        }
        .quiet-box p {
            color: var(--opc-body);
            margin: 0;
            line-height: 1.6;
        }
        .action-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            margin: 14px 0;
        }
        .action-box {
            border: 1px solid rgba(15,118,110,0.15);
            border-radius: 8px;
            background: linear-gradient(180deg, rgba(248,250,252,0.95), rgba(255,255,255,0.9));
            padding: 12px;
            min-height: 96px;
        }
        .action-box span {
            display: block;
            color: var(--opc-muted);
            font-size: 12px;
            margin-bottom: 5px;
        }
        .action-box strong {
            color: var(--opc-ink);
            font-size: 18px;
        }
        .asset-box {
            border: 1px solid var(--opc-border-soft);
            border-radius: 8px;
            padding: 12px;
            background: #fcfcfd;
            margin: 10px 0;
        }
        .asset-box h4 {
            color: var(--opc-ink);
            font-size: 15px;
            margin: 0 0 6px;
        }
        .asset-box p, .asset-box li {
            color: var(--opc-body);
            font-size: 14px;
            line-height: 1.55;
        }
        button, [role="button"], .stDownloadButton button {
            min-height: 44px;
        }
        @media (max-width: 760px) {
            .block-container {
                padding-top: 1.25rem;
            }
            .dashboard-shell {
                padding: 16px;
            }
            .section-band {
                align-items: flex-start;
                flex-direction: column;
            }
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
            .action-grid {
                grid-template-columns: 1fr;
            }
            .cluster-card {
                padding: 16px;
            }
            .cluster-card h3 {
                font-size: 21px;
            }
            .evidence-row {
                grid-template-columns: 1fr;
                gap: 3px;
            }
        }
        @media (max-width: 520px) {
            .cluster-meta {
                grid-template-columns: 1fr;
            }
            .metric-card {
                min-height: auto;
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


def decision_label(verdict: str) -> str:
    if verdict == "Build Now":
        return "立即验证"
    if verdict == "Monitor":
        return "继续观察"
    return "暂不投入"


def render_executive_summary(summary: dict, decision_summary: dict, source_stats: dict) -> None:
    build_now = int(decision_summary.get("build_now_count", 0) or 0)
    monitor = int(decision_summary.get("monitor_count", 0) or 0)
    discard = int(decision_summary.get("discard_count", 0) or 0)
    total_clusters = int(decision_summary.get("total_clusters", 0) or 0)
    raw_count = int(summary.get("raw_count", 0) or 0)
    candidate_count = int(summary.get("candidate_count", 0) or 0)
    top_platform = ""
    platforms = source_stats.get("platforms", []) if source_stats else []
    if platforms:
        top_platform = f"主要来源是 {platforms[0].get('name')}，贡献 {platforms[0].get('percent', 0)}% 候选信号。"

    if build_now:
        headline = f"今天有 {build_now} 个需求簇值得立即验证"
        detail = "这些机会同时满足高分、重复信号、明确场景和可执行验证动作。"
    else:
        headline = "今天没有足够可信的立即开工机会"
        detail = "当前信号更适合继续观察：有讨论热度，但证据链还不够完整，或带有明显泛创业/自推噪音。"

    st.markdown(
        f"""
        <div class="summary-box">
            <h2>{esc(headline)}</h2>
            <p>{esc(detail)}</p>
            <p>本次扫描 {esc(raw_count)} 条原始信号，筛出 {esc(candidate_count)} 条候选，合并为 {esc(total_clusters)} 个需求簇：
            {esc(build_now)} 个立即验证，{esc(monitor)} 个继续观察，{esc(discard)} 个暂不投入。{esc(top_platform)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_signal_strip(summary: dict, analysis_label: str, generated_at: str) -> str:
    raw_count = int(summary.get("raw_count", 0) or 0)
    candidate_count = int(summary.get("candidate_count", 0) or 0)
    saved_count = int(summary.get("saved_count", 0) or 0)
    error_count = len(summary.get("errors", []) or [])
    candidate_rate = round(candidate_count / max(raw_count, 1) * 100)
    return f"""
        <div class="signal-strip">
            <div class="signal-pill"><span class="signal-dot"></span><b>{esc(candidate_rate)}%</b> 候选率</div>
            <div class="signal-pill"><span class="signal-dot"></span><b>{esc(saved_count)}</b> 条写入历史</div>
            <div class="signal-pill"><span class="signal-dot"></span><b>{esc(error_count)}</b> 个来源错误</div>
            <div class="signal-pill"><span class="signal-dot"></span><b>{esc(analysis_label)}</b> 分析状态</div>
            <div class="signal-pill"><span class="signal-dot"></span><b>{esc(generated_at)}</b> 快照时间</div>
        </div>
        """


def render_quality_notices(notices: list) -> None:
    if not notices:
        return
    for notice in notices:
        level = notice.get("level", "info")
        css_class = "quality-success" if level == "success" else "quality-warning" if level == "warning" else ""
        st.markdown(
            f"""
            <div class="quality-notice {css_class}">
                <h3>{esc(notice.get("title", ""))}</h3>
                <p>{esc(notice.get("body", ""))}</p>
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


def render_evidence_chain(chain: dict) -> str:
    if not chain:
        return (
            '<div class="evidence-chain">'
            "<h4>证据链完整度：未评估</h4>"
            '<div class="evidence-row">'
            '<div class="evidence-miss">缺口</div>'
            '<div class="evidence-label">证据链数据</div>'
            "<div>当前快照缺少 evidence_chain 字段，请重新生成报告。</div>"
            "</div>"
            "</div>"
        )
    summary = evidence_chain_summary({"evidence_chain": chain})
    rows = []
    for item in chain.get("items", []) or []:
        passed = bool(item.get("passed"))
        status_class = "evidence-pass" if passed else "evidence-miss"
        status_text = "通过" if passed else "缺口"
        rows.append(
            '<div class="evidence-row">'
            f'<div class="{status_class}">{status_text}</div>'
            f'<div class="evidence-label">{esc(item.get("label", ""))}</div>'
            f'<div>{esc(item.get("detail", ""))}</div>'
            "</div>"
        )
    score_text = f"{esc(summary.get('passed_count', 0))}/{esc(summary.get('total_count', 0))}"
    return (
        '<div class="evidence-chain">'
        f"<h4>证据链完整度：{score_text} · {esc(summary.get('label', ''))}</h4>"
        f"{''.join(rows)}"
        "</div>"
    )


def render_action_view(cluster: dict) -> str:
    action = build_action_view(cluster)
    funnel = action["funnel"]
    blockers = "".join(f"<li>{esc(item)}</li>" for item in funnel.get("blockers", []) if item)
    blocker_html = f'<ul class="anti-list">{blockers}</ul>' if blockers else "<p>暂无漏斗阻塞项。</p>"
    return f"""
        <div class="action-grid">
            <div class="action-box"><span>Funnel Verdict</span><strong>{esc(funnel.get("verdict", "未评估"))}</strong></div>
            <div class="action-box"><span>Funnel Score</span><strong>{esc(funnel.get("total_score", 0))}</strong></div>
            <div class="action-box"><span>Risk Penalty</span><strong>{esc(funnel.get("risk_penalty", 0))}</strong></div>
        </div>
        <p class="analysis-section"><strong>漏斗拆分：</strong>Competitor {esc(funnel.get("competitor_score", 0))} · Distribution {esc(funnel.get("distribution_score", 0))}</p>
        <p class="analysis-section"><strong>下一步动作：</strong>{esc(action.get("next_step", ""))}</p>
        <div class="analysis-section"><strong>漏斗阻塞：</strong>{blocker_html}</div>
    """


def render_cluster_card(cluster: dict) -> None:
    verdict = cluster.get("decision_verdict", "Monitor")
    verdict_class = "tag-strong" if verdict == "Build Now" else "tag-warm" if verdict == "Monitor" else ""
    label = decision_label(verdict)
    anti_signals = cluster.get("anti_signals") or cluster.get("codex_anti_signals") or []
    anti_items = "".join(f"<li>{esc(item)}</li>" for item in anti_signals if item)
    anti_html = (
        f'<div class="analysis-section"><strong>反信号：</strong><ul class="anti-list">{anti_items}</ul></div>'
        if anti_items
        else ""
    )
    evidence_chain = render_evidence_chain(cluster.get("evidence_chain", {}))
    opportunity_hypothesis = cluster.get("opportunity_hypothesis") or cluster.get("codex_opportunity_thesis") or ""
    evidence = cluster.get("evidence") or cluster.get("evidence_summary") or ""
    not_build_now_reason = cluster.get("not_build_now_reason") or cluster.get("decision_reason") or ""
    seven_day_validation = cluster.get("seven_day_validation") or cluster.get("recommended_action") or ""
    paid_signal = cluster.get("paid_signal") or "尚未形成明确付费信号。"
    action_view = render_action_view(cluster)
    st.markdown(
        f"""
        <div class="cluster-card">
            <div class="cluster-kicker">
                <span class="tag {verdict_class}">{esc(label)}</span>
                <span class="tag">判断分 {esc(cluster.get("decision_score", 0))}</span>
                <span class="tag">{esc(cluster.get("category", "其他/待判定"))}</span>
            </div>
            <h3>{esc(cluster.get("title", "待验证机会"))}</h3>
            {evidence_chain}
            <div class="cluster-meta">
                <div><span>7天重复</span><strong>{esc(cluster.get("count_7d", 0))}</strong></div>
                <div><span>来源数</span><strong>{esc(cluster.get("source_count", 0))}</strong></div>
                <div><span>最高原始分</span><strong>{esc(cluster.get("top_score", 0))}</strong></div>
                <div><span>平均分</span><strong>{esc(cluster.get("avg_score", 0))}</strong></div>
            </div>
            <p class="analysis-section"><strong>机会假设：</strong>{esc(opportunity_hypothesis)}</p>
            <p class="analysis-section"><strong>证据：</strong>{esc(evidence)}</p>
            <p class="analysis-section"><strong>付费信号：</strong>{esc(paid_signal)}</p>
            <p class="analysis-section"><strong>为什么不是立即开工：</strong>{esc(not_build_now_reason)}</p>
            {anti_html}
            <p class="analysis-section"><strong>7天验证动作：</strong>{esc(seven_day_validation)}</p>
            {action_view}
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


def render_source_stats(source_stats: dict) -> None:
    st.subheader("来源统计")
    if not source_stats or not source_stats.get("total_candidates"):
        st.info("暂无来源统计。")
        return

    st.caption(f"按候选信号统计，共 {source_stats.get('total_candidates', 0)} 条。")
    for platform in source_stats.get("platforms", []):
        percent = int(platform.get("percent", 0) or 0)
        st.markdown(
            f"""
            <div class="source-row">
                <div>
                    <div class="source-name">{esc(platform.get("name", ""))}</div>
                    <div class="source-bar"><span style="width:{percent}%"></span></div>
                </div>
                <div class="source-count">{esc(platform.get("count", 0))} · {esc(percent)}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    top_sources = source_stats.get("top_sources", [])
    if top_sources:
        with st.expander("具体来源排行", expanded=False):
            rows = [
                {
                    "来源": item.get("source", ""),
                    "候选数": item.get("count", 0),
                    "占比": f"{item.get('percent', 0)}%",
                }
                for item in top_sources
            ]
            st.dataframe(rows, width="stretch", hide_index=True)


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


def render_source_health(source_health: dict) -> None:
    if not source_health:
        return
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


def render_source_metrics(source_metrics: list) -> None:
    st.subheader("Source Metrics")
    rows = build_source_metric_rows(source_metrics)
    if not rows:
        st.info("暂无 source metrics。")
        return
    st.caption("按 raw/candidate/cluster/validation 反馈判断数据源投入策略。")
    st.dataframe(rows, width="stretch", hide_index=True)


def render_artifact_summaries(snapshot: dict) -> None:
    rows = build_artifact_summary_rows(
        snapshot.get("container_summary", {}),
        snapshot.get("pain_signal_summary", {}),
    )
    if not rows:
        return
    st.subheader("Discovery Artifacts")
    st.dataframe(rows, width="stretch", hide_index=True)


def render_repeated_signals(repeated: list) -> None:
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


def render_markdown_report(report: str, generated_at: str) -> None:
    if not report:
        return
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


def render_audit_appendix(snapshot: dict, source_stats: dict, source_health: dict, repeated: list, generated_at: str) -> None:
    with st.expander("审计附录：来源、分类、历史和日报", expanded=False):
        st.caption("这些内容用于追溯和复核，不参与第一眼的行动判断。")
        source_col, category_col = st.columns([1, 1], gap="large")
        with source_col:
            render_source_stats(source_stats)
            render_source_health(source_health)
            render_source_metrics(snapshot.get("source_metrics", []))
        with category_col:
            render_counts_table("分类分布", snapshot.get("category_counts", {}), "分类")
            render_counts_table("人工标注", snapshot.get("label_counts", {}), "标注")
        render_repeated_signals(repeated)
        render_markdown_report(snapshot.get("markdown_report", ""), generated_at)


render_styles()
snapshot = load_dashboard_snapshot()

if snapshot is None:
    render_empty_state()
    st.stop()

summary = snapshot.get("summary", {})
decision_summary = snapshot.get("decision_summary", {})
source_health = snapshot.get("source_health", {})
source_stats = snapshot.get("source_stats", {})
opportunity_clusters = snapshot.get("opportunity_clusters", [])
top_ideas = snapshot.get("top_ideas", [])
repeated = snapshot.get("repeated_signals_7d", [])
generated_at = snapshot.get("generated_at", "未生成")
analysis_metadata = snapshot.get("analysis_metadata", {})
analysis_label = (
    f"{analysis_metadata.get('analysis_provider', 'heuristic')} / "
    f"{analysis_metadata.get('analysis_status', 'local')}"
)

hero_left, hero_right = st.columns([1.55, 1], gap="large")
with hero_left:
    st.markdown(
        f"""
        <section class="hero dashboard-shell">
            <div class="eyebrow">HYPERFRAMES PERSONAL RADAR · LOCAL-FIRST</div>
            <h1>OPC Pain Intelligence</h1>
            <p>把公开信号、人工线索和漏斗评分压成一张个人机会驾驶舱。今天只看证据链、付费暗示和下一步验证动作。</p>
            {render_signal_strip(summary, analysis_label, generated_at)}
        </section>
        """,
        unsafe_allow_html=True,
    )
with hero_right:
    render_radar_panel(summary, decision_summary, len(repeated))

render_executive_summary(summary, decision_summary, source_stats)
render_quality_notices(build_quality_notices(snapshot))

metric_cols = st.columns(4)
with metric_cols[0]:
    render_metric("候选机会", summary.get("candidate_count", 0), f"原始信号 {summary.get('raw_count', 0)}")
with metric_cols[1]:
    render_metric("立即验证", decision_summary.get("build_now_count", summary.get("build_now_count", 0)), "证据链完整")
with metric_cols[2]:
    render_metric("继续观察", decision_summary.get("monitor_count", summary.get("monitor_count", 0)), "等待更多重复")
with metric_cols[3]:
    render_metric("需求簇", decision_summary.get("total_clusters", len(opportunity_clusters)), f"重复信号 {len(repeated)}")

if summary.get("errors"):
    with st.expander("本地扫描记录的抓取错误", expanded=False):
        for error in summary.get("errors", []):
            st.warning(error)

st.divider()
if opportunity_clusters:
    st.markdown(
        """
        <div class="section-band">
            <h2>今日机会决策备忘录</h2>
            <span>按 funnel score、证据链完整度和下一步动作排序阅读</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for cluster in opportunity_clusters:
        render_cluster_card(cluster)
else:
    st.subheader("Top 机会")
    if not top_ideas:
        st.info("当前快照没有候选机会。")
    for idea in top_ideas:
        render_idea_card(idea)

render_audit_appendix(snapshot, source_stats, source_health, repeated, generated_at)
