#!/usr/bin/env python3
"""Manual intake for high-signal external pain snippets."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from demand_engine import RawItem


MANUAL_INTAKE_FILE = Path(__file__).resolve().parent / "data" / "manual_intake.json"


def _manual_id(source: str, text: str, url: str) -> str:
    payload = url.strip() if url.strip() else "|".join([source or "", text or "", url or ""])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_manual_items(path: Optional[Path] = None) -> List[Dict]:
    target = Path(path or MANUAL_INTAKE_FILE)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def save_manual_items(items: List[Dict], path: Optional[Path] = None) -> None:
    target = Path(path or MANUAL_INTAKE_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def add_manual_item(source: str, text: str, url: str = "", note: str = "", path: Optional[Path] = None) -> Dict:
    item = {
        "id": _manual_id(source, text, url),
        "source": source.strip() or "manual",
        "url": url.strip(),
        "text": text.strip(),
        "note": note.strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    items = load_manual_items(path)
    if not any(existing.get("id") == item["id"] or (item["url"] and existing.get("url") == item["url"]) for existing in items):
        items.append(item)
        save_manual_items(items, path)
        return item
    for existing in items:
        if existing.get("id") == item["id"] or (item["url"] and existing.get("url") == item["url"]):
            return existing
    return item


def delete_manual_item(item_id: str, path: Optional[Path] = None) -> bool:
    items = load_manual_items(path)
    kept = [item for item in items if item.get("id") != item_id]
    if len(kept) == len(items):
        return False
    save_manual_items(kept, path)
    return True


def manual_items_to_raw_items(items: List[Dict]) -> List[RawItem]:
    raw_items: List[RawItem] = []
    for item in items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        source = str(item.get("source", "manual")).strip() or "manual"
        raw_items.append(RawItem(
            id=str(item.get("id") or _manual_id(source, text, str(item.get("url", "")))),
            source=f"Manual {source}",
            title=text[:80],
            body=text,
            source_url=str(item.get("url", "")),
            published_at=str(item.get("created_at", "")),
            metadata={
                "manual": True,
                "source": source,
                "note": str(item.get("note", "")),
            },
        ))
    return raw_items


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage manual pain signals in data/manual_intake.json.")
    subparsers = parser.add_subparsers(dest="command")

    add_parser = subparsers.add_parser("add", help="Add a manual pain signal.")
    add_parser.add_argument("--source", required=True)
    add_parser.add_argument("--text", required=True)
    add_parser.add_argument("--url", default="")
    add_parser.add_argument("--note", default="")

    subparsers.add_parser("list", help="List manual pain signals.")
    delete_parser = subparsers.add_parser("delete", help="Delete a manual pain signal by id.")
    delete_parser.add_argument("--id", required=True)
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "list":
        print(json.dumps(load_manual_items(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "delete":
        deleted = delete_manual_item(args.id)
        print(json.dumps({"deleted": deleted, "id": args.id}, ensure_ascii=False, indent=2))
        return 0 if deleted else 1
    item = add_manual_item(args.source, args.text, args.url, args.note)
    print(json.dumps(item, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
