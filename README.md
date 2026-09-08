# Relay

A local support-agent demo with controlled billing records. A model proposes an
answer, refund, cancellation, or handoff. Python checks cited records, ownership,
billing limits, and a small explicit-request grammar before allowing a mutation.

```
intake → scoped records → proposal → grounding → policy → execute or handoff
       → audit record → response
```

The offline path uses a deterministic `MockBrain`; `ClaudeBrain` accepts structured
model output through the same execution gates. This is not a live support service.

## What works locally

- Supported account questions return the renewal date, recurring amount, active
  status, or latest invoice total from sample records.
- Explicit supported refund and cancellation requests pass through independent
  record and request checks. Unsupported wording goes to human review.
- A handoff includes the reason, evidence note, proposed action, and an unsent
  draft for review. The draft is not verified advice or confirmation of an effect.
- Same customer, ticket ID, and payload replay the original result once per
  running Agent. Changed content conflicts; other customers have separate keys.
- Concurrent audit appends retain a sequential hash chain. Exported snapshots
  cannot mutate the stored details.

See [the request contract](docs/SAFETY.md) for exact examples and boundaries.
No general natural-language safety or model-answer accuracy guarantee is made.

## Offline evaluation

The fixed 64-ticket corpus uses a fresh sample world per case. The current run
has **7 resolutions, 57 escalations, and 0 unsafe mutations under its labels**.
This is an adversarial-heavy regression corpus, not representative traffic.

```text
eval: 64 cases · automated-resolution 11% · unsafe-action 0% · audit verified=True
```

The September 8 audit found that earlier labels counted irrelevant answers and
ignored request constraints as resolutions. The previous 15/64 result is not a
valid comparison of customer problems solved. The corpus bodies remain unchanged;
44 expected outcome/code pairs changed. See the
[audit and label history](docs/2026-09-08-WORKFLOW-AUDIT.md) and
[metric limitations](docs/HONESTY.md).

## Run it

```bash
pip install -e ".[dev,service,llm]"
relay run "Please refund invoice in_ada1." --customer cus_ada
relay run "Please refund invoice in_bob1." --customer cus_ada
relay run "When does my plan renew?" --customer cus_ada
relay eval --out results/demo
relay verify-chain results/demo/audit.jsonl
python scripts/build_dashboard_data.py
python -m http.server 8768 --bind 127.0.0.1 --directory dashboard
```

The dashboard previews decisions only: no billing call, reply delivery, case
routing, or persistent state change. The CLI and local HTTP harness actually
mutate their in-memory sample store. CLI runs start fresh; HTTP requests share
state within one running app.

`relay serve` exposes the local HTTP harness. It trusts supplied customer IDs
and **must not be exposed as an authenticated production service**.

## Integration boundaries

Python, Pydantic, OpenTelemetry, FastAPI, and an optional Anthropic structured-output
client. Real-model runs require a key and incur provider usage; no real-model run
was performed for this repair.

The Stripe-like adapter is a reference seam tested with injected offline fakes.
It validates refund amount/charge/status and cancellation identity/status,
binds local replay keys, and stops on uncertain responses. It is not a verified
current Stripe deployment: durable replay, charge-level reconciliation, current
API-version mappings, pagination, authentication, and operational controls remain
production work. [Details and primary references](docs/HONESTY.md).

## Verification and docs

```bash
ruff format --check relay tests scripts
ruff check relay tests scripts
mypy
pytest -q
python scripts/check_js_parity.py
node scripts/check_dashboard_ui.js
python scripts/leakgate.py .
```

Node 22 runs the offline browser regressions. CI checks Python gates, fixed
snapshot regeneration, dashboard data, and Python/browser parity.

[Architecture](docs/ARCHITECTURE.md) · [Safety contract](docs/SAFETY.md) ·
[Threat model](docs/THREAT-MODEL.md) · [Metrics](docs/METRICS.md) ·
[Walkthrough](docs/DEMO.md) · [Contributing](docs/CONTRIBUTING.md)

MIT licensed.
