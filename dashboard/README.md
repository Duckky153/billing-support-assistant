# Billing Support Assistant dashboard

A zero-build static page that renders the committed evaluation snapshot and lets a
reviewer run one ticket through the grounding and policy gates.

This is a decision preview, not billing execution or a sender. Replies and review
packets are visible drafts. Editing the ticket or customer invalidates the old
result. See ../docs/SAFETY.md for supported short requests and limitations.

## Run it

It's plain HTML + one generated data module. No build step.

```bash
# from the repo root, after `billing-support eval --out results/demo`:
python scripts/build_dashboard_data.py     # refresh dashboard/report-data.js
npx serve dashboard                         # or any static server; or open index.html
```

## Deploy it

`.github/workflows/pages.yml` publishes `dashboard/` to GitHub Pages when a push
to `main` changes it. The live copy is at
https://duckky153.github.io/billing-support-assistant/. Any static host also works.

`report-data.js` embeds the report as `window.BILLING_SUPPORT_REPORT`, so the page works
from a static host and from `file://` with no fetch/CORS step. Regenerate it
whenever the snapshot changes (CI checks it stays in sync).

Offline checks: `python scripts/check_js_parity.py` compares 64 fixed tickets plus
15 regressions against Python, including replies and handoff presence;
`node scripts/check_dashboard_ui.js` exercises the shipped page event handlers.
