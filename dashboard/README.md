# Relay dashboard

A zero-build static page that renders the committed evaluation snapshot and lets a
reviewer run one ticket through the grounding and policy gates.

## Run it

It's plain HTML + one generated data module. No build step.

```bash
# from the repo root, after `relay eval --out results/demo`:
python scripts/build_dashboard_data.py     # refresh dashboard/report-data.js
npx serve dashboard                         # or any static server; or open index.html
```

## Deploy it

Any static host. For example:

```bash
npx vercel deploy --prod dashboard          # or push dashboard/ to GitHub Pages
```

`report-data.js` embeds the report as `window.RELAY_REPORT`, so the page works
from a static host and from `file://` with no fetch/CORS step. Regenerate it
whenever the snapshot changes (CI checks it stays in sync).
