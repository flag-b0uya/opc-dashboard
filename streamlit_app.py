from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parent


def find_latest_report(root: Path = ROOT) -> Path | None:
    reports = sorted((root / "reports").glob("*.md"), key=lambda path: path.stat().st_mtime, reverse=True)
    return reports[0] if reports else None


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_metrics(db_path: Path = ROOT / "data" / "demand_engine.db") -> dict[str, int]:
    if not db_path.exists():
        return {
            "raw_items": 0,
            "candidates": 0,
            "scored_ideas": 0,
            "build_now": 0,
            "monitor": 0,
            "discard": 0,
        }
    with closing(_connect(db_path)) as conn:
        raw_items = conn.execute("select count(*) from raw_items").fetchone()[0]
        candidates = conn.execute("select count(*) from candidates").fetchone()[0]
        scored_ideas = conn.execute("select count(*) from scored_ideas").fetchone()[0]
        verdicts = {
            str(row["verdict"]): int(row["count"])
            for row in conn.execute("select verdict, count(*) as count from scored_ideas group by verdict")
        }
    return {
        "raw_items": int(raw_items),
        "candidates": int(candidates),
        "scored_ideas": int(scored_ideas),
        "build_now": verdicts.get("Build Now", 0),
        "monitor": verdicts.get("Monitor", 0),
        "discard": verdicts.get("Discard", 0),
    }


def _parse_evidence(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value) if value else {}
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_tracks(db_path: Path = ROOT / "data" / "demand_engine.db", limit: int = 20) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    query = """
        select
          scored_ideas.mvp_concept,
          scored_ideas.target_audience,
          scored_ideas.pain_summary,
          scored_ideas.total_score,
          scored_ideas.verdict,
          scored_ideas.why,
          scored_ideas.validation_step,
          scored_ideas.evidence_json,
          raw_items.source_url as source_url
        from scored_ideas
        left join candidates on candidates.id = scored_ideas.candidate_id
        left join raw_items on raw_items.id = candidates.raw_item_id
        order by scored_ideas.total_score desc
        limit ?
    """
    with closing(_connect(db_path)) as conn:
        rows = conn.execute(query, (limit,)).fetchall()
    tracks: list[dict[str, Any]] = []
    for row in rows:
        evidence = _parse_evidence(str(row["evidence_json"]))
        track = {key: row[key] for key in row.keys() if key != "evidence_json"}
        track.update(evidence)
        if not track.get("source_urls") and track.get("source_url"):
            track["source_urls"] = [track["source_url"]]
        tracks.append(track)
    return tracks


def load_published_artifact(root: Path = ROOT) -> dict[str, Any] | None:
    artifact_path = root / "reports" / "latest.json"
    if not artifact_path.exists():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _metrics_from_artifact(artifact: dict[str, Any]) -> dict[str, int]:
    summary = artifact.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return {
        "raw_items": int(summary.get("raw_count", 0)),
        "candidates": int(summary.get("candidate_count", 0)),
        "scored_ideas": int(summary.get("scored_count", 0)),
        "build_now": int(summary.get("build_now_count", 0)),
        "monitor": int(summary.get("monitor_count", 0)),
        "discard": 0,
    }


def load_dashboard_data(root: Path = ROOT) -> dict[str, Any]:
    artifact = load_published_artifact(root)
    if artifact is not None:
        tracks = artifact.get("tracks", [])
        return {
            "source": "published",
            "date": artifact.get("date", ""),
            "analysis_mode": artifact.get("analysis_mode", ""),
            "metrics": _metrics_from_artifact(artifact),
            "tracks": tracks if isinstance(tracks, list) else [],
        }

    db_path = root / "data" / "demand_engine.db"
    return {
        "source": "database",
        "date": "",
        "analysis_mode": "",
        "metrics": load_metrics(db_path),
        "tracks": load_tracks(db_path),
    }


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="OPC Demand Engine", layout="wide")
    st.title("OPC Demand Engine")

    db_path = ROOT / "data" / "demand_engine.db"
    latest_report = find_latest_report(ROOT)
    dashboard = load_dashboard_data(ROOT)
    metrics = dashboard["metrics"]
    tracks = dashboard["tracks"]

    metric_cols = st.columns(5)
    metric_cols[0].metric("Raw", metrics["raw_items"])
    metric_cols[1].metric("Candidates", metrics["candidates"])
    metric_cols[2].metric("Scored", metrics["scored_ideas"])
    metric_cols[3].metric("Build Now", metrics["build_now"])
    metric_cols[4].metric("Monitor", metrics["monitor"])

    if latest_report:
        st.caption(f"Latest report: {latest_report.name}")
    elif dashboard["source"] == "published":
        st.caption(f"Latest published artifact: {dashboard['date']}")
    else:
        st.info("No report yet. Run `PYTHONPATH=src python3 -m demand_engine.cli daily` first.")

    st.header("Opportunity Tracks")
    if not tracks:
        st.warning("No scored opportunity tracks found.")
    for track in tracks:
        with st.expander(f"{track['total_score']} · {track['mvp_concept']}", expanded=False):
            st.write(f"**Verdict:** {track['verdict']}")
            st.write(f"**Audience:** {track['target_audience']}")
            st.write(f"**Pain:** {track['pain_summary']}")
            st.write(f"**Thesis:** {track.get('opportunity_thesis', track['why'])}")
            st.write(f"**Existing workaround:** {track.get('existing_workaround', 'Unknown')}")
            st.write(f"**Validation:** {track['validation_step']}")
            anti_signals = track.get("anti_signals") or []
            if anti_signals:
                st.write("**Anti-signals:**")
                for signal in anti_signals:
                    st.write(f"- {signal}")
            source_urls = track.get("source_urls") or []
            if source_urls:
                st.write("**Sources:**")
                for url in source_urls:
                    st.link_button(url, url)

    if latest_report:
        st.header("Markdown Report")
        st.markdown(latest_report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
