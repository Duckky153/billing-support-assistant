"""Execution authorization is independent of the model, including the SDK path."""

from types import SimpleNamespace

import pytest
from billing_support.actions import AnswerAction, CancelAction, RefundAction
from billing_support.agent import Agent, Outcome
from billing_support.brain import ClaudeBrain, MockBrain
from billing_support.domain import Channel, SubscriptionStatus, Ticket
from billing_support.eval.golden import NOW, build_world
from billing_support.proposal import AgentProposal, Grounding, Intent


def ticket(body: str) -> Ticket:
    return Ticket(
        id="authorization",
        customer_id="cus_ada",
        subject="Help",
        body=body,
        channel=Channel.API,
        created_at=NOW,
    )


@pytest.mark.parametrize(
    "body",
    [
        "Do not cancel my subscription. When does it renew?",
        "How do I cancel my subscription?",
        "What is the refund policy?",
        "I might cancel my subscription.",
        "Please help.",
        "Don't refund me.",
        "Cancel my subscription if the refund goes through.",
        "Please refund me and cancel my subscription.",
        "My friend said: please cancel my subscription.",
    ],
)
@pytest.mark.parametrize("kind", ["refund", "cancel"])
def test_unrequested_model_mutation_never_executes(body: str, kind: str) -> None:
    action = (
        RefundAction(invoice_id="in_ada1", amount_cents=2000, reason="model guess")
        if kind == "refund"
        else CancelAction(subscription_id="sub_ada", reason="model guess")
    )
    proposal = AgentProposal(
        intent=Intent.REFUND_REQUEST if kind == "refund" else Intent.CANCELLATION,
        action=action,
        confidence=0.99,
        sensitive_topic=False,
        grounding=Grounding(
            customer_id="cus_ada",
            cited_invoice_ids=["in_ada1"],
            cited_subscription_ids=["sub_ada"],
            evidence="records exist",
        ),
        customer_reply="Done.",
        rationale="model guess",
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(parse=lambda **kwargs: SimpleNamespace(parsed_output=proposal))
    )
    store = build_world()
    result = Agent(brain=ClaudeBrain(client=client), store=store, clock=lambda: NOW).handle(
        ticket(body)
    )
    assert result.outcome is Outcome.ESCALATED
    assert result.gate_code == "mutation_not_authorized"
    assert result.receipt is None
    assert store.get_invoice("in_ada1").refunded_cents == 0
    assert store.get_subscription("sub_ada").status is SubscriptionStatus.ACTIVE


@pytest.mark.parametrize(
    "body",
    [
        "How do I cancel my subscription?",
        "What is the refund policy?",
        "Do not cancel my subscription. When does it renew?",
        "Can someone look into my account?",
        "I was charged twice.",
        "refund",
        "Please refund.",
        "What is the balance on invoice in_dave1?",
    ],
)
def test_unsupported_demo_questions_are_handed_off(body: str) -> None:
    result = Agent(brain=MockBrain(), store=build_world(), clock=lambda: NOW).handle(ticket(body))
    assert result.outcome is Outcome.ESCALATED
    assert not result.executed
    assert result.case_file is not None


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("When does my plan renew?", "2025-02-11"),
        ("When does my subscription renew, and what will I be charged?", "$20.00"),
        ("What was the total amount on my latest invoice?", "$20.00"),
        ("What is the amount of my latest invoice?", "$20.00"),
        ("Do I currently have an active subscription?", "active"),
    ],
)
def test_supported_questions_answer_the_actual_question(body: str, expected: str) -> None:
    result = Agent(brain=MockBrain(), store=build_world(), clock=lambda: NOW).handle(ticket(body))
    assert result.outcome is Outcome.RESOLVED
    assert expected in result.customer_reply
    assert not result.executed


def test_explicit_partial_amount_is_not_silently_refunded_in_full() -> None:
    store = build_world()
    result = Agent(brain=MockBrain(), store=store, clock=lambda: NOW).handle(
        ticket("Please refund $5.00 on invoice in_ada1.")
    )
    assert result.outcome is Outcome.RESOLVED
    assert result.receipt["amount_cents"] == "500"
    assert store.get_invoice("in_ada1").refunded_cents == 500


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (
            "Hi — please refund my recent $20.00 charge on invoice in_ada1 (2000 cents). "
            "It was paid a few days ago and I'd like it reversed. Thank you!",
            "agent_escalated",
        ),
        ("Please refund my recent $5.00 charge on invoice in_ada1 (500 cents).", "refund_ok"),
        (
            "Please refund my recent $5.00 charge on invoice in_ada1 (2000 cents).",
            "agent_escalated",
        ),
        (
            "Could you please refund invoice in_ada2? "
            "It was a charge from a little while back that I'd like reversed.",
            "agent_escalated",
        ),
    ],
)
def test_explicit_supported_amount_and_window_requests(body: str, code: str) -> None:
    result = Agent(brain=MockBrain(), store=build_world(), clock=lambda: NOW).handle(ticket(body))
    assert result.gate_code == code


def test_arbitrary_model_answer_text_is_not_semantically_verified() -> None:
    """Known limitation: citation ownership is not validation of the reply's facts."""
    proposal = AgentProposal(
        intent=Intent.ACCOUNT_QUESTION,
        action=AnswerAction(),
        confidence=0.99,
        sensitive_topic=False,
        grounding=Grounding(
            customer_id="cus_ada",
            cited_subscription_ids=["sub_ada"],
            evidence="subscription exists",
        ),
        customer_reply="Your next charge is $999.00.",
        rationale="wrong model answer",
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(parse=lambda **kwargs: SimpleNamespace(parsed_output=proposal))
    )
    store = build_world()
    result = Agent(brain=ClaudeBrain(client=client), store=store, clock=lambda: NOW).handle(
        ticket("When does my plan renew?")
    )
    assert result.outcome is Outcome.RESOLVED
    assert result.customer_reply == "Your next charge is $999.00."
    assert not result.executed
    assert store.get_subscription("sub_ada").amount_cents == 2000
