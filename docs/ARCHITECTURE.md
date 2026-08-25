# Architecture

Relay handles one ticket through a fixed pipeline. The order is load-bearing.

```
                 ┌──────────── relay.agent.Agent.handle ────────────┐
                 │                                                   │
 Ticket ──▶ retrieve (scoped) ──▶ brain.propose ──▶ grounding gate ─┼─▶ policy gate
                 │  store.get_*       AgentProposal   check_grounding │      decide
                 │  (customer-scoped)                                 │
                 │                                                    ▼
                 │                          ┌── both ALLOW ──▶ store.issue_refund / cancel
                 │                          │                      (last-line invariants)
                 │                          └── any block ──▶ escalate + CaseFile
                 │                                                    │
                 └──────────── hash-chained audit ◀───────────────────┘
                                       │
                                  TicketResolution
```

## The two gates are different questions

| | Policy gate (`relay.policy`) | Grounding gate (`relay.grounding`) |
|---|---|---|
| Asks | "Is this action **authorized**?" | "Is this action **backed by retrieved records**?" |
| Checks | cap, refund window, invoice status, ownership, confidence, topic sensitivity | the cited records exist, belong to this customer, and the change targets a cited record |
| Catches | over-cap / out-of-window / unpaid-invoice refunds, low-confidence and sensitive tickets | invented refunds, cross-customer citations, the prompt-injection "refund invoice X" case |
| Property | pure, deterministic, **deny-by-default**, no `else: allow` | pure, deterministic, rejects on any unverifiable claim |

An action auto-executes **only if** the grounding gate says *grounded* **and** the
policy gate returns `ALLOW`. Anything else escalates.

## The brain only proposes

`relay.brain` defines a `Brain` protocol with two implementations:

- **`MockBrain`** — deterministic, dependency-free, *ticket-trusting*. It does
  roughly what the ticket asks, including citing an invoice id a malicious ticket
  names. That naivety is intentional: it lets the eval prove the gates are
  load-bearing, because even a fully ticket-driven brain can't cause an unsafe
  action once the gates run. Drives CI and the fixed evaluation.
- **`ClaudeBrain`** — Claude with structured outputs (`messages.parse` →
  `AgentProposal`, Opus 4.8, adaptive thinking). On a refusal or parse failure it
  falls back to a safe escalation rather than guessing.

The brain returns a closed, discriminated `AgentProposal`: one of four actions
(`answer`, `refund`, `cancel_subscription`, `escalate`), a confidence, a
sensitivity flag, a customer reply, and a **grounding claim** (the records it
says justify the action). The gate verifies the claim; it never trusts it.

## Per-customer isolation

Retrieval (`store.get_subscriptions` / `get_invoices`) is scoped to the ticket's
customer id. The brain only ever sees that customer's records, so it cannot
construct a grounded reference to another account. If a ticket *names* a foreign
record id, the brain may cite it, but the grounding gate rejects it because it
isn't in the scoped records (`cited_invoice_not_found`).

## The store is the last line

`relay.store.InMemoryBillingStore` (and the `BillingStore` protocol) enforce
their own invariants regardless of upstream decisions: refunds can't exceed an
invoice's remaining balance, operations are idempotent by key, and a bad call
raises `BillingError`. A bug in the agent cannot double-refund. A raised
`BillingError` during execution fails closed to escalation.

## Audit

`relay.audit` is an append-only, hash-chained log with deny-by-default
(allowlist) redaction. Every resolution and escalation appends exactly one
record; `verify_chain` recomputes the chain to detect any tamper or drop. PII
(emails, names, raw ticket bodies) is dropped before a record is written —
records carry only ids, amounts, gate codes, and outcomes.

## Observability

`relay.observability` installs an OpenTelemetry SDK tracer provider and wraps each
step (`relay.handle_ticket` → `brain.propose` → `grounding` → `policy` →
`execute`) in a span. Point an OTLP exporter at any eval/observability backend and
the spans appear there unchanged. The trace id is returned on every
`TicketResolution`.

## Module map

| Module | Responsibility |
|---|---|
| `relay/domain.py` | immutable billing/ticket value objects (money in integer cents) |
| `relay/store.py` | system of record; idempotent, invariant-enforcing writes |
| `relay/actions.py` | the closed set of proposable actions |
| `relay/proposal.py` | the brain's structured output schema |
| `relay/brain.py` | `Brain` protocol, `MockBrain`, `ClaudeBrain` |
| `relay/grounding.py` | the grounding gate |
| `relay/policy.py` | the fail-closed policy gate |
| `relay/audit.py` | hash-chained, redacted audit log |
| `relay/observability.py` | OpenTelemetry tracing |
| `relay/agent.py` | the orchestrator + `TicketResolution` + `CaseFile` |
| `relay/metrics.py` | resolution / escalation / unsafe-action rates |
| `relay/eval/` | the golden world, suite, harness, report |
| `relay/service.py` | FastAPI surface |
| `relay/cli.py` | the `relay` command |
