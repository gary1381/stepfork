"""Support-triage agent demonstrating changed-arguments divergence.

This agent processes support tickets: it looks up customer info, gets an LLM
decision, then issues a refund. The buggy version divides cents by 100 before
refunding, so it refunds 49 cents instead of 4999.

The bug changes the **argument** of the `issue_refund` tool call. This means:
- Recording the buggy run captures `issue_refund(amount_cents=49)`
- The fixed code calls `issue_refund(amount_cents=4999)`
- Frozen replay diverges at the tool call inputs (ReplayMismatchError)
- A failure-trace export can never go green against the fixed code

This demonstrates Finding #1 from the stepfork test report: frozen-replay
export works when the fix leaves instrumented call inputs unchanged, but
not when the fix changes what arguments are passed to a later tool.
"""

from __future__ import annotations

import json
from typing import Any

from stepfork import llm_request, trace_tool

from .fake_llm import FakeLLM

_llm = FakeLLM()

DEFAULT_TICKET = "Charged twice for March, please refund $49.99"


@trace_tool(name="lookup_customer")
def lookup_customer(email: str) -> dict[str, Any]:
    """Look up customer by email. Returns plan and refund limit."""
    return {"email": email, "plan": "enterprise", "refund_limit_cents": 10000}


@trace_tool(name="issue_refund")
def issue_refund(email: str, amount_cents: int) -> dict[str, Any]:
    """Issue a refund to the customer."""
    return {"ok": True, "email": email, "amount_cents": amount_cents}


def _ask(messages: list[dict[str, str]]) -> dict[str, Any]:
    result: dict[str, Any] = llm_request(
        provider="fake",
        model="stub-1",
        input={"messages": messages},
        call=lambda: _llm.chat(messages),
    )
    return result


def _run(ticket: str, buggy: bool) -> dict[str, Any]:
    msgs: list[dict[str, str]] = [{"role": "user", "content": f"TICKET:{ticket}"}]
    r1 = _ask(msgs)
    call = r1["tool_call"]
    cust = lookup_customer(**call["args"])

    msgs.append({"role": "user", "content": "CUSTOMER:" + json.dumps(cust)})
    r2 = _ask(msgs)
    decision = json.loads(r2["content"])

    amount = decision["refund_cents"]
    if buggy:
        amount = amount // 100  # BUG: treats cents as dollars → refunds 49 cents

    refunded = None
    if amount <= cust["refund_limit_cents"]:
        refunded = issue_refund(cust["email"], amount)["amount_cents"]

    return {"priority": decision["priority"], "refunded_cents": refunded}


def run_agent(ticket: str = DEFAULT_TICKET) -> dict[str, Any]:
    """Buggy implementation: divides cents by 100 before refunding."""
    return _run(ticket, buggy=True)


def run_agent_fixed(ticket: str = DEFAULT_TICKET) -> dict[str, Any]:
    """Corrected implementation: uses the correct amount."""
    return _run(ticket, buggy=False)


EXPECTED_OUTPUT: dict[str, Any] = {"priority": "high", "refunded_cents": 4999}
