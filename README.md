# Billing Support Assistant

A support assistant for a subscription business that answers billing questions
and handles refund and cancellation requests, without letting the AI move money
on its own. The AI proposes an action; code checks it against the customer's own
records and the billing rules; anything unclear goes to a person with a short
review packet.

**Live demo: [duckky153.github.io/billing-support-assistant](https://duckky153.github.io/billing-support-assistant/)**
(runs in your browser with the built-in rule-based model).

## Results

| Check | Result |
| --- | --- |
| 64 test tickets, each with an expected result | 7 resolved, 57 sent to review, 0 unsafe changes, 64 of 64 as expected |
| Stand-in model that always proposes harm (`billing-support hostile`) | 256 refund or cancellation proposals; 0 harmful ones executed |
| Automated tests | 194 Python tests, plus a check that the browser demo and the Python code agree on 88 tickets |
| Audit log | every decision is written to a hash-chained log; the 64-ticket chain verifies |

40 of the 64 tickets are built so that resolving them would be unsafe: another
customer's invoice, an over-limit refund, prompt injection, impersonation, a
legal threat, hidden instructions. See the [test results by ticket type](https://duckky153.github.io/billing-support-assistant/#results)
and the [evaluation history](docs/EVAL-HISTORY.md), which lists what testing
caught and why 44 expected results were corrected.

## How it works

```
ticket → customer's records → AI proposal → record check → policy check
       → execute, or hand off to a person → audit log
```

- **Record check** (`grounding.py`): every invoice or subscription the proposal
  cites must exist and belong to this customer.
- **Policy check** (`policy.py`): refund cap, refund window, invoice status and
  ownership are rules in code, deny by default. It also runs the request check
  (`authorization.py`): a refund or cancellation goes ahead only when the customer
  explicitly asked for that exact action. Questions ("How do I cancel?"), negations
  ("don't cancel"), conditions and combined requests go to review.

The offline path uses `MockBrain`, a rule-based stand-in for the model.
`ClaudeBrain` sends the same records to Claude and gets a structured proposal
that passes through the same checks. See [Architecture](docs/ARCHITECTURE.md).

## Run it

```bash
pip install -e ".[dev,service,llm]"
billing-support run "Please refund invoice in_ada1." --customer cus_ada   # resolved
billing-support run "Please refund invoice in_bob1." --customer cus_ada   # Bob's invoice: review
billing-support run "When does my plan renew?" --customer cus_ada
billing-support eval --out results/demo
billing-support hostile
billing-support verify-chain results/demo/audit.jsonl
python -m http.server 8768 --bind 127.0.0.1 --directory dashboard         # local demo page
```

## Checks

```bash
ruff format --check billing_support tests scripts && ruff check billing_support tests scripts
mypy && pytest -q
python scripts/check_js_parity.py && node scripts/check_dashboard_ui.js
python scripts/leakgate.py .
```

CI runs all of these, regenerates the evaluation and fails if the committed
results differ.

## Limits

- Sample data and a test suite, not live traffic. The Claude path and a
  Stripe-style adapter are built and tested with stand-in responses; neither has
  been run against a live account.
- The request rules are deliberately narrow, so some real requests with extra
  wording go to review instead of resolving.
- The local HTTP server (`billing-support serve`) trusts the customer ID it is
  given and is not an authenticated production service.

Details: [Safety rules](docs/SAFETY.md) · [Threat model](docs/THREAT-MODEL.md) ·
[What the results mean](docs/HONESTY.md) · [Metrics](docs/METRICS.md) ·
[Walkthrough](docs/DEMO.md) · [Contributing](docs/CONTRIBUTING.md)

MIT licensed.
