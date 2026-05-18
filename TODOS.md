# TODOs

## Weekly Evidence Shortlist

- What: Add a weekly view that rolls persisted daily evidence packs into the top 3 opportunity tracks over 7 days.
- Why: The success metric is a 7-day shortlist of narrow SaaS/MVP tracks worth validation; daily evidence packs are the prerequisite signal.
- Pros: Makes the CLI directly answer "what should I validate this week?" and reduces day-to-day noise.
- Cons: Adds aggregation rules that should wait until the daily evidence-pack shape is proven.
- Context: Start from `scored_ideas.evidence_json`, group recurring target audiences or workflow pains, and preserve anti-signals in the weekly output.
- Depends on: Evidence-pack daily reports and persisted `evidence_json`.
