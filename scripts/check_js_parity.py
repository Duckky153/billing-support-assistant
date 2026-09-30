#!/usr/bin/env python3
"""Prove the in-browser demo (dashboard/billing-support-demo.js) matches the real Python.

Runs every golden case through BOTH the real Python agent and the JavaScript
port (via node), and asserts the outcome + controlling gate code are identical.
If they ever diverge, the browser demo is lying and this fails. Run in CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from billing_support.agent import Agent
from billing_support.brain import MockBrain
from billing_support.domain import Channel, Ticket
from billing_support.eval.golden import NOW, build_world, load_golden

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "dashboard" / "billing-support-demo.js"

NODE_RUNNER = f"""
const {{ billingSupportDecide }} = require({json.dumps(str(JS))});
const inputs = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = inputs.map(function (x) {{
  const r = billingSupportDecide(x[0], x[1]);
  return {{ outcome: r.outcome, gate_code: r.gate_code, executed: r.executed,
    customer_reply: r.customer_reply, handoff: !!r.case_file }};
}});
process.stdout.write(JSON.stringify(out));
"""


def python_result(cid: str, body: str) -> dict:
    agent = Agent(brain=MockBrain(), store=build_world(NOW), clock=lambda: NOW)
    res = agent.handle(
        Ticket(
            id="t", customer_id=cid, subject="x", body=body, channel=Channel.EMAIL, created_at=NOW
        )
    )
    return {
        "outcome": res.outcome.value,
        "gate_code": res.gate_code,
        "executed": res.executed,
        "customer_reply": res.customer_reply,
        "handoff": res.case_file is not None,
    }


def main() -> int:
    cases = load_golden()
    inputs = [[c.customer_id, c.body] for c in cases]
    regressions = [
        "Do not cancel my subscription. When does it renew?",
        "How do I cancel my subscription?",
        "What is the refund policy?",
        "I might cancel my subscription.",
        "Please help.",
        "Don't refund me.",
        "Cancel my subscription if the refund goes through.",
        "Please refund me and cancel my subscription.",
        "My friend said: please cancel my subscription.",
        "What was the total amount on my latest invoice?",
        "What is the amount of my latest invoice?",
        "Please refund $5.00 on invoice in_ada1.",
        "Please refund my recent $5.00 charge on invoice in_ada1 (2000 cents).",
        "Please refund invoice in_bob1.",
        "Please cancel subscription sub_bob.",
    ]
    inputs += [["cus_ada", body] for body in regressions]

    proc = subprocess.run(
        ["node", "-e", NODE_RUNNER],
        input=json.dumps(inputs),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print("node failed:", proc.stderr, file=sys.stderr)
        return 2
    js_results = json.loads(proc.stdout)

    mismatches = 0
    for (cid, body), js in zip(inputs, js_results, strict=True):
        py = python_result(cid, body)
        if py != js:
            mismatches += 1
            print(f"MISMATCH {cid}: {body[:90]}\n  python={py}\n  js    ={js}")
    print(
        f"\nchecked {len(cases)} golden + {len(regressions)} regression cases "
        f"· mismatches: {mismatches}"
    )
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
