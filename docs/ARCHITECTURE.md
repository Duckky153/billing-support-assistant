# Architecture

```
ticket → scoped records → structured proposal → grounding → policy
                                                ↓             ↓
                                            denial         allow
                                                ↓             ↓
                                           CaseFile      store + receipt checks
                                                └──────┬──────┘
                                                   audit → response
```

The Python agent computes both gates; a grounding failure takes precedence over
the policy result. EscalateAction goes directly to the handoff builder.

## Request boundary and brains

MockBrain supports a small whole-request grammar and specific account questions.
ClaudeBrain returns an AgentProposal from structured model output; failures hand
off. Neither brain executes a billing operation.

The policy independently matches refund/cancel intent, target, and amount against
the request grammar, then combines that result with billing eligibility checks.
Confidence and topic sensitivity remain model-supplied flags. Grounding checks
record IDs/ownership and stated evidence presence, not the semantic truth of prose.

## Replay and receipts

One Agent serializes requests and binds (customer ID, ticket ID) to the request
payload excluding creation time. Same content returns the original deep-copied
resolution; changed content produces a conflict CaseFile without replacing the
original result. Hashed operation keys include customer and ticket identity.

InMemoryBillingStore locks writes, checks balance, and binds replay keys to exact
targets/amounts. The Stripe-like adapter additionally checks provider receipt
shape and preserves uncertain attempts for review. The executor checks receipt
target/amount/key/status before exporting success. These are process-local controls,
not a durable exactly-once system; see [SAFETY.md](SAFETY.md).

## Audit and tracing

AuditLog atomically appends sequential hash-linked records, allowlists detail
fields, and returns defensive snapshots. Identical request replays return the
original audit sequence; they do not create another decision record. An externally
trusted checkpoint is required to detect tail removal or replacement of the chain.

OpenTelemetry provider initialization is locked. Original decisions have spans;
replays return the original trace ID. Exporters are optional and not activated by
the local demo.

## Interfaces

- CLI: fresh sample world per invocation.
- HTTP: shared in-memory Agent; trusts the supplied customer ID; local harness only.
- Browser: static decision preview, no mutation, sending, or audit persistence.
  Python/browser parity checks include customer replies and review-packet presence.
- CaseFile: reason, gate code, proposed action, evidence note, and unsent draft.

## Module map

| Module | Responsibility |
| --- | --- |
| domain / actions / proposal | Validated record and proposal types |
| authorization | Bounded request grammar and target/amount binding |
| brain | Deterministic demo and optional structured-model proposal paths |
| grounding / policy | Citation checks and execution authorization |
| agent | Replay, orchestration, receipt checks, response and handoff |
| store / stripe_store | Sample mutations and offline-tested reference adapter |
| audit / observability | Chain integrity and tracing |
| eval / metrics | Fixed corpus, report, and label-dependent metrics |
| service / cli | Local entry points |
| dashboard | Static workflow preview and committed report |
