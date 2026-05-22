#!/usr/bin/env python3
"""Local health checks for OPC pipeline artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from snapshot_contract import validate_snapshot_contract


ARTIFACTS = [
    {"name": "dashboard_snapshot", "path": "data/dashboard_snapshot.json", "required": True},
    {"name": "manual_intake", "path": "data/manual_intake.json", "required": False},
    {"name": "source_metrics", "path": "data/source_metrics.json", "required": False},
    {"name": "source_metrics_history", "path": "data/source_metrics_history.json", "required": False},
    {"name": "experiment_results", "path": "data/experiment_results.json", "required": False},
    {"name": "containers", "path": "data/containers.json", "required": False},
    {"name": "comments_by_container", "path": "data/comments_by_container.json", "required": False},
    {"name": "pain_signals", "path": "data/pain_signals.json", "required": False},
]


def _read_json_file(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _check_json_file(root: Path, artifact: Dict) -> Dict:
    path = root / artifact["path"]
    if not path.exists():
        return {
            "name": artifact["name"],
            "path": artifact["path"],
            "required": artifact["required"],
            "status": "missing_required" if artifact["required"] else "missing_optional",
        }
    try:
        payload = _read_json_file(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "name": artifact["name"],
            "path": artifact["path"],
            "required": artifact["required"],
            "status": "invalid_json",
            "error": str(exc),
        }
    size = len(payload) if isinstance(payload, (list, dict)) else 1
    result = {
        "name": artifact["name"],
        "path": artifact["path"],
        "required": artifact["required"],
        "status": "ok",
        "size": size,
    }
    if artifact["name"] == "dashboard_snapshot":
        contract = validate_snapshot_contract(payload)
        result["contract_status"] = contract["status"]
        result["contract_errors"] = contract["errors"]
        result["contract_warnings"] = contract["warnings"]
        if contract["status"] == "error":
            result["status"] = "contract_error"
        elif contract["status"] == "warning":
            result["status"] = "contract_warning"
    return result


def _mark_stale_source_metrics(root: Path, checks: List[Dict]) -> None:
    by_name = {item["name"]: item for item in checks}
    source_check = by_name.get("source_metrics")
    if not source_check or source_check.get("status") != "ok":
        return

    try:
        snapshot = _read_json_file(root / "data/dashboard_snapshot.json")
        sidecar_metrics = _read_json_file(root / "data/source_metrics.json")
    except (OSError, json.JSONDecodeError):
        return

    snapshot_metrics = snapshot.get("source_metrics")
    if isinstance(snapshot_metrics, list) and snapshot_metrics != sidecar_metrics:
        source_check["status"] = "stale_warning"
        source_check["warning"] = "data/source_metrics.json does not match dashboard_snapshot source_metrics"


def summarize_status(checks: List[Dict]) -> Dict:
    return {
        "ok": sum(1 for item in checks if item.get("status") == "ok"),
        "missing_optional": sum(1 for item in checks if item.get("status") == "missing_optional"),
        "warnings": sum(1 for item in checks if str(item.get("status", "")).endswith("_warning")),
        "errors": sum(1 for item in checks if item.get("status") in {"missing_required", "invalid_json", "contract_error"}),
    }


def check_local_pipeline(root: Path | str = ".") -> Dict:
    root_path = Path(root)
    checks = [_check_json_file(root_path, artifact) for artifact in ARTIFACTS]
    _mark_stale_source_metrics(root_path, checks)
    summary = summarize_status(checks)
    return {
        "status": "error" if summary["errors"] else "ok",
        "summary": summary,
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local OPC artifact health.")
    parser.add_argument("--root", default=".")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = check_local_pipeline(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
