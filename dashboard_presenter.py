#!/usr/bin/env python3
"""Pure presentation helpers for the OPC Streamlit dashboard."""

from __future__ import annotations

from typing import Dict, List


def evidence_chain_summary(cluster: Dict) -> Dict:
    chain = cluster.get("evidence_chain") or {}
    total = int(chain.get("total_count") or 0)
    passed = int(chain.get("passed_count") or 0)
    score = int(chain.get("score") or (round(passed / total * 100) if total else 0))
    if total == 0:
        status = "unknown"
        label = "未评估"
    elif passed >= 4:
        status = "strong"
        label = "证据较完整"
    elif passed >= 3:
        status = "medium"
        label = "需要补证据"
    else:
        status = "weak"
        label = "证据不足"
    return {
        "passed_count": passed,
        "total_count": total,
        "score": score,
        "status": status,
        "label": label,
    }


def build_quality_notices(snapshot: Dict) -> List[Dict]:
    summary = snapshot.get("summary") or {}
    source_health = snapshot.get("source_health") or {}
    analysis = snapshot.get("analysis_metadata") or {}
    clusters = snapshot.get("opportunity_clusters") or []
    notices: List[Dict] = []

    provider = analysis.get("analysis_provider", "heuristic")
    status = analysis.get("analysis_status", "local")
    if provider == "codex" and status != "ok":
        notices.append({
            "level": "warning",
            "title": "Codex 分析已降级",
            "body": "当前报告仍可用于查看候选和规则聚类，但机会假设、反信号和付费信号可能没有经过大模型合成。",
        })
    elif provider == "codex" and status == "ok":
        notices.append({
            "level": "success",
            "title": "Codex 深度分析已完成",
            "body": "需求簇已生成中文机会假设、证据、反信号、付费信号和 7 天验证动作。",
        })

    errors = list(summary.get("errors") or [])
    error_count = int(source_health.get("error_count") or len(errors))
    cache_fallback_count = int(source_health.get("cache_fallback_count") or 0)
    if cache_fallback_count:
        notices.append({
            "level": "info",
            "title": "部分数据沿用缓存",
            "body": f"{cache_fallback_count} 个数据源本次未完全成功，已使用最近可用数据补齐。机会排序可用，但需要关注来源新鲜度。",
        })
    if error_count:
        notices.append({
            "level": "warning",
            "title": "部分数据源降级",
            "body": f"本次记录 {error_count} 个抓取错误。看板保留可用信号，但来源覆盖度会影响判断置信度。",
        })

    incomplete = [
        cluster for cluster in clusters
        if evidence_chain_summary(cluster)["status"] in {"weak", "medium", "unknown"}
    ]
    if incomplete:
        notices.append({
            "level": "info",
            "title": "存在证据链缺口",
            "body": f"{len(incomplete)} 个需求簇缺少独立来源、付费信号、替代方案抱怨、具体工作流或可触达验证中的至少一项。",
        })

    if not clusters and int(summary.get("candidate_count") or 0):
        notices.append({
            "level": "warning",
            "title": "候选存在但未形成需求簇",
            "body": "候选信号已抓到，但聚类结果为空。请检查聚类规则或 Codex 输出状态。",
        })

    return notices


def build_action_view(cluster: Dict) -> Dict:
    funnel = cluster.get("funnel_score") or {}
    return {
        "funnel": {
            "total_score": int(funnel.get("total_score") or 0),
            "verdict": funnel.get("verdict") or cluster.get("funnel_verdict") or "",
            "competitor_score": int(funnel.get("competitor_score") or 0),
            "distribution_score": int(funnel.get("distribution_score") or 0),
            "risk_penalty": int(funnel.get("risk_penalty") or 0),
            "blockers": list(funnel.get("blockers") or []),
        },
        "next_step": cluster.get("funnel_next_step") or funnel.get("next_step") or "",
    }


def build_source_metric_rows(source_metrics: List[Dict]) -> List[Dict]:
    rows: List[Dict] = []
    for item in source_metrics or []:
        rate = float(item.get("candidate_rate") or 0)
        rows.append({
            "来源": item.get("source", ""),
            "原始": int(item.get("raw_count") or 0),
            "候选": int(item.get("candidate_count") or 0),
            "候选率": f"{round(rate * 100)}%",
            "信号": int(item.get("signal_count") or 0),
            "需求簇": int(item.get("cluster_count") or 0),
            "可验证": int(item.get("validation_candidate_count") or 0),
            "错误": int(item.get("error_count") or 0),
            "建议": item.get("recommended_action", ""),
        })
    return sorted(rows, key=lambda row: (row["可验证"], row["候选"], -row["错误"]), reverse=True)


def build_artifact_summary_rows(container_summary: Dict, pain_signal_summary: Dict) -> List[Dict]:
    return [
        {"指标": "Containers", "值": int(container_summary.get("total_containers") or 0)},
        {"指标": "Selected Containers", "值": int(container_summary.get("selected_for_sampling") or 0)},
        {"指标": "Pain Signals", "值": int(pain_signal_summary.get("total_pain_signals") or 0)},
        {"指标": "High Confidence Signals", "值": int(pain_signal_summary.get("high_confidence_count") or 0)},
        {"指标": "Payment Signals", "值": int(pain_signal_summary.get("payment_signal_count") or 0)},
        {"指标": "Average Confidence", "值": pain_signal_summary.get("average_confidence", 0)},
    ]
