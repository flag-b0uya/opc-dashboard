# Blue Ocean Demand Engine V0

Small implementation of the one-person company demand engine described in `optimized-blue-ocean-demand-engine.md`.

The report format is evidence-pack first: each top track includes a source excerpt,
the opportunity thesis, the current workaround, anti-signals, confidence notes, and
the next validation step. The goal is to produce a short list of narrow SaaS/MVP
tracks worth validating, not a generic pile of startup ideas.

By default the daily pipeline tries to use the local Codex CLI account first, then
the OpenAI Responses API if `OPENAI_API_KEY` is present, then deterministic
heuristic scoring. The model path clusters related demand signals and synthesizes
opportunity tracks instead of turning each post into its own idea.

## Local Commands

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Run the full pipeline with deterministic offline fixture data:

```bash
PYTHONPATH=src python3 -m demand_engine.cli daily --offline-fixture
```

Force local heuristic mode:

```bash
PYTHONPATH=src python3 -m demand_engine.cli daily --no-llm
```

Force a specific analysis provider:

```bash
PYTHONPATH=src python3 -m demand_engine.cli daily --llm-provider codex
PYTHONPATH=src python3 -m demand_engine.cli daily --llm-provider openai
PYTHONPATH=src python3 -m demand_engine.cli daily --llm-provider heuristic
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

Run the dashboard locally:

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=src streamlit run streamlit_app.py
```

The dashboard reads `data/demand_engine.db` and the latest Markdown report from
`reports/`. If `reports/latest.json` exists, the dashboard uses that published
artifact first. This is the Streamlit Cloud path because the cloud app cannot see
your local SQLite database.

Streamlit Cloud deployment needs this repository pushed to GitHub. It does not need
model credentials because it only reads `reports/latest.json`.

## Daily Codex Automation

Recommended scheduled job:

```bash
PYTHONPATH=src python3 -m demand_engine.cli daily --max-llm-candidates 40
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
git add reports/latest.json
git commit -m "chore: publish daily demand report"
git push
```

`reports/latest.json` is intentionally tracked so Streamlit Cloud can refresh from
GitHub after the automation pushes. Date-stamped Markdown reports and SQLite
databases stay local by default.

## Configuration

Edit `config/sources.json` to change HN queries, subreddits, and App Store competitor IDs.

The App Store entry currently contains a placeholder app id. Replace it with real
competitor app ids before relying on App Store review signals.

Useful knobs:

- `--llm-provider codex`: use the local Codex CLI login for analysis.
- `CODEX_BIN`: optional path to a non-default Codex binary.
- `OPENAI_API_KEY`: optional fallback for OpenAI Responses API analysis.
- `OPENAI_MODEL`: optional OpenAI model override, default `gpt-4o-mini`.
- `--max-llm-candidates`: caps how many filtered candidates are sent to the model.
