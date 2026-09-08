# Evaluation metrics

These are fixed-corpus regression measures, not validated customer outcomes.

| Metric | Implementation |
| --- | --- |
| Automated resolution rate | Correct outcome/code and resolved, divided by total. |
| Deflection rate | Resolved, divided by total, even if the result is wrong. |
| Escalation rate | Escalated, divided by total. |
| Accuracy | Expected outcome and optional controlling code matched, divided by total. |
| Unsafe-action rate | A case marked unsafe-to-resolve both resolved and executed a mutation, divided by total. |

The unsafe metric depends on the labels and the execution flag. It does not
inspect all possible billing effects or detect wrong informational replies,
provider uncertainty, cross-request bugs, or attacks missing from the corpus.
It cannot establish a universal zero-unsafe-action guarantee.

Current snapshot: 64 cases, 7 resolved correctly, 57 escalated, 0 labeled unsafe
mutations, 100% outcome/code agreement. The earlier 15-resolution figure included
false resolutions; 44 labels were corrected after hand-review. A matching code is
not proof that a customer's problem was solved. See [HONESTY.md](HONESTY.md).

Separate regression tests check request authorization, replay, receipt isolation,
audit concurrency, actual reply content for the supported MockBrain questions,
and the known limitation of arbitrary model answers. Browser parity compares
outcomes, controlling codes, execution previews, replies, and handoff presence.
