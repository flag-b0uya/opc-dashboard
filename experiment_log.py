#!/usr/bin/env python3
"""Local experiment logging for validated opportunity clusters."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional


EXPERIMENT_RESULTS_FILE = Path(__file__).resolve().parent / "data" / "experiment_results.json"


def _safe_int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _experiment_id(cluster_id: str, channel: str, asset_type: str, audience: str, created_at: str) -> str:
    payload = "|".join([cluster_id, channel, asset_type, audience, created_at])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_experiments(path: Optional[Path] = None) -> List[Dict]:
    target = Path(path or EXPERIMENT_RESULTS_FILE)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def save_experiments(records: List[Dict], path: Optional[Path] = None) -> None:
    target = Path(path or EXPERIMENT_RESULTS_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def add_experiment(
    cluster_id: str,
    channel: str,
    asset_type: str,
    audience: str,
    posted_at: str = "",
    views: int = 0,
    clicks: int = 0,
    replies: int = 0,
    waitlist_signups: int = 0,
    calls_booked: int = 0,
    paid_commitments: int = 0,
    objections: Optional[List[str]] = None,
    decision: str = "pending",
    path: Optional[Path] = None,
) -> Dict:
    created_at = datetime.now().isoformat(timespec="seconds")
    record = {
        "experiment_id": _experiment_id(cluster_id, channel, asset_type, audience, created_at),
        "cluster_id": cluster_id,
        "channel": channel,
        "asset_type": asset_type,
        "audience": audience,
        "posted_at": posted_at or created_at,
        "views": _safe_int(views),
        "clicks": _safe_int(clicks),
        "replies": _safe_int(replies),
        "waitlist_signups": _safe_int(waitlist_signups),
        "calls_booked": _safe_int(calls_booked),
        "paid_commitments": _safe_int(paid_commitments),
        "main_objections": list(objections or []),
        "decision": decision or "pending",
    }
    records = load_experiments(path)
    records.append(record)
    save_experiments(records, path)
    return record


def summarize_by_cluster(records: Iterable[Dict]) -> Dict[str, Dict]:
    summaries: Dict[str, Dict] = {}
    for record in records:
        cluster_id = str(record.get("cluster_id", "")).strip()
        if not cluster_id:
            continue
        summary = summaries.setdefault(cluster_id, {
            "experiments_count": 0,
            "views": 0,
            "clicks": 0,
            "replies": 0,
            "waitlist_signups": 0,
            "calls_booked": 0,
            "paid_commitments": 0,
            "main_objections": [],
        })
        summary["experiments_count"] += 1
        for field in ["views", "clicks", "replies", "waitlist_signups", "calls_booked", "paid_commitments"]:
            summary[field] += _safe_int(record.get(field))
        for objection in record.get("main_objections", []) or []:
            if objection and objection not in summary["main_objections"]:
                summary["main_objections"].append(objection)
    return summaries


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record validation experiment results.")
    parser.add_argument("add", nargs="?")
    parser.add_argument("--cluster-id", required=True)
    parser.add_argument("--channel", required=True)
    parser.add_argument("--asset-type", required=True)
    parser.add_argument("--audience", required=True)
    parser.add_argument("--posted-at", default="")
    parser.add_argument("--views", type=int, default=0)
    parser.add_argument("--clicks", type=int, default=0)
    parser.add_argument("--replies", type=int, default=0)
    parser.add_argument("--waitlist-signups", type=int, default=0)
    parser.add_argument("--calls-booked", type=int, default=0)
    parser.add_argument("--paid-commitments", type=int, default=0)
    parser.add_argument("--objection", action="append", default=[])
    parser.add_argument("--decision", default="pending")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    record = add_experiment(
        cluster_id=args.cluster_id,
        channel=args.channel,
        asset_type=args.asset_type,
        audience=args.audience,
        posted_at=args.posted_at,
        views=args.views,
        clicks=args.clicks,
        replies=args.replies,
        waitlist_signups=args.waitlist_signups,
        calls_booked=args.calls_booked,
        paid_commitments=args.paid_commitments,
        objections=args.objection,
        decision=args.decision,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
