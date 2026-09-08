# Threat model

Relay is a local sample-data harness, not an authenticated production service.

| Failure mode | Current control | Limit |
| --- | --- | --- |
| Model proposes an unwanted refund/cancel | Whole-request grammar checked independently at policy boundary | Unknown language hands off; not general semantic consent. |
| Invented or foreign record | Scoped retrieval, citation/target ownership checks | Supplied customer ID must already be authenticated upstream. |
| Over-cap, stale, unpaid, or excess refund | Deterministic policy plus store balance checks | Stripe charge-level reconciliation is not implemented. |
| Retry returns another customer's receipt | Customer-scoped keys, payload binding, receipt matching | Registries are process-local, not durable or multi-worker. |
| Same ticket ID with changed content | Conflict handoff, no new execution | Owner must use a new request ID after review. |
| Concurrent audit writes break linkage | Locked append/snapshot, defensive copies | An external checkpoint is needed to detect tail removal or full rewrites. |
| Confident wrong model answer | No semantic verifier | Valid citations do not make the reply true; explicitly covered as a known limitation. |
| Misleading evaluation labels | Hand-reviewed golden expectations; candidate tool exports observations only | Fixed corpus coverage is incomplete and not representative traffic. |

## Trust boundaries

The local HTTP endpoint trusts customer_id verbatim. A caller can impersonate any
sample customer; do not expose it publicly. Production must replace client-supplied
identity with an authenticated subject before constructing the ticket.

Ticket bodies and model proposals are untrusted. The model has no direct executor
access, but its confidence, sensitivity flag, evidence prose, and answer prose are
not independently validated facts. The store is trusted for record truth.
Provider responses are checked against the requested operation; a timeout or
mismatched receipt is an uncertain outcome requiring reconciliation.

The static dashboard has no sender, billing executor, case queue, or live monitor.
A preview labeled Approved means code would allow a sample action, not that a
customer was charged/refunded, a reply was sent, or a human accepted the case.

Secrets stay out of committed artifacts. Leak scanning and detail-field redaction
are controls, not a substitute for log access controls and credential governance.
