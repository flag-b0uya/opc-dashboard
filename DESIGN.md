# OPC Dashboard Design System

This dashboard is an app UI for daily opportunity triage, not a marketing page.
The interface should feel calm, evidence-first, and fast to scan.

## Typography

- Display and body stack: `Source Sans 3`, `Noto Sans SC`, `PingFang SC`, sans-serif.
- Body text must be at least 16px in evidence memos.
- Labels may use 13px only when paired with strong adjacent values.
- Avoid decorative type, centered marketing copy, and long instruction text.

## Color

- Ink: `#101828`
- Body: `#475467`
- Muted: `#667085`
- Border: `#dfe4ea`
- Surface: `#ffffff`
- Soft surface: `#f8fafc`
- Primary evidence green: `#0f766e`
- Action blue: `#2563eb`
- Warning amber: `#b45309`
- Critical red: `#b42318`

Body text must meet 4.5:1 contrast. Status colors may not be the only signal;
pair them with text labels such as `通过`, `缺口`, or `降级`.

## Spacing And Shape

- Use an 8px radius for cards, panels, and metric containers.
- Use 4px internal rhythm for labels, 8px for compact groups, 16px for content blocks, 24px for section breaks.
- Cards are allowed only when the card is an interaction or a decision memo.
- Secondary data belongs in an audit appendix, not in the primary decision path.

## Evidence Memo Pattern

Each demand cluster must read like a short investment memo:

1. Decision label and score.
2. Evidence-chain completeness.
3. Opportunity hypothesis.
4. Evidence.
5. Paid signal.
6. Why not build now, or why Build Now is justified.
7. Anti-signals.
8. Seven-day validation action.
9. Representative source samples.

Raw samples are supporting evidence, not the lead.

## Responsive Rules

- Desktop may use a hero plus radar panel, but opportunity memos are full-width.
- Mobile uses a single-column memo. Do not preserve desktop sidebars.
- On mobile, show verdict, evidence chain, and validation action before source samples.
- Touch targets for expanders, buttons, and links should be at least 44px tall where controllable.

## States

- Empty state: explain that the dashboard needs a generated snapshot and show the exact runner command.
- Codex fallback: keep the report visible, but mark the analysis as degraded and explain what is still usable.
- Partial source failure: keep usable opportunities visible and show which source health degraded.
- Incomplete evidence chain: show missing criteria inline. Do not hide the opportunity.
