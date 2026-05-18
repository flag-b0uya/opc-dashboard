#!/usr/bin/env python3
"""Optional Codex-backed synthesis for existing OPC opportunity clusters."""

from __future__ import annotations

import json
import os
from pathlib import Path
import glob
import shutil
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
        "evidence_chain": cluster.get("evidence_chain", {}),
        "recommended_action": cluster.get("recommended_action", ""),
        "sample_ideas": cluster.get("sample_ideas", []),
    }


def build_codex_prompt(rows: List[Dict[str, Any]], clusters: List[Dict[str, Any]]) -> str:
    payload = {
        "ideas": [_compact_idea(row) for row in rows[:80]],
        "clusters": [_compact_cluster(cluster) for cluster in clusters[:12]],
    }
    return (
        "你正在改进一个蓝海机会雷达。请阅读候选信号和已有启发式需求簇，"
        "把每个需求簇改写成中文、产品化、可执行的机会分析。"
        "不要逐条复述帖子，要合成需求。只返回 JSON，不要 Markdown。"
        "JSON 形状必须是："
        '{"clusters":[{"cluster_id":"保持原 id","title":"中文机会标题",'
        '"opportunity_hypothesis":"机会假设，1-2 句中文",'
        '"evidence":"证据，说明哪些重复痛点或来源支持它",'
        '"anti_signals":["反信号 1","反信号 2"],'
        '"not_build_now_reason":"为什么不是立即开工；如果是 Build Now 也说明最强理由",'
        '"seven_day_validation":"7 天验证动作，必须具体到触达人群、动作、通过标准",'
        '"paid_signal":"付费信号；没有就写尚不明确，并说明要验证什么",'
        '"decision_score":0,'
        '"decision_verdict":"Build Now|Monitor|Discard"}]}. '
        "每个 cluster_id 必须保持不变；所有面向用户的文字必须用中文。\n\n"
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
            "opportunity_hypothesis",
            "evidence",
            "anti_signals",
            "not_build_now_reason",
            "seven_day_validation",
            "paid_signal",
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
        if "opportunity_hypothesis" in update:
            merged["codex_opportunity_thesis"] = update["opportunity_hypothesis"]
        if "evidence" in update:
            merged["evidence_summary"] = update["evidence"]
        if "anti_signals" in update:
            merged["codex_anti_signals"] = update["anti_signals"]
        if "not_build_now_reason" in update:
            merged["decision_reason"] = update["not_build_now_reason"]
        if "seven_day_validation" in update:
            merged["recommended_action"] = update["seven_day_validation"]
        merged["analysis_provider"] = "codex"
        enhanced.append(merged)
    return enhanced


def _candidate_codex_bins(codex_bin: Optional[str]) -> List[str]:
    if codex_bin:
        return [codex_bin]

    candidates: List[str] = []
    env_bin = os.environ.get("CODEX_BIN")
    if env_bin:
        candidates.append(env_bin)

    # Keep the plain command first so cloud Codex environments can resolve their own CLI.
    candidates.append("codex")
    path_bin = shutil.which("codex")
    if path_bin:
        candidates.append(path_bin)

    home = Path.home()
    patterns = [
        str(home / ".vscode/extensions/openai.chatgpt-*/bin/macos-aarch64/codex"),
        str(home / ".cursor/extensions/openai.chatgpt-*/bin/macos-aarch64/codex"),
    ]
    for pattern in patterns:
        candidates.extend(sorted(glob.glob(pattern), reverse=True))

    unique: List[str] = []
    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    return unique


def analyze_clusters_with_codex(
    rows: List[Dict[str, Any]],
    clusters: List[Dict[str, Any]],
    *,
    codex_bin: Optional[str] = None,
    timeout: int = 600,
    runner: Any = subprocess.run,
    cwd: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    prompt = build_codex_prompt(rows, clusters)
    errors: List[str] = []
    for binary in _candidate_codex_bins(codex_bin):
        completed = runner(
            [binary, "exec", prompt, "-C", str(cwd or Path.cwd()), "-s", "read-only"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd or Path.cwd()),
        )
        if completed.returncode != 0:
            errors.append(f"{binary}: {completed.stderr.strip() or 'codex exec failed'}")
            continue
        payload = _extract_json_object(completed.stdout)
        return _merge_clusters(clusters, payload), {
            "analysis_provider": "codex",
            "analysis_status": "ok",
            "analysis_binary": binary,
        }
    raise CodexAnalysisError("; ".join(errors) or "No Codex CLI candidates were available")
