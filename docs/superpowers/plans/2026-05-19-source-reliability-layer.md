# Source Reliability Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make daily dashboard publishing resilient when one public data source is blocked, rate-limited, or temporarily unavailable.

**Architecture:** Add a small source reliability module that persists last-good source payloads in a local ignored cache, records per-source status, and computes a publishable coverage gate. `local_runner.py` will use this layer before scoring, and `snapshot_exporter.py` will carry the resulting source health metadata into the static dashboard snapshot.

**Tech Stack:** Python standard library, existing `unittest` suite, JSON cache files under `data/`.

---

### Task 1: Source Cache and Coverage Gate

**Files:**
- Create: `source_reliability.py`
- Test: `tests/test_source_reliability.py`
- Modify: `.gitignore`

- [ ] Write failing tests for saving successful source fetches, reusing fresh cached items after failures, treating disabled sources as skipped, and blocking publish when no current or cached source has usable data.
- [ ] Implement `SourceFetchResult`, `run_source_with_cache`, `SourceReliabilityReport`, and JSON cache helpers.
- [ ] Ignore `data/source_cache.json`.
- [ ] Run `PYTHONPATH=. python3 -m unittest tests.test_source_reliability -v`.

### Task 2: Runner Integration

**Files:**
- Modify: `local_runner.py`
- Test: `tests/test_local_runner_config.py`

- [ ] Add a `--source-cache` path option and `source_cache_path` config field.
- [ ] Replace direct `run_demand_scan(...)` usage with source reliability fetches plus the existing scoring pipeline.
- [ ] Preserve output shape while adding `summary.source_health` and a blocked exit when coverage is not publishable.
- [ ] Run focused local runner tests.

### Task 3: Snapshot and Dashboard Metadata

**Files:**
- Modify: `snapshot_exporter.py`
- Modify: `dashboard_presenter.py`
- Test: `tests/test_snapshot_exporter.py`, `tests/test_dashboard_presenter.py`

- [ ] Carry `coverage_status`, per-source statuses, and cache usage into `source_health`.
- [ ] Surface cache fallback as a concise quality notice instead of raw transport errors on the main page.
- [ ] Run focused presenter/exporter tests.

### Task 4: Verify and Publish

**Files:**
- Modify: `data/dashboard_snapshot.json`
- Modify: `README.md`

- [ ] Regenerate snapshot with `python3 local_runner.py --analysis-provider codex`.
- [ ] Run `PYTHONPATH=. python3 -m unittest discover -v`.
- [ ] Run `python3 -m compileall codex_analysis.py local_runner.py snapshot_exporter.py opc_dashboard.py source_health_check.py source_reliability.py`.
- [ ] Commit and push to `main` only if the snapshot is valid and the worktree has only intentional changes.
