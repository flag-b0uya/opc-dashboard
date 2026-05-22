#!/usr/bin/env python3
"""Read-only Streamlit host for a custom OPC dashboard app shell."""

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


st.set_page_config(page_title="OPC Pain Intelligence", layout="wide", initial_sidebar_state="collapsed")


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
        return "build"
    if verdict == "Monitor":
        return "monitor"
    if verdict == "Discard":
        return "discard"
    return "neutral"


def list_items(items: Iterable[Any]) -> str:
    values = [str(item) for item in items if item]
    if not values:
        return '<p class="muted">暂无。</p>'
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in values) + "</ul>"


def metric_tile(label: str, value: Any, note: str = "") -> str:
    return f"""
    <div class="metric">
      <span>{esc(label)}</span>
      <strong>{esc(value)}</strong>
      <em>{esc(note)}</em>
    </div>
    """


def rail(label: str, value: int, css_class: str = "") -> str:
    return f"""
    <div class="rail-row">
      <span>{esc(label)}</span>
      <div class="rail"><b class="{esc(css_class)}" style="width:{value}%"></b></div>
      <strong>{value}%</strong>
    </div>
    """


def evidence_block(chain: Dict) -> str:
    if not chain:
        return """
        <section class="evidence">
          <h4>证据链</h4>
          <div class="check-row miss"><span>缺口</span><b>数据</b><p>当前快照缺少 evidence_chain 字段。</p></div>
        </section>
        """
    summary = evidence_chain_summary({"evidence_chain": chain})
    rows = []
    for item in chain.get("items", []) or []:
        passed = bool(item.get("passed"))
        rows.append(
            f"""
            <div class="check-row {'pass' if passed else 'miss'}">
              <span>{'通过' if passed else '缺口'}</span>
              <b>{esc(item.get('label', ''))}</b>
              <p>{esc(item.get('detail', ''))}</p>
            </div>
            """
        )
    return f"""
    <section class="evidence">
      <h4>证据链 · {esc(summary.get('passed_count', 0))}/{esc(summary.get('total_count', 0))} · {esc(summary.get('label', ''))}</h4>
      {''.join(rows)}
    </section>
    """


def action_panel(cluster: Dict) -> str:
    action = build_action_view(cluster)
    funnel = action.get("funnel", {})
    blockers = funnel.get("blockers", []) or []
    return f"""
    <aside class="action-panel">
      <div class="panel-label">Validation Funnel</div>
      <div class="funnel-score">
        <strong>{esc(funnel.get('total_score', 0))}</strong>
        <span>{esc(verdict_label(funnel.get('verdict', '')))}</span>
      </div>
      <div class="split-metrics">
        <div><span>Competitor</span><b>{esc(funnel.get('competitor_score', 0))}</b></div>
        <div><span>Distribution</span><b>{esc(funnel.get('distribution_score', 0))}</b></div>
        <div><span>Risk</span><b>{esc(funnel.get('risk_penalty', 0))}</b></div>
      </div>
      <p><b>下一步</b>{esc(action.get('next_step', ''))}</p>
      <div class="blockers"><b>阻塞项</b>{list_items(blockers)}</div>
    </aside>
    """


