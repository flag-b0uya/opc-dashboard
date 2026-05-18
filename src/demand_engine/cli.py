from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

from .fetchers import fetch_all, fetch_source
from .filters import filter_candidates
from .llm_analysis import (
    CodexCLIClient,
    LLMClient,
    OpenAIResponsesClient,
    codex_cli_available,
    synthesize_with_llm,
)
from .models import RawItemInput
from .reports import render_daily_report
from .scoring import heuristic_score
from .storage import DemandStore


DEFAULT_CONFIG: dict[str, Any] = {
    "hn": {
        "queries": ["alternative to", "too expensive", "I wish", "manual workflow"],
        "lookback_hours": 24,
        "max_items": 100,
    },
    "reddit": {
        "subreddits": ["SaaS", "Entrepreneur", "smallbusiness", "freelance", "webdev"],
        "lookback_hours": 24,
        "max_items_per_subreddit": 50,
    },
    "app_store": {
        "apps": [{"name": "example_competitor", "id": "123456789", "country": "us"}],
        "max_reviews_per_app": 50,
    },
}


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with config_path.open("r", encoding="utf-8") as handle:
        user_config = json.load(handle)
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    for key, value in user_config.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return config


def offline_fixture_items() -> list[RawItemInput]:
    return [
        RawItemInput(
            source="hn",
            source_url="https://news.ycombinator.com/item?id=fixture-1",
            title="Alternative to manual client reports",
            body="I wish there was an alternative to this slow manual client reporting workflow. We would pay for something simple.",
            author="fixture",
            published_at="2026-05-18T00:00:00Z",
            metadata={"fixture": True},
        ),
        RawItemInput(
            source="reddit",
            source_url="https://www.reddit.com/r/SaaS/comments/fixture",
            title="Subscription too expensive for small teams",
            body="The current subscription is too expensive and missing basic approval features for client work.",
            author="fixture",
            published_at="2026-05-18T01:00:00Z",
            metadata={"fixture": True},
        ),
    ]


def _idea_with_source(idea: Any, candidates_by_id: dict[str, Any]) -> dict[str, Any]:
    candidate = candidates_by_id.get(idea.candidate_id)
    source_urls = list(getattr(idea, "source_urls", []) or [])
    if candidate and candidate.source_url and candidate.source_url not in source_urls:
        source_urls.append(candidate.source_url)
    return {
        "mvp_concept": idea.mvp_concept,
        "target_audience": idea.target_audience,
        "pain_summary": idea.pain_summary,
        "errc_score": idea.errc_score,
        "jtbd_score": idea.jtbd_score,
        "opc_score": idea.opc_score,
        "rice_score": idea.rice_score,
        "total_score": idea.total_score,
        "verdict": idea.verdict,
        "why": idea.why,
        "validation_step": idea.validation_step,
        **idea.evidence_payload(),
        "source_url": candidate.source_url if candidate else "n/a",
        "source_urls": source_urls,
    }


def _write_latest_artifact(
    path: Path,
    date: str,
    result: dict[str, int | str],
    report_ideas: list[dict[str, Any]],
) -> None:
    build_now_count = sum(1 for idea in report_ideas if idea.get("verdict") == "Build Now")
    monitor_count = sum(1 for idea in report_ideas if idea.get("verdict") == "Monitor")
    artifact = {
        "date": date,
        "analysis_mode": result["analysis_mode"],
        "summary": {
            "raw_count": result["raw_count"],
            "raw_inserted": result["raw_inserted"],
            "candidate_count": result["candidate_count"],
            "candidate_inserted": result["candidate_inserted"],
            "scored_count": result["scored_count"],
            "failed_scores": result["failed_scores"],
            "build_now_count": build_now_count,
            "monitor_count": monitor_count,
        },
        "tracks": sorted(report_ideas, key=lambda idea: int(idea.get("total_score", 0)), reverse=True),
    }
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")


