# Contributing

## Setup

```bash
python -m venv .venv && source .venv/bin/activate     # or: uv venv
pip install -e ".[dev,service,llm]"
```

## The gate (all green before a commit lands)

```bash
ruff format billing_support tests scripts
ruff check billing_support tests scripts
mypy                                  # strict
pytest -q
python scripts/leakgate.py .          # no secrets or private terms in tracked files
```

CI runs the same set, plus a JSON-schema validation of the committed eval
snapshot and a regenerate-and-diff check.

## How this codebase is built

- **Test first.** Write a failing test for the behavior, then the smallest change
  that passes it.
- **Checks stay deny-by-default.** `billing_support/policy.py` and
  `billing_support/grounding.py` stay pure and deterministic, with no catch-all
  allow. A new capability needs a new action type and a tested allow rule.
- **Adding an action** means: a new variant in `billing_support/actions.py`, an allow-rule in
  `billing_support/policy.py`, a grounding rule if it changes state, execution in
  `billing_support/agent.py`, and golden cases (including an adversarial one) in
  `billing_support/data/golden_tickets.json`.
- **Request rules stay general.** Do not add phrases copied from a test ticket to
  `billing_support/authorization.py`; add new wording to the unseen-phrasing tests
  in `tests/test_authorization.py` instead.
- **Regenerate the snapshot** after any behavior change:
  `billing-support eval --out results/demo` (and `billing-support schema --out schema/run-report-v1.json`
  if the report shape changed). The snapshot test will otherwise fail.
- **No secrets, ever** in code, prompts, ticket bodies, fixtures, or the audit log.

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module map.
