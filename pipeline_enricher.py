"""Enrich opportunity clusters with funnel scoring fields."""

from __future__ import annotations

import copy
from typing import Dict, List

from opportunity_funnel import FunnelInput, score_funnel


def _cluster_text(cluster: Dict) -> str:
    parts = [
        str(cluster.get("title", "")),
        str(cluster.get("category", "")),
        str(cluster.get("decision_reason", "")),
        str(cluster.get("evidence_summary", "")),
    ]
    for idea in cluster.get("sample_ideas", []) or []:
        parts.extend([
            str(idea.get("title", "")),
            str(idea.get("pain_summary", "")),
            str(idea.get("source", "")),
        ])
    return " ".join(part for part in parts if part)


def cluster_to_funnel_input(cluster: Dict) -> FunnelInput:
    chain = cluster.get("evidence_chain") or {}
    evidence_score = int(chain.get("score") or 0)
    if not evidence_score:
        passed = int(chain.get("passed_count") or 0)
        total = int(chain.get("total_count") or 0)
        evidence_score = round(passed / total * 100) if total else 0
    return FunnelInput(
        cluster_id=str(cluster.get("cluster_id", "")),
        title=str(cluster.get("title", "")),
        category=str(cluster.get("category", "")),
        evidence_score=evidence_score,
        source_count=int(cluster.get("source_count") or 0),
        count_7d=int(cluster.get("count_7d") or 0),
        top_score=int(cluster.get("top_score") or cluster.get("decision_score") or 0),
        text=_cluster_text(cluster),
    )


def enrich_clusters_with_pipeline(clusters: List[Dict]) -> List[Dict]:
    enriched: List[Dict] = []
    for cluster in clusters:
        row = copy.deepcopy(cluster)
        funnel_score = score_funnel(cluster_to_funnel_input(cluster))
        row["funnel_score"] = funnel_score
        row["funnel_verdict"] = funnel_score["verdict"]
        row["funnel_next_step"] = funnel_score["next_step"]
        enriched.append(row)
    return enriched