def run_daily(
    root_dir: Path,
    config_path: Path,
    db_path: Path,
    offline_items: list[RawItemInput] | None = None,
    report_date: str | None = None,
    no_llm: bool = False,
    max_llm_candidates: int = 40,
    llm_client: LLMClient | None = None,
    llm_provider: str = "auto",
    llm_client_factory: Any | None = None,
) -> dict[str, int | str]:
    config = load_config(config_path)
    store = DemandStore(db_path)
    store.initialize()

    raw_items = offline_items if offline_items is not None else fetch_all(config)
    raw_inserted = store.upsert_raw_items(raw_items)

    candidates = filter_candidates(raw_items, existing_body_hashes=set())
    candidate_inserted = store.insert_candidates(candidates)

    failed_scores = 0
    analysis_mode = "heuristic"
    provider = "heuristic" if no_llm else llm_provider
    client: LLMClient | None = llm_client
    if client is not None and provider == "auto":
        provider = "llm"
    if client is None and provider != "heuristic":
        if llm_client_factory is not None:
            client = llm_client_factory(provider)
        elif provider == "codex" or (provider == "auto" and codex_cli_available()):
            client = CodexCLIClient(cwd=root_dir)
            provider = "codex"
        elif provider == "openai" or (provider == "auto" and os.environ.get("OPENAI_API_KEY")):
            client = OpenAIResponsesClient()
            provider = "openai"
    should_use_llm = client is not None and provider != "heuristic"
    if should_use_llm and candidates:
        try:
            analysis = synthesize_with_llm(candidates, client, max_candidates=max_llm_candidates)
            scored = analysis.scored_ideas
            failed_scores = analysis.failed_scores
            analysis_mode = provider
            if not scored:
                scored = [heuristic_score(candidate) for candidate in candidates]
                analysis_mode = "heuristic_fallback"
                failed_scores = max(failed_scores, 1)
        except Exception:
            scored = [heuristic_score(candidate) for candidate in candidates]
            analysis_mode = "heuristic_fallback"
            failed_scores = 1
    else:
        scored = [heuristic_score(candidate) for candidate in candidates]
    store.insert_scored_ideas(scored)

    candidates_by_id = {candidate.id: candidate for candidate in candidates}
    report_ideas = [_idea_with_source(idea, candidates_by_id) for idea in scored]
    date = report_date or datetime.now().date().isoformat()
    result = {
        "raw_count": len(raw_items),
        "raw_inserted": raw_inserted,
        "candidate_count": len(candidates),
        "candidate_inserted": candidate_inserted,
        "scored_count": len(scored),
        "failed_scores": failed_scores,
        "analysis_mode": analysis_mode,
    }
    report = render_daily_report(
        date=date,
        raw_count=len(raw_items),
        candidate_count=len(candidates),
        scored_ideas=report_ideas,
        failed_scores=failed_scores,
    )

    reports_dir = root_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{date}.md"
    report_path.write_text(report, encoding="utf-8")
    _write_latest_artifact(reports_dir / "latest.json", date, result, report_ideas)

    return {**result, "report_path": str(report_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Blue Ocean Demand Engine V0")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=Path("config/sources.json"))
    parser.add_argument("--db", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch one source and store raw items")
    fetch_parser.add_argument("--source", choices=["hn", "reddit", "app_store"], required=True)

    daily_parser = subparsers.add_parser("daily", help="Run the full daily pipeline")
    daily_parser.add_argument("--offline-fixture", action="store_true")
    daily_parser.add_argument("--date", default=None)
    daily_parser.add_argument("--no-llm", action="store_true", help="Force deterministic heuristic scoring")
    daily_parser.add_argument(
        "--llm-provider",
        choices=["auto", "codex", "openai", "heuristic"],
        default="auto",
        help="Analysis provider. auto prefers local Codex CLI, then OpenAI API, then heuristic.",
    )
    daily_parser.add_argument("--max-llm-candidates", type=int, default=40)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root
    config_path = args.config if args.config.is_absolute() else root / args.config
    db_path = args.db or Path(os.environ.get("DATABASE_URL", root / "data" / "demand_engine.db"))
    db_path = db_path if db_path.is_absolute() else root / db_path
    config = load_config(config_path)

    if args.command == "fetch":
        store = DemandStore(db_path)
        store.initialize()
        items = fetch_source(args.source, config)
        inserted = store.upsert_raw_items(items)
        print(json.dumps({"fetched": len(items), "inserted": inserted}, ensure_ascii=False))
        return 0

    if args.command == "daily":
        offline_items = offline_fixture_items() if args.offline_fixture else None
        result = run_daily(
            root_dir=root,
            config_path=config_path,
            db_path=db_path,
            offline_items=offline_items,
            report_date=args.date,
            no_llm=args.no_llm,
            llm_provider=args.llm_provider,
            max_llm_candidates=args.max_llm_candidates,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
