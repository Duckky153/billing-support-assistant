# What the results mean

## Current evidence

The committed evaluation uses one controlled billing world, a deterministic
MockBrain, and 64 fixed tickets. A fresh world is created for each ticket.
The current run resolves 7 and escalates 57; 0 labeled unsafe mutations execute.
Seven out of 64 is 10.9375%, rounded to 11% in the CLI.

The corpus is not representative of customer traffic. Passing it does not
establish production safety, customer satisfaction, or live-model accuracy.
The browser and Python checks include additional regressions outside the 64 cases.

## Why the prior result changed

The September 8 audit reproduced unwanted cancellations/refunds from questions,
cross-customer receipt reuse, broken concurrent audit linkage, and irrelevant
answers reported as resolved. Existing tests and the old fixed evaluation passed.

The candidate script had treated observed behavior as expected behavior, and
discarded discovered unsafe examples. That is not independent ground truth.
It now exports observations for review, retains counterexamples, and does not
generate approved golden labels.

All 64 ticket bodies were hand-reviewed against the sample records and the
bounded request contract. Forty-four expected outcome/code pairs changed.
The old 15 resolutions included irrelevant answers and ignored constraints;
the new grammar also hands off longer legitimate requests it cannot interpret.
This is a correction of the measurement and behavior, not evidence of a traffic
benchmark regression or improvement. Full changes are in the
[audit record](2026-09-08-WORKFLOW-AUDIT.md).

## Remaining boundaries

- Live Claude was not called in this audit. Its structured-output path was tested
  with injected responses, including malicious mutation proposals.
- Citation ownership is not semantic validation of an answer. A test shows that
  a wrong $999 answer can pass with a valid subscription citation. Confidence and
  sensitive-topic flags are supplied by the model, not independent classifiers.
- A CaseFile contains an evidence note and unsent proposed draft, not verified
  findings, a sent message, or a completed human handoff.
- Request matching is a narrow literal grammar, not general language understanding.
  Unknown wording requires review; it does not prove every negation or nuance is understood.
- Replay state is in memory, bound to one Agent/store instance. Restarted or
  multi-worker deployments need a durable authenticated request/receipt ledger.
- The Stripe adapter uses legacy-style injected object mappings and has not been
  verified against a live account or current end-to-end SDK flow. Current API-version
  mappings, pagination, charge-level refund reconciliation, and durable uncertain
  outcome handling remain prerequisites for production use.

The receipt checks use documented [refund amount, charge, and status fields](https://docs.stripe.com/api/refunds/object)
and [cancellation identity/status](https://docs.stripe.com/api/subscriptions/cancel).
[Stripe idempotency](https://docs.stripe.com/api/idempotent_requests) applies to POST
requests, not DELETE. Cancellation replay protection here is local, not a provider
idempotency promise. Provider timeouts or incomplete receipts require reconciliation;
they do not prove that a billing effect did not occur.

See [SAFETY.md](SAFETY.md) for exact request examples and audit-chain limits.
