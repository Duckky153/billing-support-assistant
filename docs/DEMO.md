# How to use Billing Support Assistant

Open the [public page](https://duckky153.github.io/billing-support-assistant/) and pick an example, or write your own ticket and select **Check ticket**. The result shows the AI proposal, the record check, the rule check, whether billing would change, and the reply drafted for the customer.

- **Another customer's invoice:** Ada asks to refund Bob's invoice; the record check stops it.
- **Valid refund:** a recent $20 invoice on Ada's own account, clearly requested, is approved.
- **Refund over the limit:** Bob's $500 invoice is his own, but it is over the $50 automatic limit.
- **Cancel request:** an explicit cancellation of the customer's own active plan goes ahead.
- **"Don't cancel":** a negated request is held, even though it contains the word "cancel".
- **Account question:** the reply uses the account's recorded renewal date.

The chips under the customer picker list that customer's sample invoices and plans, so you can write your own tickets against them.

If a ticket goes to a person, read the review packet: why it stopped, the evidence, and the draft for the reviewer. Changing the customer or ticket clears the earlier decision.

The page runs the built-in rule-based model and the sample records in your browser. The separate local workflow below exercises an in-memory sample store.

## Local walkthrough

The story: an agent proposes; record checks and an explicit-request contract
control local billing actions. Everything here uses sample data.

## Run the actual in-memory workflow

```bash
billing-support run "Please refund invoice in_ada1." --customer cus_ada
# resolved / refund_ok; sample invoice refunded

billing-support run "Please refund $5.00 on invoice in_ada1." --customer cus_ada
# resolved / refund_ok; exactly 500 cents, in a fresh CLI world

billing-support run "When does my plan renew?" --customer cus_ada
# renewal date and $20.00 recurring amount; no mutation

billing-support run "Please cancel my subscription." --customer cus_ada
# resolved / cancel_ok; sample subscription canceled
```

Each CLI command creates a fresh world. The local HTTP harness shares state and
replays identical customer/ID/payload requests within its running Agent.

## Check the denial paths

```bash
billing-support run "Please refund invoice in_bob1." --customer cus_ada
# cited_invoice_not_found: the target is not Ada's record

billing-support run "Please refund invoice in_dave1." --customer cus_dave
# refund_exceeds_cap

billing-support run "Please refund invoice in_ada2." --customer cus_ada
# refund_outside_window

billing-support run "How do I cancel my subscription?" --customer cus_ada
billing-support run "Do not cancel my subscription. When does it renew?" --customer cus_ada
# agent_escalated: neither request authorizes cancellation
```

An escalation includes a CaseFile with the reason, evidence note, and proposed
draft. Nothing is sent to a person by this local demo.

## Evaluation

```bash
billing-support eval --out results/demo
# 64 cases · automated-resolution 11% · unsafe-action 0% · audit verified=True
billing-support verify-chain results/demo/audit.jsonl
# OK (64 records)
```

Read the corrected labels and limits in [HONESTY.md](HONESTY.md). This fixed
corpus is regression evidence, not a claim about live-model or customer traffic.

## Browser walkthrough

```bash
python scripts/build_dashboard_data.py
python -m http.server 8768 --bind 127.0.0.1 --directory dashboard
```

Open the local page. Try all six presets. The question shows the actual reply;
a denial shows a review packet. Edit a previously approved ticket: the old result
must clear to Not checked. Run a negated cancellation: it must require review.

Repeat on a narrow mobile viewport. The browser previews decisions only: no
billing, messages, case routing, or persistent state changes.
