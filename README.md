# Blue Ocean Demand Engine V0

Small, stdlib-only implementation of the one-person company demand engine described in `optimized-blue-ocean-demand-engine.md`.

## Local Commands

Run tests:

```bash
PYTHONPATH=src python3 -m unittest -v
```

Run the full pipeline with deterministic offline fixture data:

```bash
PYTHONPATH=src python3 -m demand_engine.cli daily --offline-fixture
```

Fetch one live source:

```bash
PYTHONPATH=src python3 -m demand_engine.cli fetch --source hn
PYTHONPATH=src python3 -m demand_engine.cli fetch --source reddit
PYTHONPATH=src python3 -m demand_engine.cli fetch --source app_store
```

Run the full live daily pipeline:

```bash
PYTHONPATH=src python3 -m demand_engine.cli daily
```

The default database is `data/demand_engine.db`, and reports are written to `reports/YYYY-MM-DD.md`.

## Configuration

Edit `config/sources.json` to change HN queries, subreddits, and App Store competitor IDs.

The first version uses deterministic heuristic scoring when no LLM integration is configured, so the pipeline can run locally without network-dependent model calls.
