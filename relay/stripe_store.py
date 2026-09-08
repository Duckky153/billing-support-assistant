"""A Stripe-backed billing store.

`StripeBillingStore` implements the same :class:`~relay.store.BillingStore`
protocol as the in-memory store, so the orchestrator and both gates are
unchanged when Relay is pointed at a real Stripe account. The mapping functions
(`to_customer` / `to_invoice` / `to_subscription`) are pure and unit-tested; the
store methods call an injected Stripe-like client (the real ``stripe`` module, or
a fake in tests).

Scope note: this is a reference adapter against Stripe's object shapes. A refund
targets an invoice's underlying charge and carries an idempotency key. A
production deployment should reconcile refund totals at the charge level rather
than trusting a single ``amount_refunded`` field — see docs/HONESTY.md.
"""

from __future__ import annotations

import datetime as dt
import threading
from typing import Any

from relay.domain import Customer, Invoice, InvoiceStatus, Subscription, SubscriptionStatus
from relay.store import BillingError, CancelReceipt, RefundReceipt

_INVOICE_STATUS = {
    "paid": InvoiceStatus.PAID,
    "open": InvoiceStatus.OPEN,
    "draft": InvoiceStatus.OPEN,
    "void": InvoiceStatus.UNCOLLECTIBLE,
    "uncollectible": InvoiceStatus.UNCOLLECTIBLE,
}
_SUB_STATUS = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.TRIALING,
    "past_due": SubscriptionStatus.PAST_DUE,
    "canceled": SubscriptionStatus.CANCELED,
    "unpaid": SubscriptionStatus.PAST_DUE,
}


def _ts(unix: int) -> dt.datetime:
    return dt.datetime.fromtimestamp(unix, dt.UTC)


def to_customer(obj: dict[str, Any]) -> Customer:
    return Customer(
        id=obj["id"],
        email=obj.get("email") or "",
        name=obj.get("name") or "",
        created_at=_ts(obj["created"]),
    )


def to_invoice(obj: dict[str, Any]) -> Invoice:
    return Invoice(
        id=obj["id"],
        customer_id=obj["customer"],
        subscription_id=obj.get("subscription"),
        amount_cents=int(obj["amount_due"]),
        currency=obj.get("currency", "usd"),
        status=_INVOICE_STATUS.get(obj["status"], InvoiceStatus.UNCOLLECTIBLE),
        created_at=_ts(obj["created"]),
        refunded_cents=int(obj.get("amount_refunded", 0)),
    )


def to_subscription(obj: dict[str, Any]) -> Subscription:
    return Subscription(
        id=obj["id"],
        customer_id=obj["customer"],
        plan=obj.get("plan", "unknown"),
        status=_SUB_STATUS.get(obj["status"], SubscriptionStatus.CANCELED),
        amount_cents=int(obj.get("amount_cents", 0)),
        currency=obj.get("currency", "usd"),
        current_period_end=_ts(obj["current_period_end"]),
    )