def cluster_memo(cluster: Dict, index: int) -> str:
    decision = cluster.get("decision_verdict", "Monitor")
    funnel_verdict = cluster.get("funnel_verdict") or (cluster.get("funnel_score") or {}).get("verdict", "")
    anti_signals = cluster.get("anti_signals") or cluster.get("codex_anti_signals") or []
    opportunity = cluster.get("opportunity_hypothesis") or cluster.get("codex_opportunity_thesis") or ""
    evidence = cluster.get("evidence") or cluster.get("evidence_summary") or ""
    paid_signal = cluster.get("paid_signal") or "尚未形成明确付费信号。"
    not_build = cluster.get("not_build_now_reason") or cluster.get("decision_reason") or ""
    validation = cluster.get("seven_day_validation") or cluster.get("recommended_action") or cluster.get("funnel_next_step") or ""
    samples = cluster.get("sample_ideas", []) or []
    sample_rows = "".join(
        f"""
        <a class="sample" href="{esc(sample.get('source_url', '#'))}" target="_blank">
          <span>{esc(sample.get('source', ''))}</span>
          <b>{esc(sample.get('title', 'Untitled'))}</b>
          <em>Score {esc(sample.get('total_score', 0))}</em>
        </a>
        """
        for sample in samples[:4]
    )

    return f"""
    <article class="memo" style="--delay:{index * 90}ms">
      <header class="memo-head">
        <div>
          <div class="chips">
            <span class="chip {verdict_class(decision)}">{esc(verdict_label(decision))}</span>
            <span class="chip {verdict_class(funnel_verdict)}">Funnel · {esc(verdict_label(funnel_verdict))}</span>
            <span class="chip neutral">{esc(cluster.get('category', '其他/待判定'))}</span>
          </div>
          <h3>{esc(cluster.get('title', '待验证机会'))}</h3>
        </div>
        <div class="score"><strong>{esc(cluster.get('decision_score', 0))}</strong><span>Decision</span></div>
      </header>
      <div class="memo-stats">
        <div><span>7天重复</span><b>{esc(cluster.get('count_7d', 0))}</b></div>
        <div><span>来源数</span><b>{esc(cluster.get('source_count', 0))}</b></div>
        <div><span>最高原始分</span><b>{esc(cluster.get('top_score', 0))}</b></div>
        <div><span>平均分</span><b>{esc(cluster.get('avg_score', 0))}</b></div>
      </div>
      <div class="memo-layout">
        <section class="memo-copy">
          <p><b>机会假设</b>{esc(opportunity)}</p>
          <p><b>证据</b>{esc(evidence)}</p>
          <p><b>付费信号</b>{esc(paid_signal)}</p>
          <p><b>暂缓理由</b>{esc(not_build)}</p>
          <p><b>7天动作</b>{esc(validation)}</p>
          <div class="anti"><b>反信号</b>{list_items(anti_signals)}</div>
          {evidence_block(cluster.get('evidence_chain', {}))}
        </section>
        {action_panel(cluster)}
      </div>
      <footer class="samples">
        <div class="panel-label">Representative Samples</div>
        {sample_rows or '<p class="muted">暂无代表样本。</p>'}
      </footer>
    </article>
    """


def idea_row(idea: Dict) -> str:
    url = idea.get("source_url") or "#"
    return f"""
    <a class="idea-row" href="{esc(url)}" target="_blank">
      <div class="chips">
        <span class="chip neutral">{esc(idea.get('category', '其他/待判定'))}</span>
        <span class="chip {verdict_class(idea.get('verdict', ''))}">{esc(verdict_label(idea.get('verdict', '')))}</span>
        <span class="chip neutral">Score {esc(idea.get('total_score', 0))}</span>
      </div>
      <h3>{esc(idea.get('mvp_concept', ''))}</h3>
      <p>{esc(idea.get('pain_summary', ''))}</p>
      <small>{esc(idea.get('source', ''))} · {esc(idea.get('title', ''))}</small>
    </a>
    """


def table_html(rows: List[Dict], columns: List[str]) -> str:
    if not rows:
        return '<p class="muted">暂无数据。</p>'
    head = "".join(f"<th>{esc(col)}</th>" for col in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(row.get(col, ''))}</td>" for col in columns) + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def source_platforms(source_stats: Dict) -> str:
    rows = []
    for platform in source_stats.get("platforms", []) or []:
        value = as_int(platform.get("percent"))
        rows.append(
            f"""
            <div class="source-row">
              <div><span>{esc(platform.get('name', ''))}</span><div class="source-bar"><b style="width:{value}%"></b></div></div>
              <strong>{esc(platform.get('count', 0))} · {value}%</strong>
            </div>
            """
        )
    return "".join(rows) or '<p class="muted">暂无来源统计。</p>'


def repeated_html(repeated: List[Dict]) -> str:
    if not repeated:
        return '<p class="muted">最近 7 天还没有出现 2 次以上的重复信号。</p>'
    return "".join(
        f"""
        <div class="repeat-row">
          <span>{esc(item.get('category', '其他/待判定'))}</span>
          <b>{esc(item.get('count', 0))} 次 · Top {esc(item.get('top_score', 0))}</b>
          <p>{esc(item.get('sample_concept', ''))}</p>
        </div>
        """
        for item in repeated
    )


def counts_table(counts: Dict, key_name: str) -> str:
    rows = [{key_name: key, "数量": value} for key, value in sorted(counts.items(), key=lambda item: item[1], reverse=True)]
    return table_html(rows, [key_name, "数量"])


