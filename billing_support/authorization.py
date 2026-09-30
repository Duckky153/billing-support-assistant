"""A deliberately small request grammar, not general natural-language consent.

Only whole supported requests authorize a mutation. Unknown wording, quoted
instructions, conditions, multiple actions, and informational questions fall
through to human review. Both brains pass through this independent boundary.
Production needs authenticated, structured confirmation and durable replay state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from billing_support.actions import CancelAction, RefundAction
from billing_support.domain import Invoice, InvoiceStatus, Subscription


def normalize(body: str) -> str:
    return re.sub(r"\s+", " ", body.lower().replace("\u2019", "'")).strip()


def request_text(body: str) -> str:
    text = normalize(body)
    text = re.sub(r"^(?:hi|hey)[, —-]+", "", text).strip()
    text = re.sub(r"[.!?]*\s*(?:thank you|thanks)[.!]*$", "", text).strip()
    text = re.sub(
        r"^(?:(?:i think i was|i was|i think i got|i got) )?(?:charged|billed) twice"
        r"(?: this week)?(?:[.,] | and )",
        "",
        text,
    )
    text = re.sub(r"^i was double charged, ", "", text)
    text = re.sub(r", i don't need it anymore[.!]*$", "", text)
    return text.rstrip(".!?").strip()


@dataclass(frozen=True)
class MutationRequest:
    kind: str
    target_id: str | None = None
    amount_cents: int | None = None


def mutation_request(body: str) -> MutationRequest | None:
    text = request_text(body)
    cancel = re.fullmatch(
        r"(?:please |can you (?:please )?|could you (?:please )?)?cancel "
        r"(?:my (?:subscription|plan)|(?:subscription )?(sub_[a-z0-9_]+))"
        r"(?: effective today| immediately| now)?(?: please)?",
        text,
    )
    if cancel:
        return MutationRequest("cancel_subscription", cancel.group(1))
    refund = re.fullmatch(
        r"(?:please |can you (?:please )?|could you (?:please )?)?refund"
        r"(?: me| the full amount| my (?:double charge|recent charge|recent payment)|"
        r" (?:invoice )?(in_[a-z0-9_]+)|"
        r" \$(\d+(?:\.\d{1,2})?) on invoice (in_[a-z0-9_]+))"
        r"(?: please)?",
        text,
    )
    if refund:
        amount = int(Decimal(refund.group(2)) * 100) if refund.group(2) else None
        return MutationRequest("refund", refund.group(1) or refund.group(3), amount)
    detailed_refund = re.fullmatch(
        r"(?:please )?refund my recent \$(\d+(?:\.\d{1,2})?) charge on invoice "
        r"(in_[a-z0-9_]+) \((\d+) cents\)",
        text,
    )
    if detailed_refund:
        amount = int(Decimal(detailed_refund.group(1)) * 100)
        if amount == int(detailed_refund.group(3)):
            return MutationRequest("refund", detailed_refund.group(2), amount)
    if re.fullmatch(r"(?:i )?(?:would like|want) my money back(?: for the extra charge)?", text):
        return MutationRequest("refund")
    return None


def authorizes(
    body: str,
    action: RefundAction | CancelAction,
    invoices: list[Invoice],
    subscriptions: list[Subscription],
) -> bool:
    request = mutation_request(body)
    if request is None or request.kind != action.type:
        return False
    if isinstance(action, RefundAction):
        candidates = [
            i
            for i in invoices
            if i.status is InvoiceStatus.PAID and i.refundable_remaining_cents > 0
        ]
        target = request.target_id
        if target is None and candidates:
            target = max(candidates, key=lambda i: (i.created_at, i.id)).id
        invoice = next((i for i in invoices if i.id == target), None)
        # An unqualified refund means the remaining amount on the latest paid
        # invoice in this sample workflow; partial refunds must name the amount.
        amount = request.amount_cents
        if amount is None and invoice is not None:
            amount = invoice.refundable_remaining_cents
        return action.invoice_id == target and action.amount_cents == amount
    active = [s for s in subscriptions if s.is_active]
    target = request.target_id
    if target is None and len(active) == 1:
        target = active[0].id
    return action.subscription_id == target
