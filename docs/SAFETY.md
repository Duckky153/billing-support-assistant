# Local execution contract

The checks below are tested controls with explicit limits, not a guarantee that
arbitrary model output or customer language is safe.

## Independent mutation authorization

Both MockBrain and ClaudeBrain proposals pass through `policy.decide`.
A refund or cancellation must pass ownership, grounding, billing eligibility,
confidence/sensitivity gates, and `authorization.authorizes`.

Authorization matches the whole request against a deliberately small grammar.
It does not take the model's claimed intent as permission. Examples:

| Request | Meaning in the sample workflow |
| --- | --- |
| Please refund invoice in_ada1. | Refund that invoice's remaining balance, subject to all gates. |
| Please refund $5.00 on invoice in_ada1. | Refund exactly 500 cents on that invoice. |
| Please refund me. | Refund the remaining balance of the latest paid, refundable invoice. |
| Please cancel my subscription. | Cancel the one active subscription immediately. Multiple active subscriptions need an explicit target. |
| Please cancel subscription sub_ada. | Cancel that subscription, subject to ownership and status. |
| Refund / Please refund. | Underspecified; hand off. |
| How do I cancel? / Do not cancel… / Cancel if… | No mutation authorization. |
| Refund and cancel / quoted commands / unknown prose | Unsupported; hand off. |

Common polite forms and brief duplicate-charge context are supported. This is
not a semantic classifier; longer legitimate requests may also need review.
Named amounts and targets must match the proposed action exactly. A changed
invoice ID, amount, or action type is not authorized by a different valid request.

## Records and execution

- Grounding checks cited record existence/ownership and requires a stated evidence
  note and the target citation for mutations. It does not prove the evidence prose.
- Policy independently checks paid status, remaining balance, cap, window, and
  subscription ownership/status. Confidence and sensitivity are still model flags.
- Only the executor calls the billing store. It checks that the returned receipt
  matches the approved target, amount, key, and cancellation status.
- A rejected proposal has no execution call. A downstream timeout or bad receipt
  may follow an actual provider effect: the response is a handoff, not proof that
  nothing happened. Verify downstream state before retrying.

## Replay and concurrency

One running Agent binds customer + ticket ID to the complete request payload
(excluding server-generated creation time). Identical retries return the original
resolution/audit sequence; changed content yields `request_id_conflict`.
Different customers have different hashed operation keys. Calls are serialized
within that Agent; store writes and shared audit appends have their own locks.

The stores reject a reused operation key with a different target or amount.
The Stripe-like adapter retains uncertain attempts rather than blindly retrying.
All these registries are process-local: there is no durable or multi-worker
exactly-once guarantee, and no automatic eviction/reconciliation service.

## Audit and trust limits

Audit append and snapshot operations are locked; detail fields are allowlisted
at append. IDs are still identifiers, so real logs require access controls.
Hashes detect changed records, interior removal, and broken sequence/linkage.
A valid prefix or a completely rewritten chain cannot be detected without an
externally trusted head/checkpoint. The chain is not an immutable external ledger.

The HTTP demo trusts `customer_id`. Production must supply authenticated identity.
Arbitrary model AnswerAction prose is not semantically checked: a confident wrong
answer can pass with valid citations. A regression test pins this limitation.
The static browser has no billing executor, durable audit, sender, or case queue.
