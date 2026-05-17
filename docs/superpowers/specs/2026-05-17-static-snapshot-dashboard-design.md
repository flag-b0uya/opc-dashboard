# Static Snapshot Dashboard Design

## Goal

GitHub and Streamlit should only publish and display results. All demand scanning, scoring, classification, manual labeling, and repeat-signal analysis run locally. The local workflow produces a committed data snapshot, and the deployed Streamlit app renders that snapshot as a polished landing page plus read-only dashboard.

## Architecture

The system has two explicit sides:

- Local execution side: runs the demand engine, updates local history and labels, calculates 7-day repeated signals, and exports a single dashboard snapshot file.
- Web display side: deployed on Streamlit, reads the committed snapshot from the repository, and renders a public-facing page. It never fetches Reddit, Hacker News, App Store, or Supabase, and it never writes labels or history.

The primary artifact is `data/dashboard_snapshot.json`. It is committed to GitHub after local generation. Streamlit Cloud then redeploys or refreshes from the repository and displays the latest committed snapshot.

## Data Flow

1. A local command runs the scanner using local configuration.
2. The command saves local history and label data.
3. The command computes summary metrics, top opportunities, category counts, repeated 7-day signals, and report text.
4. The command writes `data/dashboard_snapshot.json`.
5. The user commits and pushes the updated snapshot to GitHub.
6. Streamlit reads only `data/dashboard_snapshot.json` and renders the dashboard.

## Snapshot Shape

The snapshot should be stable and presentation-oriented:

- `generated_at`: latest local generation time.
- `summary`: raw count, candidate count, Build Now count, Monitor count, saved count.
- `top_ideas`: ranked opportunities with category, score, verdict, pain summary, validation step, source title, and source URL.
- `category_counts`: current or recent counts grouped by category.
- `repeated_signals_7d`: repeated signal cards with count, category, top score, sample concept, and sample URL.
- `label_counts`: manual label totals, including non-R&D demand labels.
- `markdown_report`: downloadable/readable report text.

The deployed app should tolerate missing keys and show empty states instead of failing.

## Streamlit UI

The Streamlit app becomes a display product:

- First viewport: landing-style hero for "蓝海机会雷达", with latest scan time, candidate count, Build Now count, and 7-day repeat count.
- Dashboard section: metric strip, category distribution, Top opportunities, repeated signals, and label summary.
- Report section: Markdown report preview and download.
- Empty state: when no snapshot exists, show a calm "等待本地生成结果" page with the expected local command.

There should be no scan button, no online source configuration, no manual label editor, and no Supabase setup UI on the deployed display page.

## Local Runner

A local runner script should own execution:

- Reads local defaults from a small config file or command arguments.
- Calls existing demand engine functions.
- Saves history and labels locally.
- Exports `data/dashboard_snapshot.json`.
- Prints next-step commands for reviewing and committing the snapshot.

This runner can later be scheduled with cron or launchd without changing the Streamlit app.

## Error Handling

Local execution records fetch errors into the snapshot report instead of blocking snapshot generation. Streamlit shows the last successful snapshot even if a later local run fails before committing a new snapshot. If the snapshot file is missing or invalid, Streamlit shows the empty state.

## Testing

Implementation should verify:

- Snapshot export works from a small local scan.
- Streamlit can render from the snapshot without importing or calling online fetch paths.
- Missing snapshot and partial snapshot states render cleanly.
- `compileall` passes for modified Python files.

## Out Of Scope

- Online scanning from Streamlit Cloud.
- Online label editing.
- Supabase as the primary display source.
- Authentication or private dashboard access.
- Automated GitHub commits from the Streamlit app.