def source_health_html(source_health: Dict) -> str:
    if not source_health:
        return '<p class="muted">暂无数据源健康信息。</p>'
    source_rows = source_health.get("sources", []) or []
    rows = [
        {
            "来源": item.get("source", ""),
            "状态": item.get("status", ""),
            "数量": item.get("count", 0),
            "缓存": "是" if item.get("used_cache") else "否",
            "错误": "; ".join(item.get("errors", []) or []),
        }
        for item in source_rows
    ]
    return f"""
    <div class="health-summary">
      <div><span>Status</span><b>{esc(source_health.get('status', 'unknown'))}</b></div>
      <div><span>Raw</span><b>{esc(source_health.get('raw_count', 0))}</b></div>
      <div><span>Unique</span><b>{esc(source_health.get('unique_count', 0))}</b></div>
      <div><span>Errors</span><b>{esc(source_health.get('error_count', 0))}</b></div>
    </div>
    {table_html(rows, ['来源', '状态', '数量', '缓存', '错误'])}
    """


def notice_html(notices: List[Dict]) -> str:
    return "".join(
        f"""
        <div class="notice {esc(notice.get('level', 'info'))}">
          <b>{esc(notice.get('title', ''))}</b>
          <p>{esc(notice.get('body', ''))}</p>
        </div>
        """
        for notice in notices
    )


def markdown_report_html(report: str) -> str:
    if not report:
        return '<p class="muted">暂无日报。</p>'
    return f"<pre>{esc(report[:6000])}</pre>"


