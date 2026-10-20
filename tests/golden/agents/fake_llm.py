"""Deterministic offline stub LLM for agent fixtures.

No network, no API keys required. Returns predefined responses based on
message content patterns.
"""

from __future__ import annotations

import json
from typing import Any


class FakeLLM:
    """Stateful fake LLM that returns deterministic responses."""

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        """Return a deterministic response based on message content."""
        self.calls += 1
        last = messages[-1]["content"]

        if last.startswith("TICKET:"):
            return {
                "role": "assistant",
                "tool_call": {
                    "name": "lookup_customer",
                    "args": {"email": "ana@example.com"},
                },
            }

        if last.startswith("CUSTOMER:"):
            cust = json.loads(last[len("CUSTOMER:") :])
            priority = "high" if cust.get("plan") == "enterprise" else "normal"
            return {
                "role": "assistant",
                "content": json.dumps({"priority": priority, "refund_cents": 4999}),
            }

        return {"role": "assistant", "content": "{}"}