class StripeBillingStore:
    """BillingStore backed by a Stripe-like client (dependency-injected)."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self._write_lock = threading.Lock()
        self._refund_payloads: dict[str, tuple[str, int]] = {}
        self._cancel_payloads: dict[str, str] = {}
        self._refunds: dict[str, RefundReceipt] = {}
        self._cancels: dict[str, CancelReceipt] = {}
        self._known_refunded: dict[str, int] = {}

    def get_customer(self, customer_id: str) -> Customer | None:
        raw = self._retrieve(self.client.Customer, customer_id)
        return to_customer(raw) if raw is not None else None

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        raw = self._retrieve(self.client.Subscription, subscription_id)
        return to_subscription(raw) if raw is not None else None

    def get_subscriptions(self, customer_id: str) -> list[Subscription]:
        data = self.client.Subscription.list(customer=customer_id)["data"]
        return [to_subscription(s) for s in data]

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        raw = self._retrieve(self.client.Invoice, invoice_id)
        return to_invoice(raw) if raw is not None else None

    def get_invoices(self, customer_id: str) -> list[Invoice]:
        data = self.client.Invoice.list(customer=customer_id)["data"]
        return [to_invoice(i) for i in data]

    def issue_refund(
        self, invoice_id: str, amount_cents: int, *, idempotency_key: str
    ) -> RefundReceipt:
        with self._write_lock:
            payload = (invoice_id, amount_cents)
            if idempotency_key in self._refund_payloads:
                if self._refund_payloads[idempotency_key] != payload:
                    raise BillingError("idempotency key conflicts with earlier refund payload")
                if idempotency_key not in self._refunds:
                    raise BillingError(
                        "prior refund outcome uncertain; verify downstream before retrying"
                    )
                return self._refunds[idempotency_key]
            self._refund_payloads[idempotency_key] = payload
            try:
                receipt = self._issue_refund(invoice_id, amount_cents, idempotency_key)
            except BillingError:
                raise
            except Exception as exc:
                raise BillingError(
                    "refund outcome uncertain; verify downstream before retrying"
                ) from exc
            self._refunds[idempotency_key] = receipt
            return receipt

    def _issue_refund(
        self, invoice_id: str, amount_cents: int, idempotency_key: str
    ) -> RefundReceipt:
        if amount_cents <= 0:
            raise BillingError("refund amount must be positive")
        raw = self._retrieve(self.client.Invoice, invoice_id)
        if raw is None:
            raise BillingError(f"unknown invoice {invoice_id!r}")
        if raw.get("id") != invoice_id:
            raise BillingError("invoice identity mismatch; verify downstream before retrying")
        already_refunded = max(
            int(raw.get("amount_refunded", 0)), self._known_refunded.get(invoice_id, 0)
        )
        if raw.get("status") != "paid" or amount_cents > int(raw["amount_due"]) - already_refunded:
            raise BillingError("invoice is unpaid or refund exceeds known remaining balance")
        charge = raw.get("charge")
        if not charge:
            raise BillingError(f"invoice {invoice_id!r} has no charge to refund")
        response = self.client.Refund.create(
            charge=charge, amount=amount_cents, idempotency_key=idempotency_key
        )
        if (
            response.get("charge") != charge
            or response.get("amount") != amount_cents
            or response.get("status") != "succeeded"
            or not response.get("id")
        ):
            raise BillingError(
                "refund receipt mismatch or incomplete; verify downstream before retrying"
            )
        self._known_refunded[invoice_id] = already_refunded + amount_cents
        return RefundReceipt(
            invoice_id=invoice_id,
            amount_cents=amount_cents,
            idempotency_key=idempotency_key,
            refunded_total_cents=already_refunded + amount_cents,
        )

    def cancel_subscription(self, subscription_id: str, *, idempotency_key: str) -> CancelReceipt:
        # Stripe DELETE does not use its POST idempotency mechanism. This local
        # registry binds our caller's key; it is not durable across restarts.
        with self._write_lock:
            if idempotency_key in self._cancel_payloads:
                if self._cancel_payloads[idempotency_key] != subscription_id:
                    raise BillingError(
                        "idempotency key conflicts with earlier cancellation payload"
                    )
                if idempotency_key not in self._cancels:
                    raise BillingError(
                        "prior cancellation outcome uncertain; verify downstream before retrying"
                    )
                return self._cancels[idempotency_key]
            self._cancel_payloads[idempotency_key] = subscription_id
            try:
                response = self.client.Subscription.delete(subscription_id)
                if response.get("id") != subscription_id or response.get("status") != "canceled":
                    raise BillingError(
                        "cancellation receipt mismatch; verify downstream before retrying"
                    )
            except BillingError:
                raise
            except Exception as exc:
                raise BillingError(
                    "cancellation outcome uncertain; verify downstream before retrying"
                ) from exc
            receipt = CancelReceipt(
                subscription_id=subscription_id,
                idempotency_key=idempotency_key,
                status=SubscriptionStatus.CANCELED,
            )
            self._cancels[idempotency_key] = receipt
            return receipt

    @staticmethod
    def _retrieve(resource: Any, oid: str) -> dict[str, Any] | None:
        try:
            return resource.retrieve(oid)  # type: ignore[no-any-return]
        except (KeyError, LookupError):
            return None