def build_dashboard_html(snapshot: Dict) -> str:
    summary = snapshot.get("summary", {})
    decision = snapshot.get("decision_summary", {})
    source_stats = snapshot.get("source_stats", {})
    source_health = snapshot.get("source_health", {})
    clusters = snapshot.get("opportunity_clusters", [])
    ideas = snapshot.get("top_ideas", [])
    repeated = snapshot.get("repeated_signals_7d", [])
    generated_at = snapshot.get("generated_at", "未生成")
    analysis = snapshot.get("analysis_metadata", {})
    analysis_label = f"{analysis.get('analysis_provider', 'heuristic')} / {analysis.get('analysis_status', 'local')}"

    raw_count = as_int(summary.get("raw_count"))
    candidate_count = as_int(summary.get("candidate_count"))
    cluster_count = as_int(decision.get("total_clusters", len(clusters)))
    build_now = as_int(decision.get("build_now_count", summary.get("build_now_count")))
    monitor = as_int(decision.get("monitor_count", summary.get("monitor_count")))
    error_count = len(summary.get("errors", []) or [])
    candidate_rate = percent(candidate_count, raw_count)

    sorted_clusters = sorted(
        clusters,
        key=lambda item: (
            as_float((item.get("funnel_score") or {}).get("total_score")),
            as_float(item.get("decision_score")),
        ),
        reverse=True,
    )
    cluster_markup = "".join(cluster_memo(cluster, index) for index, cluster in enumerate(sorted_clusters))
    if not cluster_markup:
        cluster_markup = "".join(idea_row(idea) for idea in ideas) or '<p class="muted">当前快照没有候选机会。</p>'

    source_metrics = build_source_metric_rows(snapshot.get("source_metrics", []))
    artifact_rows = build_artifact_summary_rows(snapshot.get("container_summary", {}), snapshot.get("pain_signal_summary", {}))
    top_source = ""
    if source_stats.get("platforms"):
        first = source_stats["platforms"][0]
        top_source = f"{first.get('name')} · {first.get('percent', 0)}%"

    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <style>
        :root {{
          --ink: #101828;
          --body: #475467;
          --muted: #667085;
          --line: #dfe4ea;
          --soft-line: #edf1f5;
          --surface: #ffffff;
          --soft: #f8fafc;
          --canvas: #f3f7f8;
          --green: #0f766e;
          --blue: #2563eb;
          --amber: #b45309;
          --red: #b42318;
          --rose: #be123c;
          --shadow: 0 18px 46px rgba(16, 24, 40, 0.08);
          --soft-shadow: 0 10px 28px rgba(16, 24, 40, 0.055);
        }}
        * {{ box-sizing: border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{
          margin: 0;
          min-height: 100vh;
          color: var(--body);
          font-family: "Source Sans 3", "Noto Sans SC", "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif;
          background:
            linear-gradient(90deg, rgba(16,24,40,0.035) 1px, transparent 1px),
            linear-gradient(180deg, rgba(15,118,110,0.04) 1px, transparent 1px),
            linear-gradient(180deg, #fbfcfd 0%, var(--canvas) 52%, #ffffff 100%);
          background-size: 48px 48px, 48px 48px, auto;
        }}
        a {{ color: inherit; text-decoration: none; }}
        .app {{
          width: min(1440px, 100%);
          margin: 0 auto;
          padding: 18px;
          display: grid;
          grid-template-columns: 252px minmax(0, 1fr);
          gap: 16px;
        }}
        .sidebar {{
          position: sticky;
          top: 18px;
          align-self: start;
          min-height: calc(100vh - 36px);
          border: 1px solid rgba(16,24,40,0.11);
          border-radius: 8px;
          background: rgba(255,255,255,0.84);
          box-shadow: var(--soft-shadow);
          overflow: hidden;
        }}
        .brand {{
          padding: 18px;
          border-bottom: 1px solid var(--soft-line);
          background:
            linear-gradient(135deg, rgba(15,118,110,0.08), rgba(37,99,235,0.04)),
            rgba(255,255,255,0.86);
        }}
        .brand span {{
          display: inline-flex;
          align-items: center;
          height: 30px;
          padding: 0 9px;
          border: 1px solid rgba(15,118,110,0.2);
          border-radius: 8px;
          color: var(--green);
          font-size: 12px;
          font-weight: 760;
        }}
        .brand h1 {{
          margin: 12px 0 5px;
          color: var(--ink);
          font-size: 25px;
          line-height: 1.05;
          font-weight: 860;
          letter-spacing: 0;
        }}
        .brand p {{
          margin: 0;
          color: var(--muted);
          font-size: 13px;
          line-height: 1.55;
        }}
        .nav {{
          display: grid;
          gap: 6px;
          padding: 14px;
          border-bottom: 1px solid var(--soft-line);
        }}
        .nav button {{
          width: 100%;
          min-height: 44px;
          border: 1px solid transparent;
          border-radius: 8px;
          background: transparent;
          color: var(--body);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 12px;
          font: inherit;
          font-size: 14px;
          font-weight: 680;
          text-align: left;
        }}
        .nav button.active {{
          border-color: rgba(15,118,110,0.18);
          background: #ecfdf5;
          color: var(--green);
        }}
        .sidebar-data {{
          padding: 14px;
          display: grid;
          gap: 10px;
        }}
        .side-stat {{
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 8px;
          border-bottom: 1px solid var(--soft-line);
          padding-bottom: 10px;
        }}
        .side-stat span {{
          color: var(--muted);
          font-size: 12px;
        }}
        .side-stat b {{
          color: var(--ink);
          font-variant-numeric: tabular-nums;
        }}
        .main {{
          min-width: 0;
          display: grid;
          gap: 16px;
        }}
        .hero {{
          position: relative;
          overflow: hidden;
          border: 1px solid rgba(16,24,40,0.11);
          border-radius: 8px;
          background:
            linear-gradient(135deg, rgba(255,255,255,0.98), rgba(248,250,252,0.92)),
            repeating-linear-gradient(135deg, rgba(15,118,110,0.04) 0 1px, transparent 1px 18px);
          box-shadow: var(--shadow);
          padding: 24px;
          animation: enter 520ms cubic-bezier(.16,1,.3,1) both 100ms;
        }}
        .hero:before {{
          content: "";
          position: absolute;
          left: 24px;
          right: 24px;
          bottom: 0;
          height: 3px;
          background: linear-gradient(90deg, var(--green), var(--blue), var(--amber), var(--rose));
        }}
        .hero-grid {{
          display: grid;
          grid-template-columns: minmax(0, 1fr) 360px;
          gap: 24px;
          align-items: stretch;
        }}
        .kicker {{
          color: var(--green);
          font-size: 12px;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0;
          margin-bottom: 14px;
        }}
        .hero h2 {{
          margin: 0;
          max-width: 820px;
          color: var(--ink);
          font-size: clamp(42px, 5vw, 72px);
          line-height: 0.98;
          font-weight: 900;
          letter-spacing: 0;
        }}
        .hero p {{
          max-width: 760px;
          margin: 16px 0 0;
          color: var(--body);
          font-size: 18px;
          line-height: 1.6;
        }}
        .status-grid {{
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 1px;
          border: 1px solid var(--soft-line);
          border-radius: 8px;
          overflow: hidden;
          background: var(--soft-line);
        }}
        .status-grid div {{
          min-height: 82px;
          background: rgba(255,255,255,0.78);
          padding: 12px;
        }}
        .status-grid span,
        .metric span,
        .memo-stats span,
        .split-metrics span,
        .health-summary span {{
          display: block;
          color: var(--muted);
          font-size: 12px;
          margin-bottom: 5px;
        }}
        .status-grid b,
        .metric strong,
        .memo-stats b,
        .split-metrics b,
        .health-summary b {{
          color: var(--ink);
          font-variant-numeric: tabular-nums;
        }}
        .metrics {{
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          animation: enter 500ms cubic-bezier(.16,1,.3,1) both 220ms;
        }}
        .metric {{
          border: 1px solid rgba(16,24,40,0.1);
          border-radius: 8px;
          background: rgba(255,255,255,0.84);
          box-shadow: var(--soft-shadow);
          padding: 15px;
          min-height: 104px;
        }}
        .metric strong {{
          display: block;
          font-size: 33px;
          line-height: 1;
          font-weight: 860;
        }}
        .metric em {{
          display: block;
          color: var(--muted);
          font-size: 12px;
          font-style: normal;
          margin-top: 8px;
        }}
        .view {{ display: none; animation: enter 440ms cubic-bezier(.16,1,.3,1) both; }}
        .view.active {{ display: block; }}
        .section-head {{
          display: flex;
          align-items: end;
          justify-content: space-between;
          gap: 16px;
          border-bottom: 1px solid var(--line);
          margin: 18px 0 16px;
          padding-bottom: 11px;
        }}
        .section-head h2 {{
          margin: 0;
          color: var(--ink);
          font-size: 22px;
        }}
        .section-head p {{
          margin: 0;
          color: var(--muted);
          font-size: 13px;
        }}
        .brief {{
          border: 1px solid rgba(16,24,40,0.1);
          border-radius: 8px;
          background: rgba(255,255,255,0.82);
          box-shadow: var(--soft-shadow);
          padding: 18px;
          margin-bottom: 14px;
        }}
        .brief h3 {{
          margin: 0 0 8px;
          color: var(--ink);
          font-size: 22px;
        }}
        .brief p {{
          margin: 6px 0;
          color: var(--body);
          font-size: 16px;
          line-height: 1.62;
        }}
        .notice {{
          border: 1px solid var(--line);
          border-radius: 8px;
          background: rgba(255,255,255,0.82);
          padding: 13px 14px;
          margin-bottom: 10px;
        }}
        .notice.warning {{ border-color: #fed7aa; background: #fffbeb; }}
        .notice.success {{ border-color: #99f6e4; background: #ecfdf5; }}
        .notice b {{
          display: block;
          color: var(--ink);
          margin-bottom: 4px;
        }}
        .notice p {{ margin: 0; line-height: 1.55; }}
        .memo {{
          border: 1px solid rgba(16,24,40,0.11);
          border-radius: 8px;
          background:
            linear-gradient(180deg, rgba(255,255,255,0.98), rgba(250,252,253,0.96));
          box-shadow: var(--shadow);
          padding: 22px;
          margin-bottom: 18px;
          animation: enter 480ms cubic-bezier(.16,1,.3,1) both;
          animation-delay: var(--delay);
        }}
        .memo-head {{
          display: grid;
          grid-template-columns: minmax(0, 1fr) 94px;
          gap: 16px;
          align-items: start;
        }}
        .memo h3 {{
          margin: 10px 0 0;
          color: var(--ink);
          font-size: 25px;
          line-height: 1.28;
        }}
        .chips {{
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
        }}
        .chip {{
          display: inline-flex;
          align-items: center;
          min-height: 28px;
          border: 1px solid #d0d5dd;
          border-radius: 8px;
          background: rgba(255,255,255,0.9);
          color: #344054;
          padding: 4px 9px;
          font-size: 12px;
          font-weight: 700;
        }}
        .chip.build {{ border-color: #99f6e4; background: #ecfdf5; color: var(--green); }}
        .chip.monitor {{ border-color: #fed7aa; background: #fff7ed; color: #c2410c; }}
        .chip.discard {{ border-color: #fecaca; background: #fef2f2; color: var(--red); }}
        .score {{
          text-align: right;
        }}
        .score strong {{
          display: block;
          color: var(--ink);
          font-size: 38px;
          line-height: 1;
          font-weight: 900;
          font-variant-numeric: tabular-nums;
        }}
        .score span {{
          color: var(--muted);
          font-size: 12px;
          font-weight: 700;
        }}
        .memo-stats,
        .split-metrics,
        .health-summary {{
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 1px;
          border: 1px solid var(--soft-line);
          border-radius: 8px;
          overflow: hidden;
          background: var(--soft-line);
          margin: 16px 0;
        }}
        .memo-stats div,
        .split-metrics div,
        .health-summary div {{
          background: var(--soft);
          padding: 11px;
        }}
        .memo-layout {{
          display: grid;
          grid-template-columns: minmax(0, 1fr) 320px;
          gap: 18px;
          align-items: start;
        }}
        .memo-copy p,
        .anti,
        .blockers {{
          margin: 10px 0;
          color: var(--body);
          font-size: 16px;
          line-height: 1.65;
        }}
        .memo-copy p b,
        .anti > b,
        .blockers > b,
        .action-panel p b {{
          display: block;
          color: var(--ink);
          margin-bottom: 3px;
        }}
        ul {{ margin: 6px 0 0 18px; padding: 0; }}
        li {{ margin: 4px 0; line-height: 1.5; }}
        .evidence {{
          margin-top: 16px;
          border-top: 1px solid var(--soft-line);
          padding-top: 13px;
        }}
        .evidence h4,
        .panel-label {{
          margin: 0 0 10px;
          color: var(--ink);
          font-size: 13px;
          text-transform: uppercase;
          font-weight: 820;
          letter-spacing: 0;
        }}
        .check-row {{
          display: grid;
          grid-template-columns: 52px 118px minmax(0, 1fr);
          gap: 9px;
          border-top: 1px solid #f3f4f6;
          padding: 8px 0;
          font-size: 13px;
          line-height: 1.45;
        }}
        .check-row:first-of-type {{ border-top: none; }}
        .check-row span {{ font-weight: 820; }}
        .check-row.pass span {{ color: var(--green); }}
        .check-row.miss span {{ color: var(--amber); }}
        .check-row b {{ color: var(--ink); }}
        .check-row p {{ margin: 0; }}
        .action-panel {{
          border: 1px solid rgba(15,118,110,0.14);
          border-radius: 8px;
          background: linear-gradient(180deg, rgba(248,250,252,0.98), rgba(255,255,255,0.95));
          padding: 15px;
        }}
        .funnel-score {{
          display: flex;
          align-items: end;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 12px;
        }}
        .funnel-score strong {{
          color: var(--ink);
          font-size: 44px;
          line-height: 1;
          font-weight: 900;
        }}
        .funnel-score span {{
          color: var(--green);
          font-weight: 800;
          text-align: right;
        }}
        .split-metrics {{
          grid-template-columns: repeat(3, minmax(0, 1fr));
          margin: 10px 0;
        }}
        .action-panel p,
        .action-panel li {{
          font-size: 14px;
          line-height: 1.55;
        }}
        .samples {{
          margin-top: 16px;
          border-top: 1px solid var(--soft-line);
          padding-top: 13px;
        }}
        .sample,
        .idea-row,
        .repeat-row {{
          display: block;
          border: 1px solid var(--soft-line);
          border-radius: 8px;
          background: rgba(248,250,252,0.76);
          padding: 12px;
          margin-top: 8px;
        }}
        .sample span,
        .sample em,
        .idea-row small,
        .repeat-row span {{
          display: block;
          color: var(--muted);
          font-size: 12px;
          font-style: normal;
        }}
        .sample b,
        .repeat-row b {{
          display: block;
          color: var(--ink);
          margin: 4px 0;
        }}
        .signal-grid,
        .audit-grid {{
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(320px, 0.75fr);
          gap: 16px;
        }}
        .panel {{
          border: 1px solid rgba(16,24,40,0.1);
          border-radius: 8px;
          background: rgba(255,255,255,0.84);
          box-shadow: var(--soft-shadow);
          padding: 16px;
          margin-bottom: 14px;
        }}
        .panel h3 {{
          margin: 0 0 12px;
          color: var(--ink);
          font-size: 18px;
        }}
        .idea-row h3 {{
          color: var(--ink);
          font-size: 18px;
          line-height: 1.36;
          margin: 10px 0 6px;
        }}
        .idea-row p {{
          margin: 0 0 8px;
          line-height: 1.55;
        }}
        .source-row {{
          display: grid;
          grid-template-columns: minmax(0, 1fr) 64px;
          gap: 10px;
          align-items: center;
          margin: 10px 0;
        }}
        .source-row span {{
          display: block;
          color: var(--body);
          font-size: 13px;
          margin-bottom: 5px;
        }}
        .source-row strong {{
          color: var(--muted);
          font-size: 13px;
          text-align: right;
        }}
        .source-bar {{
          height: 8px;
          border-radius: 999px;
          background: #edf2f7;
          overflow: hidden;
        }}
        .source-bar b {{
          display: block;
          height: 100%;
          border-radius: inherit;
          background: linear-gradient(90deg, var(--green), var(--blue));
        }}
        .table-wrap {{
          max-width: 100%;
          overflow: auto;
          border: 1px solid var(--soft-line);
          border-radius: 8px;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          background: rgba(255,255,255,0.8);
          font-size: 13px;
        }}
        th, td {{
          padding: 9px 10px;
          border-bottom: 1px solid var(--soft-line);
          text-align: left;
          vertical-align: top;
        }}
        th {{
          color: var(--ink);
          background: var(--soft);
          font-size: 12px;
        }}
        td {{
          color: var(--body);
        }}
        pre {{
          max-height: 520px;
          overflow: auto;
          border: 1px solid var(--soft-line);
          border-radius: 8px;
          padding: 14px;
          background: #101828;
          color: #f8fafc;
          font-size: 12px;
          line-height: 1.55;
          white-space: pre-wrap;
        }}
        .muted {{ color: var(--muted); }}
        @keyframes enter {{
          from {{ opacity: 0; transform: translateY(18px) scale(.992); }}
          to {{ opacity: 1; transform: translateY(0) scale(1); }}
        }}
        @media (max-width: 980px) {{
          .app {{ grid-template-columns: 1fr; padding: 12px; }}
          .sidebar {{ position: relative; top: auto; min-height: auto; }}
          .hero-grid,
          .memo-layout,
          .signal-grid,
          .audit-grid {{ grid-template-columns: 1fr; }}
          .metrics,
          .status-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
        }}
        @media (max-width: 620px) {{
          .hero h2 {{ font-size: 38px; }}
          .metrics,
          .memo-stats,
          .status-grid,
          .health-summary,
          .check-row,
          .memo-head {{ grid-template-columns: 1fr; }}
          .score {{ text-align: left; }}
          .section-head {{ align-items: start; flex-direction: column; }}
        }}
      </style>
    </head>
    <body>
      <div class="app" data-composition-id="opc-dashboard-shell" data-width="1440" data-height="2600">
        <aside class="sidebar">
          <div class="brand">
            <span>LOCAL FIRST</span>
            <h1>OPC Pain Intelligence</h1>
            <p>Daily opportunity triage for evidence, payment signals, and validation actions.</p>
          </div>
          <nav class="nav">
            <button class="nav-btn active" data-view="command">指挥台 <span>{build_now}</span></button>
            <button class="nav-btn" data-view="signals">信号板 <span>{candidate_count}</span></button>
            <button class="nav-btn" data-view="audit">审计 <span>{error_count}</span></button>
          </nav>
          <div class="sidebar-data">
            <div class="side-stat"><span>Snapshot</span><b>{esc(generated_at)}</b></div>
            <div class="side-stat"><span>Analysis</span><b>{esc(analysis_label)}</b></div>
            <div class="side-stat"><span>Top Source</span><b>{esc(top_source or "N/A")}</b></div>
            <div class="side-stat"><span>Candidate Rate</span><b>{candidate_rate}%</b></div>
          </div>
        </aside>
        <main class="main">
          <section class="hero">
            <div class="hero-grid">
              <div>
                <div class="kicker">Evidence-first command board</div>
                <h2>{'进入验证台' if build_now else '补证据优先'}</h2>
                <p>本页只回答今天该看什么、为什么值得看、下一步怎么验证。原始样本和健康检查收进信号板与审计区。</p>
              </div>
              <div class="status-grid">
                <div><span>Raw Signals</span><b>{raw_count}</b></div>
                <div><span>Candidates</span><b>{candidate_count}</b></div>
                <div><span>Clusters</span><b>{cluster_count}</b></div>
                <div><span>Monitor</span><b>{monitor}</b></div>
              </div>
            </div>
          </section>
          <section class="metrics">
            {metric_tile("候选机会", candidate_count, f"原始信号 {raw_count}")}
            {metric_tile("需求簇", cluster_count, f"重复信号 {len(repeated)}")}
            {metric_tile("立即验证", build_now, "进入行动队列")}
            {metric_tile("来源错误", error_count, "保留可用信号")}
          </section>
          {notice_html(build_quality_notices(snapshot))}
          <section id="command" class="view active">
            <div class="brief">
              <h3>今日判断</h3>
              <p>扫描 {raw_count} 条原始信号，筛出 {candidate_count} 条候选，合并为 {cluster_count} 个需求簇。{build_now} 个进入立即验证，{monitor} 个继续观察。</p>
              <p>{esc('主要候选来源为 ' + top_source if top_source else '当前来源分布仍需继续积累。')}</p>
            </div>
            <div class="section-head">
              <h2>机会决策队列</h2>
              <p>按 funnel score、证据链、决策分排序</p>
            </div>
            {cluster_markup}
          </section>
          <section id="signals" class="view">
            <div class="section-head">
              <h2>信号板</h2>
              <p>候选、来源、重复信号</p>
            </div>
            <div class="signal-grid">
              <div class="panel">
                <h3>候选信号</h3>
                {''.join(idea_row(idea) for idea in ideas) or '<p class="muted">暂无候选信号。</p>'}
              </div>
              <div>
                <div class="panel">
                  <h3>来源分布</h3>
                  {source_platforms(source_stats)}
                </div>
                <div class="panel">
                  <h3>来源指标</h3>
                  {table_html(source_metrics, ['来源', '原始', '候选', '候选率', '信号', '需求簇', '可验证', '错误', '建议'])}
                </div>
                <div class="panel">
                  <h3>7 天重复信号</h3>
                  {repeated_html(repeated)}
                </div>
              </div>
            </div>
          </section>
          <section id="audit" class="view">
            <div class="section-head">
              <h2>审计</h2>
              <p>来源健康、分类、产物与日报</p>
            </div>
            <div class="audit-grid">
              <div>
                <div class="panel">
                  <h3>数据源健康</h3>
                  {source_health_html(source_health)}
                </div>
                <div class="panel">
                  <h3>分类分布</h3>
                  {counts_table(snapshot.get('category_counts', {}), '分类')}
                </div>
                <div class="panel">
                  <h3>人工标注</h3>
                  {counts_table(snapshot.get('label_counts', {}), '标注')}
                </div>
              </div>
              <div>
                <div class="panel">
                  <h3>发现产物</h3>
                  {table_html(artifact_rows, ['指标', '值'])}
                </div>
                <div class="panel">
                  <h3>Markdown 日报</h3>
                  {markdown_report_html(snapshot.get('markdown_report', ''))}
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>
      <script>
        const buttons = Array.from(document.querySelectorAll('.nav-btn'));
        const views = Array.from(document.querySelectorAll('.view'));
        buttons.forEach((button) => {{
          button.addEventListener('click', () => {{
            buttons.forEach((item) => item.classList.remove('active'));
            views.forEach((view) => view.classList.remove('active'));
            button.classList.add('active');
            document.getElementById(button.dataset.view).classList.add('active');
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
          }});
        }});
      </script>
    </body>
    </html>
    """


def build_empty_html() -> str:
    return """
    <!doctype html>
    <html lang="zh-CN">
    <head>
      <meta charset="utf-8" />
      <style>
        body { margin: 0; font-family: "Source Sans 3", "Noto Sans SC", "PingFang SC", sans-serif; background: #f8fafc; color: #475467; }
        .empty { margin: 24px; border: 1px solid #dfe4ea; border-radius: 8px; background: #fff; padding: 28px; }
        h1 { color: #101828; margin: 0 0 12px; font-size: 44px; }
        code { background: #f3f4f6; padding: 3px 6px; border-radius: 6px; }
      </style>
    </head>
    <body>
      <section class="empty">
        <h1>等待第一份快照</h1>
        <p>缺少 <code>data/dashboard_snapshot.json</code>。请在本地运行 <code>python3 local_runner.py</code>。</p>
      </section>
    </body>
    </html>
    """


snapshot = load_dashboard_snapshot()
st.markdown(
    """
    <style>
      [data-testid="stAppViewContainer"] { background: #f3f7f8; }
      [data-testid="stHeader"], [data-testid="stToolbar"] { display: none; }
      .block-container { padding: 0 !important; max-width: none !important; }
      iframe { display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

if snapshot is None:
    st.iframe(build_empty_html(), height=360)
else:
    height = min(7200, 1180 + len(snapshot.get("opportunity_clusters", [])) * 720 + len(snapshot.get("top_ideas", [])) * 150)
    st.iframe(build_dashboard_html(snapshot), height=height)
