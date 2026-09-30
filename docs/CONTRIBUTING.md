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
python scripts/leakgate.py .          # no PII / secrets / private-project leakage
```

CI runs the same set, plus a JSON-schema validation of the committed eval
snapshot and a regenerate-and-diff check.

## How this codebase is built

- **TDD, strictly.** Write the failing test, watch it fail for the right reason,
  write the minimal code to pass. Every module here was built that way.
- **The gates are sacred.** Any change to `billing_support/policy.py` or `billing_support/grounding.py`
  must keep them pure, deterministic, and deny-by-default. There is no `else: allow`
  and there must never be one. New capabilities require a new action type **and**
  a matching, fully-tested allow-rule.
- **Adding an action** means: a new variant in `billing_support/actions.py`, an allow-rule in
  `billing_support/policy.py`, a grounding rule if it changes state, execution in
  `billing_support/agent.py`, and golden cases (including an adversarial one) in
  `billing_support/data/golden_tickets.json`.
- **Regenerate the snapshot** after any behavior change:
  `billing-support eval --out results/demo` (and `billing-support schema --out schema/run-report-v1.json`
  if the report shape changed). The snapshot test will otherwise fail.
- **No secrets, ever** in code, prompts, ticket bodies, fixtures, or the audit log.

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module map.
