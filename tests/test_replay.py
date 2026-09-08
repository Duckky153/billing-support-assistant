"""Real request retries, tenant isolation, and the final receipt boundary."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from relay.agent import Agent, Outcome
from relay.audit import verify_chain
from relay.brain import MockBrain
from relay.domain import Channel, SubscriptionStatus, Ticket
from relay.eval.golden import NOW, build_world
from relay.service import create_app
from relay.store import BillingError, CancelReceipt, InMemoryBillingStore, RefundReceipt


def make_ticket(body: str, customer: str = "cus_ada") -> Ticket:
    return Ticket(
        id="same-request",
        customer_id=customer,
        subject="Billing",
        body=body,
        channel=Channel.API,
        created_at=NOW,
    )


def test_identical_refund_retries_return_original_result_and_one_effect() -> None:
    store = build_world()
    agent = Agent(brain=MockBrain(), store=store, clock=lambda: NOW)
    ticket = make_ticket("Please refund invoice in_ada1.")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(agent.handle, [ticket] * 16))
    assert results[0].outcome is Outcome.RESOLVED
    assert all(r == results[0] for r in results)
    assert store.get_invoice("in_ada1").refunded_cents == 2000
    assert len(agent.audit.records) == 1
    assert verify_chain(agent.audit.records)


def test_same_ticket_id_for_two_customers_has_isolated_receipts() -> None:
    store = build_world()
    client = TestClient(create_app(Agent(brain=MockBrain(), store=store, clock=lambda: NOW)))
    for customer, subscription in [("cus_ada", "sub_ada"), ("cus_erin", "sub_erin")]:
        response = client.post(
            "/tickets",
            json={
                "ticket_id": "same-request",
                "customer_id": customer,
                "subject": "Billing",
                "body": "Please cancel my subscription.",
            },
        )
        assert response.status_code == 200
        assert response.json()["receipt"]["subscription_id"] == subscription
        assert store.get_subscription(subscription).status is SubscriptionStatus.CANCELED


def test_changed_payload_same_customer_and_id_conflicts_without_new_effect() -> None:
    store = build_world()
    agent = Agent(brain=MockBrain(), store=store, clock=lambda: NOW)
    original = agent.handle(make_ticket("Please refund invoice in_ada1."))
    changed = agent.handle(make_ticket("Please cancel my subscription."))
    assert changed.outcome is Outcome.ESCALATED
    assert changed.gate_code == "request_id_conflict"
    assert changed.receipt is None
    assert store.get_subscription("sub_ada").status is SubscriptionStatus.ACTIVE
    assert agent.handle(make_ticket("Please refund invoice in_ada1.")) == original


@pytest.mark.parametrize(("invoice", "amount"), [("in_ada2", 100), ("in_ada1", 200)])
def test_store_refuses_reused_key_with_different_refund_payload(invoice: str, amount: int) -> None:
    store = build_world()
    store.issue_refund("in_ada1", 100, idempotency_key="same")
    with pytest.raises(BillingError, match="idempotency"):
        store.issue_refund(invoice, amount, idempotency_key="same")
    assert store.get_invoice("in_ada1").refunded_cents == 100
    assert store.get_invoice("in_ada2").refunded_cents == 0


def test_store_refuses_reused_cancel_key_with_different_subscription() -> None:
    store = build_world()
    store.cancel_subscription("sub_ada", idempotency_key="same")
    with pytest.raises(BillingError, match="idempotency"):
        store.cancel_subscription("sub_erin", idempotency_key="same")
    assert store.get_subscription("sub_erin").is_active


@pytest.mark.parametrize("operation", ["refund", "cancel"])
def test_executor_never_exports_a_mismatched_store_receipt(operation: str) -> None:
    class MismatchedStore(InMemoryBillingStore):
        def issue_refund(
            self, invoice_id: str, amount_cents: int, *, idempotency_key: str
        ) -> RefundReceipt:
            return RefundReceipt(
                invoice_id="in_foreign",
                amount_cents=amount_cents,
                idempotency_key=idempotency_key,
                refunded_total_cents=amount_cents,
            )

        def cancel_subscription(
            self, subscription_id: str, *, idempotency_key: str
        ) -> CancelReceipt:
            return CancelReceipt(
                subscription_id="sub_foreign",
                idempotency_key=idempotency_key,
                status=SubscriptionStatus.CANCELED,
            )

    store = MismatchedStore()
    seed = build_world()
    store.add_customer(seed.get_customer("cus_ada"))
    store.add_invoice(seed.get_invoice("in_ada1"))
    store.add_subscription(seed.get_subscription("sub_ada"))
    result = Agent(brain=MockBrain(), store=store, clock=lambda: NOW).handle(
        make_ticket(
            "Please refund invoice in_ada1."
            if operation == "refund"
            else "Please cancel my subscription."
        )
    )
    assert result.outcome is Outcome.ESCALATED
    assert result.gate_code == "store_rejected"
    assert result.receipt is None
    assert "foreign" not in result.model_dump_json()
