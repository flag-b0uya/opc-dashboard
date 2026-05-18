from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Protocol
from urllib.request import Request, urlopen

from .models import CandidateInput, ScoredIdea
from .scoring import ScoreParseError, parse_score_response


class LLMAnalysisError(RuntimeError):
    pass


class LLMClient(Protocol):
    def analyze(self, prompt: str, schema: dict[str, Any]) -> str | dict[str, Any]:
        pass


OPPORTUNITY_TRACKS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tracks", "discarded_patterns", "source_quality_notes"],
    "properties": {
        "tracks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "candidate_ids",
                    "mvp_concept",
                    "target_audience",
                    "pain_summary",
                    "source_excerpt",
                    "opportunity_thesis",
                    "existing_workaround",
                    "anti_signals",
                    "confidence_note",
                    "scores",
                    "why",
                    "validation_step",
                ],
                "properties": {
                    "candidate_ids": {"type": "array", "items": {"type": "string"}},
                    "mvp_concept": {"type": "string"},
                    "target_audience": {"type": "string"},
                    "pain_summary": {"type": "string"},
                    "source_excerpt": {"type": "string"},
                    "opportunity_thesis": {"type": "string"},
                    "existing_workaround": {"type": "string"},
                    "anti_signals": {"type": "array", "items": {"type": "string"}},
                    "confidence_note": {"type": "string"},
                    "scores": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["errc", "jtbd", "opc", "rice"],
                        "properties": {
                            "errc": {"type": "integer"},
                            "jtbd": {"type": "integer"},
                            "opc": {"type": "integer"},
                            "rice": {"type": "integer"},
                        },
                    },
                    "why": {"type": "string"},
                    "validation_step": {"type": "string"},
                },
            },
        },
        "discarded_patterns": {"type": "array", "items": {"type": "string"}},
        "source_quality_notes": {"type": "array", "items": {"type": "string"}},
    },
}


class LLMAnalysisResult:
    def __init__(self, scored_ideas: list[ScoredIdea], failed_scores: int = 0):
        self.scored_ideas = scored_ideas
        self.failed_scores = failed_scores


class OpenAIResponsesClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: int = 60):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout = timeout
        if not self.api_key:
            raise LLMAnalysisError("OPENAI_API_KEY is required for LLM analysis")

    def analyze(self, prompt: str, schema: dict[str, Any]) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "You are a demand researcher for one-person software businesses. "
                            "Cluster similar pain signals before proposing opportunity tracks. "
                            "Return only JSON that matches the schema."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "opportunity_tracks",
                        "strict": True,
                        "schema": schema,
                    }
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            "https://api.openai.com/v1/responses",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        output_text = _extract_response_text(payload)
        if not output_text:
            raise LLMAnalysisError("OpenAI response did not contain output text")
        return output_text


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise LLMAnalysisError("Codex output did not contain a JSON object")
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMAnalysisError(f"Codex output JSON was invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise LLMAnalysisError("Codex output must be a JSON object")
    return payload


class CodexCLIClient:
    def __init__(
        self,
        codex_bin: str | None = None,
        cwd: Path | str | None = None,
        timeout: int = 600,
        runner: Any | None = None,
    ):
        self.codex_bin = codex_bin or os.environ.get("CODEX_BIN", "codex")
        self.cwd = str(cwd or Path.cwd())
        self.timeout = timeout
        self.runner = runner or subprocess.run

    def analyze(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        full_prompt = (
            "You are the LLM analysis layer for an OPC demand-mining pipeline.\n"
            "Cluster similar demand signals before proposing opportunity tracks.\n"
            "Return only a JSON object. Do not include markdown fences or prose.\n\n"
            f"JSON schema:\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"{prompt}"
        )
        completed = self.runner(
            [self.codex_bin, "exec", full_prompt, "-C", self.cwd, "-s", "read-only"],
            capture_output=True,
            text=True,
            timeout=self.timeout,
            cwd=self.cwd,
        )
        if completed.returncode != 0:
            raise LLMAnalysisError(f"codex exec failed: {completed.stderr.strip()}")
        return _extract_json_object(completed.stdout)


def codex_cli_available(codex_bin: str | None = None) -> bool:
    binary = codex_bin or os.environ.get("CODEX_BIN", "codex")
    if shutil.which(binary) is None:
        return False
    try:
        completed = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def _extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                return text
    return ""


def _candidate_packet(candidate: CandidateInput, index: int) -> dict[str, Any]:
    return {
        "index": index,
        "candidate_id": candidate.id,
        "title": candidate.title,
        "source_url": candidate.source_url,
        "matched_rules": candidate.matched_rules,
        "text": candidate.normalized_text[:1200],
    }


def build_synthesis_prompt(candidates: list[CandidateInput]) -> str:
    packet = [_candidate_packet(candidate, index) for index, candidate in enumerate(candidates, start=1)]
    return (
        "Cluster these demand signals into 3-10 opportunity tracks. Do not create one "
        "track per post unless the pains are genuinely unrelated. Prefer narrow B2B "
        "or prosumer workflows with visible workarounds and willingness-to-pay signals. "
        "Every track must cite candidate_ids from the input and include anti_signals.\n\n"
        f"Candidates JSON:\n{json.dumps(packet, ensure_ascii=False)}"
    )


def _coerce_payload(response: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    try:
        payload = json.loads(response)
    except json.JSONDecodeError as exc:
        raise LLMAnalysisError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LLMAnalysisError("LLM response must be a JSON object")
    return payload


def parse_opportunity_tracks(payload: dict[str, Any], candidates: list[CandidateInput]) -> LLMAnalysisResult:
    tracks = payload.get("tracks")
    if not isinstance(tracks, list):
        raise LLMAnalysisError("LLM response must contain a tracks array")

    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    scored_ideas: list[ScoredIdea] = []
    failed_scores = 0

    for track in tracks:
        if not isinstance(track, dict):
            failed_scores += 1
            continue
        candidate_ids = track.get("candidate_ids", [])
        if not isinstance(candidate_ids, list):
            failed_scores += 1
            continue
        matched_candidates = [
            candidates_by_id[candidate_id]
            for candidate_id in candidate_ids
            if isinstance(candidate_id, str) and candidate_id in candidates_by_id
        ]
        if not matched_candidates:
            failed_scores += 1
            continue

        primary_id = matched_candidates[0].id
        response_payload = {key: value for key, value in track.items() if key != "candidate_ids"}
        try:
            idea = parse_score_response(primary_id, json.dumps(response_payload, ensure_ascii=False))
        except ScoreParseError:
            failed_scores += 1
            continue
        source_urls = []
        for candidate in matched_candidates:
            if candidate.source_url and candidate.source_url not in source_urls:
                source_urls.append(candidate.source_url)
        scored_ideas.append(replace(idea, source_urls=source_urls))

    return LLMAnalysisResult(scored_ideas=scored_ideas, failed_scores=failed_scores)


def synthesize_with_llm(
    candidates: list[CandidateInput],
    client: LLMClient,
    max_candidates: int = 40,
) -> LLMAnalysisResult:
    selected = candidates[:max_candidates]
    if not selected:
        return LLMAnalysisResult(scored_ideas=[], failed_scores=0)
    response = client.analyze(build_synthesis_prompt(selected), OPPORTUNITY_TRACKS_SCHEMA)
    payload = _coerce_payload(response)
    return parse_opportunity_tracks(payload, selected)
