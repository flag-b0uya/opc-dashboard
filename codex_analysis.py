#!/usr/bin/env python3
"""Optional Codex-backed synthesis for existing OPC opportunity clusters."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional, Tuple


class CodexAnalysisError(RuntimeError):
    pass


def _extract_json_object(text: str) -> Dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise CodexAnalysisError("Codex output did not contain JSON")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise CodexAnalysisError(f"Codex output was invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CodexAnalysisError("Codex output must be a JSON object")
    return payload


def _compact_idea(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "idea_id": row.get("idea_id", ""),
        "title": row.get("title", ""),
        "source": row.get("source", ""),
        "source_url": row.get("source_url", ""),
        "category": row.get("category", ""),
        "total_score": row.get("total_score", 0),
        "pain_summary": row.get("pain_summary", ""),
        "mvp_concept": row.get("mvp_concept", ""),
        "validation_step": row.get("validation_step", ""),
    }


def _compact_cluster(cluster: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "cluster_id": cluster.get("cluster_id", ""),
        "title": cluster.get("title", ""),
        "category": cluster.get("category", ""),
        "decision_score": cluster.get("decision_score", 0),
        "decision_verdict": cluster.get("decision_verdict", "Monitor"),
        "decision_reason": cluster.get("decision_reason", ""),
        "evidence_summary": cluster.get("evidence_summary", ""),
        "recommended_action": cluster.get("recommended_action", ""),
        "sample_ideas": cluster.get("sample_ideas", []),
    }


def build_codex_prompt(rows: List[Dict[str, Any]], clusters: List[Dict[str, Any]]) -> str:
    payload = {
        "ideas": [_compact_idea(row) for row in rows[:80]],
        "clusters": [_compact_cluster(cluster) for cluster in clusters[:12]],
    }
    return (
        "You are improving a blue-ocean opportunity dashboard. Read the candidate ideas "
        "and existing heuristic clusters. Return only JSON with this shape: "
        '{"clusters":[{"cluster_id":"same id","title":"clear opportunity title",'
        '"evidence_summary":"specific evidence synthesis","decision_reason":"why this verdict",'
        '"recommended_action":"7-day validation action","decision_score":0,'
        '"decision_verdict":"Build Now|Monitor|Discard","codex_opportunity_thesis":"thesis",'
        '"codex_anti_signals":["risk"]}]}. Keep every cluster_id unchanged.\n\n'
        f"Input JSON:\n{json.dumps(payload, ensure_ascii=False)}"
    )


def _merge_clusters(clusters: List[Dict[str, Any]], codex_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    updates = codex_payload.get("clusters", [])
    if not isinstance(updates, list):
        raise CodexAnalysisError("Codex JSON must contain clusters array")
    updates_by_id = {
        update.get("cluster_id"): update
        for update in updates
        if isinstance(update, dict) and update.get("cluster_id")
    }
    enhanced: List[Dict[str, Any]] = []
    for cluster in clusters:
        update = updates_by_id.get(cluster.get("cluster_id"))
        if not update:
            enhanced.append(cluster)
            continue
        merged = dict(cluster)
        for key in [
            "title",
            "evidence_summary",
            "decision_reason",
            "recommended_action",
            "decision_score",
            "decision_verdict",
            "codex_opportunity_thesis",
            "codex_anti_signals",
        ]:
            if key in update:
                merged[key] = update[key]
        merged["analysis_provider"] = "codex"
        enhanced.append(merged)
    return enhanced


def analyze_clusters_with_codex(
    rows: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
    *,
    codex_bin: Optional[str] = None,
    timeout: int = 600,
    runner: Any = subprocess.run,
    cwd: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    binary = codex_bin or os.environ.get("CODEX_BIN", "codex")
    prompt = build_codex_prompt(rows, clusters)
    completed = runner(
        [binary, "exec", prompt, "-C", str(cwd or Path.cwd()), "-s", "read-only"],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or Path.cwd()),
    )
    if completed.returncode != 0:
        raise CodexAnalysisError(completed.stderr.strip() or "codex exec failed")
    payload = _extract_json_object(completed.stdout)
    return _merge_clusters(clusters, payload), {
        "analysis_provider": "codex",
        "analysis_status": "ok",
    }
