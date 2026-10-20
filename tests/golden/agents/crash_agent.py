"""Crash agent demonstrating extra-calls divergence.

This agent processes angry customer messages: it parses an LLM response
(wrapped in a markdown fence) and escalates the ticket. The buggy version
crashes on JSON parsing because it doesn't strip the fence.

The bug causes the agent to crash **before** calling the `escalate` tool:
- Recording the buggy run captures only the LLM call (no escalate)
- The fixed code successfully calls `escalate`
- Frozen replay fails with ReplayExhaustedError (unexpected tool call)
- A failure-trace export can never go green against the fixed code

This demonstrates Finding #1 from the stepfork test report: frozen-replay
export works when the fix leaves instrumented call inputs and order unchanged,
but not when the fix enables a tool call that the buggy run never reached.

Also tests redaction: the fake LLM output contains a synthetic secret pattern
(`sk-proj-...`) to verify that stepfork redacts it in the trace.
"""

from __future__ import annotations

import json
from typing import Any

from stepfork import llm_request, trace_tool


def _fake_chat(messages: list[dict[str, str]]) -> dict[str, Any]:
    """Return a markdown-fenced JSON response with a synthetic secret."""
    del messages  # unused
    return {
        "content": (
            "```json\n"
            '{"action": "escalate", '
            '"secret_seen": "sk-proj-ABCDEF1234567890abcdef1234567890"}'
            "\n```"
        )
    }


@trace_tool(name="escalate")
def escalate(reason: str) -> dict[str, Any]:
    """Escalate a ticket. Returns the escalation ticket ID."""
    return {
        "ticket": "ESC-1",
        "reason": reason,
        "api_key": "sk-proj-ZYXW9876543210zyxw9876543210ab",
    }


def _decide(strip_fence: bool) -> dict[str, Any]:
    msgs: list[dict[str, str]] = [{"role": "user", "content": "Customer is angry"}]
    r = llm_request(
        provider="fake",
        model="stub-1",
        input={"messages": msgs},
        call=lambda: _fake_chat(msgs),
    )
    text = r["content"]

    if strip_fence:
        text = text.strip().removeprefix("```json").removesuffix("```").strip()

    data = json.loads(text)  # buggy version raises JSONDecodeError
    res = escalate(data["action"])
    return {"action": data["action"], "ticket": res["ticket"]}


def run_agent() -> dict[str, Any]:
    """Buggy implementation: crashes on markdown-fenced JSON."""
    return _decide(strip_fence=False)


def run_agent_fixed() -> dict[str, Any]:
    """Corrected implementation: strips the markdown fence before parsing."""
    return _decide(strip_fence=True)


EXPECTED_OUTPUT: dict[str, Any] = {"action": "escalate", "ticket": "ESC-1"}
