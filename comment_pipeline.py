"""Convert sampled container comments into structured pain signals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional

from comment_sampler import sample_from_containers
from container_pipeline import CONTAINERS_FILE, load_containers
from signal_extractor import extract_pain_signal


PAIN_SIGNALS_FILE = Path(__file__).resolve().parent / "data" / "pain_signals.json"


def _container_by_id(containers: List[Dict]) -> Dict[str, Dict]:
    return {str(container.get("container_id", "")): container for container in containers}


def _comment_source_item(comment: Dict, container: Dict) -> Dict:
    text = str(comment.get("text") or comment.get("body") or "")
    return {
        "source_item_id": str(comment.get("comment_id") or comment.get("id") or ""),
        "source": str(container.get("platform") or container.get("source") or ""),
        "title": str(container.get("title", "")),
        "text": text,
        "source_url": str(container.get("url", "")),
    }


def build_comment_pain_signals(
    containers: List[Dict],
    comments_by_container: Dict[str, List[Dict]],
    max_per_container: int = 50,
) -> List[Dict]:
    containers_by_id = _container_by_id(containers)
    sampled = sample_from_containers(containers, comments_by_container, max_per_container=max_per_container)
    rows: List[Dict] = []
    for comment in sampled:
        container_id = str(comment.get("container_id", ""))
        container = containers_by_id.get(container_id, {})
        pain_signal = extract_pain_signal(_comment_source_item(comment, container))
        rows.append({
            "container_id": container_id,
            "container_title": container.get("title", ""),
            "container_url": container.get("url", ""),
            "comment_id": comment.get("comment_id") or comment.get("id") or "",
            "comment_text": comment.get("text") or comment.get("body") or "",
            "comment_score": comment.get("score", 0),
            "comment_created_at": comment.get("created_at", ""),
            "pain_signal": pain_signal,
        })
    return rows


def save_pain_signals(rows: List[Dict], path: Optional[Path] = None) -> None:
    target = Path(path or PAIN_SIGNALS_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def load_pain_signals(path: Optional[Path] = None) -> List[Dict]:
    target = Path(path or PAIN_SIGNALS_FILE)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def load_comments_by_container(path: Path) -> Dict[str, List[Dict]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sample comments from selected containers and extract pain signals.")
    parser.add_argument("--containers", default=str(CONTAINERS_FILE))
    parser.add_argument("--comments", required=True, help="JSON object keyed by container_id.")
    parser.add_argument("--max-per-container", type=int, default=50)
    parser.add_argument("--output", default=str(PAIN_SIGNALS_FILE))
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    containers = load_containers(Path(args.containers))
    comments = load_comments_by_container(Path(args.comments))
    rows = build_comment_pain_signals(containers, comments, max_per_container=args.max_per_container)
    save_pain_signals(rows, Path(args.output))
    print(f"Pain signals written: {args.output}")
    print(f"Pain signals: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
