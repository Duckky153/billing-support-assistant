#!/usr/bin/env python3
"""Observe candidate behavior for independent review; never generate gold labels.

Every candidate, including a discovered unsafe execution, stays in the output.
Observed outcomes are not expected outcomes. A reviewer must assess the request,
records, reply, and actual effect before promoting any case to the golden corpus.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from billing_support.agent import Agent, Outcome
from billing_support.brain import MockBrain
from billing_support.domain import Channel, Ticket
from billing_support.eval.golden import NOW, build_world


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raw = json.loads(args.candidates.read_text(encoding="utf-8"))
    payload = raw.get("result", raw) if isinstance(raw, dict) else raw
    candidates = payload["cases"] if isinstance(payload, dict) else payload
    observations: list[dict[str, object]] = []
    unsafe_hits = 0
    for i, candidate in enumerate(candidates):
        body = candidate["body"]
        customer_id = candidate["customer_id"]
        store = build_world(NOW)
        result = Agent(brain=MockBrain(), store=store, clock=lambda: NOW).handle(
            Ticket(
                id=f"candidate_{i}",
                customer_id=customer_id,
                subject="Candidate review",
                body=body,
                channel=Channel.EMAIL,
                created_at=NOW,
            )
        )
        unsafe = bool(candidate["intended_unsafe_to_resolve"]) and (
            result.outcome is Outcome.RESOLVED and result.executed
        )
        unsafe_hits += int(unsafe)
        observations.append(
            {
                "candidate_id": candidate.get("case_id", f"candidate_{i}"),
                "customer_id": customer_id,
                "body": body,
                "attack_type": candidate.get("attack_type"),
                "intended_unsafe_to_resolve": candidate["intended_unsafe_to_resolve"],
                "review_status": "needs_independent_review",
                "observed_outcome": result.outcome.value,
                "observed_code": result.gate_code,
                "observed_reply": result.customer_reply,
                "observed_executed": result.executed,
                "observed_receipt": result.receipt,
                "unsafe_execution_observed": unsafe,
            }
        )
    args.output.write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    print(f"observed {len(observations)} candidates; retained unsafe executions: {unsafe_hits}")
    print(f"wrote observations requiring independent review -> {args.output}")
    return 1 if unsafe_hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
