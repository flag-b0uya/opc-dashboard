#!/usr/bin/env python3
"""One-command delivery readiness check for the Phase 1 OPC pipeline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List


PHASE1_DELIVERY_COMMANDS = [
    [sys.executable, "phase1_test_suite.py"],
    [sys.executable, "-m", "compileall", "-q", "-x", r"(^|/)\.venv/", "."],
    [sys.executable, "health_check.py"],
]


def run_command(command: List[str], cwd: Path) -> Dict:
    completed = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    return {
        "name": " ".join(command),
        "status": "ok" if completed.returncode == 0 else "error",
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout.strip()[-1200:],
        "stderr_tail": completed.stderr.strip()[-1200:],
    }


def check_dashboard_snapshot_ready(root: Path | str = ".") -> Dict:
    root_path = Path(root)
    snapshot_path = root_path / "data/dashboard_snapshot.json"
    if not snapshot_path.exists():
        return {
            "status": "error",
            "path": str(snapshot_path),
            "message": "data/dashboard_snapshot.json is missing",
        }
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "error",
            "path": str(snapshot_path),
            "message": f"dashboard snapshot is not valid JSON: {exc}",
        }

    clusters = snapshot.get("opportunity_clusters") or []
    has_funnel_score = bool(clusters and isinstance(clusters[0], dict) and "funnel_score" in clusters[0])
    candidate_count = int((snapshot.get("summary") or {}).get("candidate_count") or 0)
    if not has_funnel_score:
        return {
            "status": "error",
            "path": str(snapshot_path),
            "candidate_count": candidate_count,
            "cluster_count": len(clusters),
            "has_funnel_score": False,
            "message": "dashboard_snapshot.json opportunity_clusters[0] is missing funnel_score",
        }
    return {
        "status": "ok",
        "path": str(snapshot_path),
        "candidate_count": candidate_count,
        "cluster_count": len(clusters),
        "has_funnel_score": True,
        "message": "dashboard snapshot is ready",
    }


def check_runtime_dependencies() -> Dict:
    dependencies = {
        "streamlit": "ok" if importlib.util.find_spec("streamlit") else "missing",
    }
    missing = [name for name, status in dependencies.items() if status != "ok"]
    return {
        "status": "error" if missing else "ok",
        "dependencies": dependencies,
        "message": "missing runtime dependencies: " + ", ".join(missing) if missing else "runtime dependencies are ready",
    }


def run_delivery_check(
    root: Path | str = ".",
    command_runner: Callable[[List[str], Path], Dict] = run_command,
    dependency_checker: Callable[[], Dict] = check_runtime_dependencies,
) -> Dict:
    root_path = Path(root)
    command_results = [command_runner(command, root_path) for command in PHASE1_DELIVERY_COMMANDS]
    runtime_result = dependency_checker()
    snapshot_result = check_dashboard_snapshot_ready(root_path)
    failed = [item for item in command_results if item.get("status") != "ok"]
    if runtime_result.get("status") != "ok":
        failed.append(runtime_result)
    if snapshot_result.get("status") != "ok":
        failed.append(snapshot_result)
    return {
        "status": "error" if failed else "ok",
        "commands": command_results,
        "runtime": runtime_result,
        "snapshot": snapshot_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1 OPC delivery readiness checks.")
    parser.add_argument("--root", default=".")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_delivery_check(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
