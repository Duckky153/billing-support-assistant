"""Local FastAPI sample-data harness.

POST /tickets returns a decision, customer-reply draft, and optional CaseFile.
The endpoint trusts customer_id and does not authenticate callers. It must not be
exposed as a production service without authenticated identity and operational
controls. See docs/THREAT-MODEL.md. No messages or real billing calls are sent by
the default in-memory app.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from billing_support.agent import Agent, TicketResolution
from billing_support.brain import MockBrain
from billing_support.domain import Channel, Ticket
from billing_support.eval.golden import NOW, build_world

_LANDING_HTML = """\
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Billing Support Assistant — local support workflow</title>
<style>
  body{margin:0;background:#0f1419;color:#e6edf3;
       font:16px/1.6 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  .wrap{max-width:760px;margin:0 auto;padding:48px 24px}
  h1{font-size:26px;margin:0 0 4px}.sub{color:#8b97a6;margin:0 0 28px}
  .card{background:#171c24;border:1px solid #232a35;border-radius:12px;padding:20px;margin:14px 0}
  code{background:#0b0e12;padding:2px 7px;border-radius:6px;font-size:13px;color:#e6edf3}
  pre{background:#0b0e12;border:1px solid #232a35;border-radius:8px;
      padding:14px;overflow:auto;font-size:13px}
  a{color:#2f81f7;text-decoration:none}a:hover{text-decoration:underline}
  .good{color:#2ea043;font-weight:600}
</style></head><body><div class="wrap">
  <h1>Billing Support Assistant</h1>
  <p class="sub">A local sample-data harness for gated support decisions.
  The model <em>proposes</em>; record checks and a bounded request grammar decide
  whether a sample refund or cancellation is allowed. The fixed offline evaluation
  is regression evidence, not a general safety or answer-accuracy guarantee.</p>
  <div class="card"><strong>Local demo only.</strong> This endpoint does not authenticate
  callers. It trusts the supplied customer ID. Do not expose it as a production
  service. Sample records change in memory; no real billing or messages are sent.</div>
  <div class="card">
    <strong>Try it — point & click:</strong> open the interactive API docs at
    <a href="/docs">/docs</a> and run <code>POST /tickets</code> in the browser.
  </div>
  <div class="card">
    <strong>Or curl it.</strong> With <code>billing-support serve</code> on its default local port,
    a supported refund resolves; a request naming
    another customer's invoice requires review:
<pre># resolves (Ada's own recent invoice, within policy):
curl -s http://127.0.0.1:8000/tickets -H 'content-type: application/json' \\
  -d '{"customer_id":"cus_ada","body":"Please refund invoice in_ada1."}'

# escalates (the target is not in Ada's sample records):
curl -s http://127.0.0.1:8000/tickets -H 'content-type: application/json' \\
  -d '{"customer_id":"cus_ada","body":"Please refund invoice in_bob1."}'</pre>
    Demo customers: <code>cus_ada</code> <code>cus_bob</code> <code>cus_carol</code>
    <code>cus_dave</code> <code>cus_erin</code>.
  </div>
  <p class="sub">Eval scoreboard: <a href="https://duckky153.github.io/billing-support-assistant/">duckky153.github.io/billing-support-assistant</a>
  · Source: <a href="https://github.com/Duckky153/billing-support-assistant">github.com/Duckky153/billing-support-assistant</a>
  · Health: <a href="/healthz">/healthz</a></p>
</div></body></html>"""


class TicketRequest(BaseModel):
    customer_id: str
    body: str
    subject: str = "support"
    ticket_id: str | None = None


def create_app(agent: Agent | None = None) -> FastAPI:
    app = FastAPI(
        title="Billing Support Assistant",
        version="0.1.0",
        description="Local sample-data support workflow; no caller authentication or live billing.",
    )
    app.state.agent = agent or Agent(brain=MockBrain(), store=build_world(NOW), clock=lambda: NOW)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        # A bare GET / from a recruiter must explain the service and link to the
        # interactive /docs demo — never a raw {"detail":"Not Found"}.
        return _LANDING_HTML

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "billing-support"}

    @app.post("/tickets")
    def handle_ticket(req: TicketRequest) -> TicketResolution:
        # NOTE: `req.customer_id` is trusted as a pre-authenticated identity here
        # (demo). In production an auth dependency must resolve the verified
        # subject and override any client-supplied customer_id. See module docs.
        ticket = Ticket(
            id=req.ticket_id or f"tkt_{uuid.uuid4().hex}",
            customer_id=req.customer_id,
            subject=req.subject,
            body=req.body,
            channel=Channel.API,
            created_at=dt.datetime.now(dt.UTC),
        )
        agent: Agent = app.state.agent
        return agent.handle(ticket)

    return app
