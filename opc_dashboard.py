#!/usr/bin/env python3
"""Read-only Streamlit dashboard for locally generated OPC demand snapshots."""

from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List

import streamlit as st

from dashboard_presenter import (
    build_action_view,
    build_artifact_summary_rows,
    build_quality_notices,
    build_source_metric_rows,
    evidence_chain_summary,
)
from snapshot_exporter import load_dashboard_snapshot


st.set_page_config(page_title="OPC Pain Intelligence", layout="wide")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def percent(part: int, total: int) -> int:
    return max(0, min(100, round(part / max(total, 1) * 100)))


def verdict_label(verdict: str) -> str:
    labels = {
        "Build Now": "立即验证",
        "Validate Manually": "人工验证",
        "Monitor": "继续观察",
        "Discard": "暂不投入",
    }
    return labels.get(verdict or "", verdict or "未判定")


def verdict_class(verdict: str) -> str:
    if verdict in {"Build Now", "Validate Manually"}:
        return "is-build"
    if verdict == "Monitor":
        return "is-monitor"
    if verdict == "Discard":
        return "is-discard"
    return "is-neutral"


def render_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --ink: #101828;
            --body: #475467;
            --muted: #667085;
            --faint: #8a96a8;
            --line: #dfe4ea;
            --line-soft: #edf1f5;
            --surface: #ffffff;
            --soft: #f8fafc;
            --canvas: #f3f7f8;
            --green: #0f766e;
            --blue: #2563eb;
            --amber: #b45309;
            --red: #b42318;
            --rose: #be123c;
            --violet: #5b21b6;
            --shadow: 0 18px 44px rgba(16, 24, 40, 0.08);
            --shadow-soft: 0 10px 28px rgba(16, 24, 40, 0.055);
        }
        html,
        body,
        [data-testid="stAppViewContainer"] {
            color: var(--body);
            font-family: "Source Sans 3", "Noto Sans SC", "PingFang SC", sans-serif;
            background:
                linear-gradient(90deg, rgba(16,24,40,0.035) 1px, transparent 1px),
                linear-gradient(180deg, rgba(15,118,110,0.042) 1px, transparent 1px),
                linear-gradient(180deg, #fbfcfd 0%, var(--canvas) 48%, #ffffff 100%);
            background-size: 48px 48px, 48px 48px, auto;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stToolbar"] {
            right: 1rem;
        }
        .block-container {
            max-width: 1280px;
            padding-top: 1.4rem;
            padding-bottom: 4rem;
        }
        h1, h2, h3, h4 {
            color: var(--ink);
            letter-spacing: 0;
        }
        button,
        [role="button"],
        .stDownloadButton button {
            min-height: 44px;
        }
        .hf-stage {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(16, 24, 40, 0.1);
            border-radius: 8px;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.96), rgba(248,250,252,0.88)),
                repeating-linear-gradient(135deg, rgba(15,118,110,0.045) 0 1px, transparent 1px 18px);
            box-shadow: var(--shadow);
            padding: 22px;
            margin-bottom: 18px;
        }
        .hf-stage:before {
            content: "";
            position: absolute;
            inset: 0;
            border-top: 3px solid var(--green);
            pointer-events: none;
        }
        .hf-stage:after {
            content: "";
            position: absolute;
            left: 22px;
            right: 22px;
            bottom: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--green), var(--blue), var(--amber), var(--rose));
            opacity: 0.9;
        }
        .control-top {
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
            gap: 22px;
            align-items: stretch;
        }
        .identity {
            min-height: 245px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            gap: 18px;
        }
        .kicker {
            color: var(--green);
            font-size: 13px;
            font-weight: 760;
            text-transform: uppercase;
            letter-spacing: 0;
            margin-bottom: 12px;
        }
        .identity h1 {
            font-size: 58px;
            line-height: 1.02;
            margin: 0;
            max-width: 850px;
            font-weight: 860;
        }
        .identity p {
            max-width: 760px;
            margin: 14px 0 0;
            color: var(--body);
            font-size: 18px;
            line-height: 1.62;
        }
        .status-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        .status-pill {
            display: inline-grid;
            grid-template-columns: 8px auto;
            align-items: center;
            gap: 8px;
            border: 1px solid rgba(15,118,110,0.18);
            border-radius: 8px;
            background: rgba(255,255,255,0.72);
            color: var(--body);
            padding: 8px 10px;
            min-height: 38px;
            font-size: 13px;
        }
        .status-pill:before {
            content: "";
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--green);
            box-shadow: 0 0 0 4px rgba(15,118,110,0.11);
        }
        .status-pill b {
            color: var(--ink);
            font-weight: 760;
            font-variant-numeric: tabular-nums;
        }
        .scene-panel {
            border: 1px solid rgba(16,24,40,0.1);
            border-radius: 8px;
            background: rgba(255,255,255,0.78);
            box-shadow: var(--shadow-soft);
            padding: 18px;
        }
        .scene-panel h2 {
            margin: 0 0 14px;
            font-size: 18px;
        }
        .radar-row {
            display: grid;
            grid-template-columns: 86px minmax(0, 1fr) 44px;
            gap: 10px;
            align-items: center;
            padding: 9px 0;
            color: var(--body);
            font-size: 13px;
        }
        .rail {
            height: 9px;
            border-radius: 999px;
            background: #e8eef2;
            overflow: hidden;
        }
        .rail span {
            display: block;
            height: 100%;
            width: 0;
            border-radius: inherit;
            background: linear-gradient(90deg, var(--green), #14b8a6);
        }
        .rail span.blue {
            background: linear-gradient(90deg, var(--blue), #38bdf8);
        }
        .rail span.amber {
            background: linear-gradient(90deg, #f59e0b, var(--amber));
        }
        .rail span.rose {
            background: linear-gradient(90deg, var(--rose), var(--violet));
        }
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 12px;
            margin: 18px 0;
        }
        .metric-tile {
            border: 1px solid rgba(16,24,40,0.09);
            border-radius: 8px;
            background: rgba(255,255,255,0.84);
            box-shadow: var(--shadow-soft);
            padding: 16px;
            min-height: 112px;
        }
        .metric-tile span {
            display: block;
            color: var(--muted);
            font-size: 13px;
            margin-bottom: 9px;
        }
        .metric-tile strong {
            display: block;
            color: var(--ink);
            font-size: 34px;
            line-height: 1;
            font-weight: 840;
            font-variant-numeric: tabular-nums;
        }
        .metric-tile em {
            display: block;
            color: var(--faint);
            font-size: 12px;
            font-style: normal;
            margin-top: 9px;
        }
        .section-title {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 14px;
            border-bottom: 1px solid var(--line);
            padding: 4px 0 11px;
            margin: 14px 0 16px;
        }
        .section-title h2 {
            margin: 0;
            font-size: 22px;
        }
        .section-title span {
            color: var(--muted);
            font-size: 13px;
        }
        .brief {
            border: 1px solid rgba(16,24,40,0.1);
            border-radius: 8px;
            background: rgba(255,255,255,0.82);
            box-shadow: var(--shadow-soft);
            padding: 18px;
            margin-bottom: 16px;
        }
        .brief h2 {
            margin: 0 0 8px;
            font-size: 24px;
            line-height: 1.25;
        }
        .brief p {
            margin: 7px 0;
            color: var(--body);
            font-size: 16px;
            line-height: 1.65;
        }
        .memo {
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(16,24,40,0.11);
            border-radius: 8px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.98), rgba(250,252,253,0.96)),
                linear-gradient(90deg, rgba(15,118,110,0.08), transparent 34%);
            box-shadow: var(--shadow);
            padding: 22px;
            margin-bottom: 18px;
        }
        .memo:before {
            content: "";
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: linear-gradient(180deg, var(--green), var(--blue));
        }
        .memo-head {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 14px;
            align-items: start;
        }
        .memo h3 {
            margin: 8px 0 0;
            color: var(--ink);
            font-size: 25px;
            line-height: 1.28;
        }
        .memo-score {
            min-width: 92px;
            text-align: right;
            color: var(--ink);
            font-weight: 840;
            font-size: 36px;
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }
        .memo-score span {
            display: block;
            color: var(--muted);
            font-size: 12px;
            font-weight: 650;
            margin-top: 5px;
        }
        .tag-row {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        .tag {
            display: inline-flex;
            align-items: center;
            min-height: 28px;
            border: 1px solid #d0d5dd;
            border-radius: 8px;
            background: rgba(255,255,255,0.86);
            color: #344054;
            font-size: 12px;
            font-weight: 650;
            padding: 4px 9px;
        }
        .tag.is-build {
            border-color: #99f6e4;
            background: #ecfdf5;
            color: var(--green);
        }
        .tag.is-monitor {
            border-color: #fed7aa;
            background: #fff7ed;
            color: #c2410c;
        }
        .tag.is-discard {
            border-color: #fecaca;
            background: #fef2f2;
            color: var(--red);
        }
        .memo-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1px;
            border: 1px solid var(--line-soft);
            border-radius: 8px;
            overflow: hidden;
            margin: 16px 0;
            background: var(--line-soft);
        }
        .memo-stat {
            background: rgba(248,250,252,0.94);
            padding: 12px;
        }
        .memo-stat span {
            display: block;
            color: var(--muted);
            font-size: 12px;
            margin-bottom: 4px;
        }
        .memo-stat strong {
            color: var(--ink);
            font-size: 20px;
            font-variant-numeric: tabular-nums;
        }
        .memo-body {
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(260px, 0.62fr);
            gap: 18px;
            align-items: start;
        }
        .memo-copy p {
            color: var(--body);
            font-size: 16px;
            line-height: 1.68;
            margin: 10px 0;
        }
        .memo-copy strong {
            color: var(--ink);
        }
        .evidence {
            border-top: 1px solid var(--line-soft);
            margin-top: 14px;
            padding-top: 12px;
        }
        .evidence h4,
        .action h4 {
            color: var(--ink);
            font-size: 15px;
            margin: 0 0 10px;
        }
        .evidence-row {
            display: grid;
            grid-template-columns: 54px 118px minmax(0, 1fr);
            gap: 9px;
            align-items: start;
            border-top: 1px solid #f3f4f6;
            padding: 8px 0;
            font-size: 13px;
            line-height: 1.45;
        }
        .evidence-row:first-of-type {
            border-top: none;
        }
        .pass {
            color: var(--green);
            font-weight: 760;
        }
        .miss {
            color: var(--amber);
            font-weight: 760;
        }
        .ev-label {
            color: var(--ink);
            font-weight: 700;
        }
        .action {
            border: 1px solid rgba(15,118,110,0.14);
            border-radius: 8px;
            background: linear-gradient(180deg, rgba(248,250,252,0.98), rgba(255,255,255,0.92));
            padding: 14px;
        }
        .action-band {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1px;
            border: 1px solid var(--line-soft);
            border-radius: 8px;
            overflow: hidden;
            background: var(--line-soft);
            margin-bottom: 12px;
        }
        .action-cell {
            background: rgba(255,255,255,0.86);
            padding: 11px;
            min-height: 82px;
        }
        .action-cell span {
            display: block;
            color: var(--muted);
            font-size: 11px;
            margin-bottom: 5px;
        }
        .action-cell strong {
            color: var(--ink);
            font-size: 18px;
            font-variant-numeric: tabular-nums;
        }
        .action p,
        .action li {
            color: var(--body);
            font-size: 14px;
            line-height: 1.55;
        }
        .action ul {
            margin: 6px 0 0 18px;
            padding: 0;
        }
        .notice {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(255,255,255,0.84);
            padding: 14px 15px;
            margin: 10px 0;
        }
        .notice h3 {
            margin: 0 0 4px;
            font-size: 16px;
        }
        .notice p {
            margin: 0;
            color: var(--body);
            line-height: 1.55;
        }
        .notice.warning {
            border-color: #fed7aa;
            background: #fffbeb;
        }
        .notice.success {
            border-color: #99f6e4;
            background: #ecfdf5;
        }
        .idea {
            border: 1px solid rgba(16,24,40,0.1);
            border-radius: 8px;
            background: rgba(255,255,255,0.84);
            padding: 15px;
            margin-bottom: 12px;
        }
        .idea h3 {
            color: var(--ink);
            font-size: 18px;
            line-height: 1.35;
            margin: 10px 0 8px;
        }
        .idea p {
            color: var(--body);
            line-height: 1.58;
            margin: 6px 0;
        }
        .quiet {
            border: 1px solid var(--line);
            border-radius: 8px;
            background: rgba(255,255,255,0.78);
            padding: 16px;
            margin-bottom: 12px;
        }
        .quiet h3 {
            font-size: 17px;
            margin: 0 0 7px;
        }
        .quiet p {
            color: var(--body);
            margin: 0;
            line-height: 1.58;
        }
        .source-row {
            display: grid;
            grid-template-columns: minmax(120px, 1fr) 48px;
            gap: 10px;
            align-items: center;
            margin: 10px 0;
        }
        .source-row span {
            display: block;
            color: var(--body);
            font-size: 13px;
            margin-bottom: 5px;
        }
        .source-bar {
            height: 8px;
            border-radius: 999px;
            background: #edf2f7;
            overflow: hidden;
        }
        .source-bar b {
            display: block;
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, var(--green), var(--blue));
        }
        .source-count {
            color: var(--muted);
            font-size: 13px;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }
        @media (max-width: 920px) {
            .control-top,
            .memo-body {
                grid-template-columns: 1fr;
            }
            .metric-grid,
            .memo-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .identity h1 {
                font-size: 44px;
            }
        }
        @media (max-width: 620px) {
            .block-container {
                padding-top: 1rem;
            }
            .hf-stage,
            .memo {
                padding: 16px;
            }
            .identity h1 {
                font-size: 36px;
            }
            .identity p {
                font-size: 16px;
            }
            .metric-grid,
            .memo-grid,
            .action-band,
            .memo-head,
            .evidence-row {
                grid-template-columns: 1fr;
            }
            .memo-score {
                text-align: left;
            }
            .section-title {
                align-items: flex-start;
                flex-direction: column;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_strip(summary: Dict, analysis_label: str, generated_at: str) -> str:
    raw_count = as_int(summary.get("raw_count"))
    candidate_count = as_int(summary.get("candidate_count"))
    saved_count = as_int(summary.get("saved_count"))
    error_count = len(summary.get("errors", []) or [])
    candidate_rate = percent(candidate_count, raw_count)
    return (
        '<div class="status-strip">'
        f'<div class="status-pill"><span><b>{candidate_rate}%</b> 候选率</span></div>'
        f'<div class="status-pill"><span><b>{saved_count}</b> 写入历史</span></div>'
        f'<div class="status-pill"><span><b>{error_count}</b> 来源错误</span></div>'
        f'<div class="status-pill"><span><b>{esc(analysis_label)}</b> 分析状态</span></div>'
        f'<div class="status-pill"><span><b>{esc(generated_at)}</b> 快照时间</span></div>'
        "</div>"
    )


def render_radar(summary: Dict, decision_summary: Dict, repeated_count: int) -> None:
    raw_count = max(as_int(summary.get("raw_count")), 1)
    candidate_count = as_int(summary.get("candidate_count"))
    build_count = as_int(decision_summary.get("build_now_count", summary.get("build_now_count")))
    monitor_count = as_int(decision_summary.get("monitor_count", summary.get("monitor_count")))
    cluster_count = as_int(decision_summary.get("total_clusters"))
    rows = [
        ("候选率", percent(candidate_count, raw_count), "green"),
        ("立即验证", percent(build_count, max(cluster_count, 1)), "amber"),
        ("继续观察", percent(monitor_count, max(cluster_count, 1)), "blue"),
        ("重复信号", min(100, repeated_count * 20), "rose"),
    ]
    body = "".join(
        f"""
        <div class="radar-row">
            <span>{esc(label)}</span>
            <div class="rail"><span class="{css}" style="width:{value}%"></span></div>
            <span>{value}%</span>
        </div>
        """
        for label, value, css in rows
    )
    st.markdown(
        f"""
        <div class="scene-panel">
            <h2>Signal Composition</h2>
            {body}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_command_stage(snapshot: Dict, analysis_label: str) -> None:
    summary = snapshot.get("summary", {})
    decision_summary = snapshot.get("decision_summary", {})
    repeated = snapshot.get("repeated_signals_7d", [])
    generated_at = snapshot.get("generated_at", "未生成")
    build_now = as_int(decision_summary.get("build_now_count", summary.get("build_now_count")))
    candidate_count = as_int(summary.get("candidate_count"))
    cluster_count = as_int(decision_summary.get("total_clusters"))

    if build_now:
        headline = f"{build_now} 个机会进入验证台"
        subline = "优先处理证据链完整、付费暗示明确、并且能在 7 天内拿到真实反馈的需求簇。"
    else:
        headline = "今天更适合观察与补证据"
        subline = "当前信号还没有形成足够强的开工证据，重点看缺口、来源质量和下一步验证动作。"

    left, right = st.columns([1.38, 0.62], gap="large")
    with left:
        st.markdown(
            f"""
            <section class="hf-stage identity">
                <div>
                    <div class="kicker">OPC PAIN INTELLIGENCE SYSTEM · PERSONAL COMMAND BOARD</div>
                    <h1>{esc(headline)}</h1>
                    <p>{esc(subline)}</p>
                </div>
                {status_strip(summary, analysis_label, generated_at)}
            </section>
            """,
            unsafe_allow_html=True,
        )
    with right:
        render_radar(summary, decision_summary, len(repeated))

    render_metric_grid(
        [
            ("候选机会", candidate_count, f"原始信号 {summary.get('raw_count', 0)}"),
            ("需求簇", cluster_count, f"重复信号 {len(repeated)}"),
            ("立即验证", build_now, "进入行动队列"),
            ("继续观察", decision_summary.get("monitor_count", summary.get("monitor_count", 0)), "等待补证据"),
        ]
    )


def render_metric_grid(metrics: Iterable[tuple]) -> None:
    tiles = "".join(
        f"""
        <div class="metric-tile">
            <span>{esc(label)}</span>
            <strong>{esc(value)}</strong>
            <em>{esc(note)}</em>
        </div>
        """
        for label, value, note in metrics
    )
    st.markdown(f'<div class="metric-grid">{tiles}</div>', unsafe_allow_html=True)


def render_quality_notices(notices: List[Dict]) -> None:
    if not notices:
        return
    for notice in notices:
        css = "success" if notice.get("level") == "success" else "warning" if notice.get("level") == "warning" else ""
        st.markdown(
            f"""
            <div class="notice {css}">
                <h3>{esc(notice.get("title", ""))}</h3>
                <p>{esc(notice.get("body", ""))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def executive_brief(summary: Dict, decision_summary: Dict, source_stats: Dict) -> None:
    raw_count = as_int(summary.get("raw_count"))
    candidate_count = as_int(summary.get("candidate_count"))
    total_clusters = as_int(decision_summary.get("total_clusters"))
    build_now = as_int(decision_summary.get("build_now_count"))
    monitor = as_int(decision_summary.get("monitor_count"))
    source_line = ""
    platforms = source_stats.get("platforms", []) if source_stats else []
    if platforms:
        first = platforms[0]
        source_line = f"主要候选来源为 {first.get('name')}，占 {first.get('percent', 0)}%。"
    st.markdown(
        f"""
        <div class="brief">
            <h2>今日判断</h2>
            <p>扫描 {esc(raw_count)} 条原始信号，筛出 {esc(candidate_count)} 条候选，合并为 {esc(total_clusters)} 个需求簇。</p>
            <p>{esc(build_now)} 个进入立即验证，{esc(monitor)} 个继续观察。{esc(source_line)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="section-title">
            <h2>{esc(title)}</h2>
            <span>{esc(note)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def evidence_html(chain: Dict) -> str:
    if not chain:
        return (
            '<div class="evidence">'
            "<h4>证据链：未评估</h4>"
            '<div class="evidence-row"><div class="miss">缺口</div><div class="ev-label">字段</div><div>当前快照缺少 evidence_chain。</div></div>'
            "</div>"
        )
    summary = evidence_chain_summary({"evidence_chain": chain})
    rows = []
    for item in chain.get("items", []) or []:
        passed = bool(item.get("passed"))
        rows.append(
            '<div class="evidence-row">'
            f'<div class="{"pass" if passed else "miss"}">{"通过" if passed else "缺口"}</div>'
            f'<div class="ev-label">{esc(item.get("label", ""))}</div>'
            f'<div>{esc(item.get("detail", ""))}</div>'
            "</div>"
        )
    return (
        '<div class="evidence">'
        f'<h4>证据链：{esc(summary.get("passed_count", 0))}/{esc(summary.get("total_count", 0))} · {esc(summary.get("label", ""))}</h4>'
        f'{"".join(rows)}'
        "</div>"
    )


def action_html(cluster: Dict) -> str:
    action = build_action_view(cluster)
    funnel = action.get("funnel", {})
    blockers = [item for item in funnel.get("blockers", []) if item]
    blocker_html = (
        "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in blockers) + "</ul>"
        if blockers
        else "<p>暂无明确阻塞项。</p>"
    )
    return f"""
    <aside class="action">
        <h4>验证漏斗</h4>
        <div class="action-band">
            <div class="action-cell"><span>Verdict</span><strong>{esc(funnel.get("verdict", "未评估"))}</strong></div>
            <div class="action-cell"><span>Score</span><strong>{esc(funnel.get("total_score", 0))}</strong></div>
            <div class="action-cell"><span>Risk</span><strong>{esc(funnel.get("risk_penalty", 0))}</strong></div>
        </div>
        <p><strong>下一步：</strong>{esc(action.get("next_step", ""))}</p>
        <p><strong>竞争/分发：</strong>Competitor {esc(funnel.get("competitor_score", 0))} · Distribution {esc(funnel.get("distribution_score", 0))}</p>
        <p><strong>阻塞：</strong></p>
        {blocker_html}
    </aside>
    """


def render_cluster(cluster: Dict) -> None:
    decision = cluster.get("decision_verdict", "Monitor")
    funnel_verdict = cluster.get("funnel_verdict") or (cluster.get("funnel_score") or {}).get("verdict", "")
    anti_signals = cluster.get("anti_signals") or cluster.get("codex_anti_signals") or []
    anti_html = ""
    if anti_signals:
        anti_html = "<p><strong>反信号：</strong>" + esc("；".join(str(item) for item in anti_signals if item)) + "</p>"

    opportunity_hypothesis = cluster.get("opportunity_hypothesis") or cluster.get("codex_opportunity_thesis") or ""
    evidence = cluster.get("evidence") or cluster.get("evidence_summary") or ""
    paid_signal = cluster.get("paid_signal") or "尚未形成明确付费信号。"
    not_build_now = cluster.get("not_build_now_reason") or cluster.get("decision_reason") or ""
    validation = cluster.get("seven_day_validation") or cluster.get("recommended_action") or cluster.get("funnel_next_step") or ""

    st.markdown(
        f"""
        <article class="memo">
            <div class="memo-head">
                <div>
                    <div class="tag-row">
                        <span class="tag {verdict_class(decision)}">{esc(verdict_label(decision))}</span>
                        <span class="tag {verdict_class(funnel_verdict)}">Funnel · {esc(verdict_label(funnel_verdict))}</span>
                        <span class="tag">{esc(cluster.get("category", "其他/待判定"))}</span>
                    </div>
                    <h3>{esc(cluster.get("title", "待验证机会"))}</h3>
                </div>
                <div class="memo-score">{esc(cluster.get("decision_score", 0))}<span>Decision Score</span></div>
            </div>
            <div class="memo-grid">
                <div class="memo-stat"><span>7天重复</span><strong>{esc(cluster.get("count_7d", 0))}</strong></div>
                <div class="memo-stat"><span>来源数</span><strong>{esc(cluster.get("source_count", 0))}</strong></div>
                <div class="memo-stat"><span>最高原始分</span><strong>{esc(cluster.get("top_score", 0))}</strong></div>
                <div class="memo-stat"><span>平均分</span><strong>{esc(cluster.get("avg_score", 0))}</strong></div>
            </div>
            <div class="memo-body">
                <section class="memo-copy">
                    <p><strong>机会假设：</strong>{esc(opportunity_hypothesis)}</p>
                    <p><strong>证据：</strong>{esc(evidence)}</p>
                    <p><strong>付费信号：</strong>{esc(paid_signal)}</p>
                    <p><strong>暂缓理由：</strong>{esc(not_build_now)}</p>
                    {anti_html}
                    <p><strong>7天动作：</strong>{esc(validation)}</p>
                    {evidence_html(cluster.get("evidence_chain", {}))}
                </section>
                {action_html(cluster)}
            </div>
        </article>
        """,
        unsafe_allow_html=True,
    )
    samples = cluster.get("sample_ideas", []) or []
    if samples:
        with st.expander(f"样本来源 · {cluster.get('title', '待验证机会')}", expanded=False):
            for sample in samples:
                title = sample.get("title", "Untitled")
                source = sample.get("source", "")
                score = sample.get("total_score", 0)
                if sample.get("source_url"):
                    st.markdown(f"- [{esc(title)}]({sample.get('source_url')}) · {esc(source)} · Score {esc(score)}")
                else:
                    st.markdown(f"- {esc(title)} · {esc(source)} · Score {esc(score)}")


def render_idea(idea: Dict) -> None:
    verdict = idea.get("verdict", "Monitor")
    st.markdown(
        f"""
        <div class="idea">
            <div class="tag-row">
                <span class="tag">{esc(idea.get("category", "其他/待判定"))}</span>
                <span class="tag {verdict_class(verdict)}">{esc(verdict_label(verdict))}</span>
                <span class="tag">Score {esc(idea.get("total_score", 0))}</span>
                <span class="tag">7天重复 {esc(idea.get("repeat_7d", 1))}</span>
            </div>
            <h3>{esc(idea.get("mvp_concept", ""))}</h3>
            <p>{esc(idea.get("pain_summary", ""))}</p>
            <p><strong>下一步：</strong>{esc(idea.get("validation_step", ""))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if idea.get("source_url"):
        st.markdown(f"[{esc(idea.get('source', '来源'))} · {esc(idea.get('title', 'Untitled'))}]({idea.get('source_url')})")


def render_source_stats(source_stats: Dict) -> None:
    total = as_int(source_stats.get("total_candidates")) if source_stats else 0
    if not total:
        st.info("暂无来源统计。")
        return
    for platform in source_stats.get("platforms", []):
        value = as_int(platform.get("percent"))
        st.markdown(
            f"""
            <div class="source-row">
                <div>
                    <span>{esc(platform.get("name", ""))}</span>
                    <div class="source-bar"><b style="width:{value}%"></b></div>
                </div>
                <div class="source-count">{esc(platform.get("count", 0))} · {esc(value)}%</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    top_sources = source_stats.get("top_sources", [])
    if top_sources:
        rows = [
            {"来源": item.get("source", ""), "候选数": item.get("count", 0), "占比": f"{item.get('percent', 0)}%"}
            for item in top_sources
        ]
        st.dataframe(rows, width="stretch", hide_index=True)


def render_counts_table(title: str, counts: Dict, key_name: str) -> None:
    st.subheader(title)
    if not counts:
        st.info(f"暂无{title}。")
        return
    rows = [
        {key_name: key, "数量": value}
        for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]
    st.dataframe(rows, width="stretch", hide_index=True)


def render_source_health(source_health: Dict) -> None:
    if not source_health:
        return
    st.markdown(
        f"""
        <div class="quiet">
            <h3>数据源健康 · {esc(source_health.get("status", "unknown"))}</h3>
            <p>原始 {esc(source_health.get("raw_count", 0))} · 去重 {esc(source_health.get("unique_count", 0))} · 候选 {esc(source_health.get("candidate_count", 0))} · 错误 {esc(source_health.get("error_count", 0))}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    rows = source_health.get("sources", [])
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)


def render_repeated_signals(repeated: List[Dict]) -> None:
    if not repeated:
        st.info("最近 7 天还没有出现 2 次以上的重复信号。")
        return
    for signal in repeated:
        st.markdown(
            f"""
            <div class="quiet">
                <h3>{esc(signal.get("category", "其他/待判定"))} · {esc(signal.get("count", 0))} 次 · Top {esc(signal.get("top_score", 0))}</h3>
                <p>{esc(signal.get("sample_concept", ""))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if signal.get("sample_url"):
            st.markdown(f"[查看样本]({signal.get('sample_url')})")


def render_source_metrics(source_metrics: List[Dict]) -> None:
    rows = build_source_metric_rows(source_metrics)
    if not rows:
        st.info("暂无 source metrics。")
        return
    st.dataframe(rows, width="stretch", hide_index=True)


def render_artifacts(snapshot: Dict) -> None:
    rows = build_artifact_summary_rows(
        snapshot.get("container_summary", {}),
        snapshot.get("pain_signal_summary", {}),
    )
    st.dataframe(rows, width="stretch", hide_index=True)


def render_markdown_report(report: str, generated_at: str) -> None:
    if not report:
        return
    st.download_button(
        "下载 Markdown 日报",
        data=report,
        file_name=f"demand-report-{generated_at.split(' ')[0]}.md",
        mime="text/markdown",
        width="stretch",
    )
    with st.expander("日报预览", expanded=False):
        st.code(report, language="markdown")


def render_empty_state() -> None:
    st.markdown(
        """
        <section class="hf-stage identity">
            <div>
                <div class="kicker">OPC PAIN INTELLIGENCE SYSTEM</div>
                <h1>等待第一份快照</h1>
                <p>本地扫描完成后，页面会展示机会决策、证据链和验证动作。</p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.info("缺少 `data/dashboard_snapshot.json`。请在本地运行：`python3 local_runner.py`。")


render_styles()
snapshot = load_dashboard_snapshot()

if snapshot is None:
    render_empty_state()
    st.stop()

summary = snapshot.get("summary", {})
decision_summary = snapshot.get("decision_summary", {})
source_health = snapshot.get("source_health", {})
source_stats = snapshot.get("source_stats", {})
clusters = snapshot.get("opportunity_clusters", [])
top_ideas = snapshot.get("top_ideas", [])
repeated = snapshot.get("repeated_signals_7d", [])
generated_at = snapshot.get("generated_at", "未生成")
analysis_metadata = snapshot.get("analysis_metadata", {})
analysis_label = (
    f"{analysis_metadata.get('analysis_provider', 'heuristic')} / "
    f"{analysis_metadata.get('analysis_status', 'local')}"
)

render_command_stage(snapshot, analysis_label)
render_quality_notices(build_quality_notices(snapshot))

tab_command, tab_signal, tab_audit = st.tabs(["指挥台", "信号板", "审计"])

with tab_command:
    executive_brief(summary, decision_summary, source_stats)
    if summary.get("errors"):
        with st.expander("本地扫描错误", expanded=False):
            for error in summary.get("errors", []):
                st.warning(error)

    if clusters:
        section_title("机会决策队列", "按 funnel score、证据链完整度和下一步动作阅读")
        sorted_clusters = sorted(
            clusters,
            key=lambda item: (
                as_float((item.get("funnel_score") or {}).get("total_score")),
                as_float(item.get("decision_score")),
            ),
            reverse=True,
        )
        for cluster in sorted_clusters:
            render_cluster(cluster)
    else:
        section_title("Top 候选机会", "当前快照尚未形成需求簇")
        for idea in top_ideas:
            render_idea(idea)

with tab_signal:
    left, right = st.columns([1.08, 0.92], gap="large")
    with left:
        section_title("候选信号", "原始痛点经过过滤后的候选列表")
        if top_ideas:
            for idea in top_ideas:
                render_idea(idea)
        else:
            st.info("当前快照没有候选机会。")
    with right:
        section_title("来源质量", "来源分布、候选率和投入建议")
        render_source_stats(source_stats)
        render_source_metrics(snapshot.get("source_metrics", []))
        section_title("重复信号", "7 天内反复出现的主题")
        render_repeated_signals(repeated)

with tab_audit:
    left, right = st.columns([1, 1], gap="large")
    with left:
        section_title("数据源健康", "采集、缓存和降级状态")
        render_source_health(source_health)
        render_counts_table("分类分布", snapshot.get("category_counts", {}), "分类")
        render_counts_table("人工标注", snapshot.get("label_counts", {}), "标注")
    with right:
        section_title("发现产物", "后续阶段的容器、评论和痛点信号摘要")
        render_artifacts(snapshot)
        section_title("日报", "本地生成的 Markdown 报告")
        render_markdown_report(snapshot.get("markdown_report", ""), generated_at)
