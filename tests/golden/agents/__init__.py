"""Offline agent fixtures for export→pytest integration tests.

These agents use a deterministic fake LLM and are designed to demonstrate
scenarios where frozen-replay-based pytest exports diverge when the fix
changes instrumented call inputs or order. They require no API keys or network.
"""

from .crash_agent import run_agent as crash_run_agent
from .crash_agent import run_agent_fixed as crash_run_agent_fixed
from .fake_llm import FakeLLM
from .triage_agent import run_agent as triage_run_agent
from .triage_agent import run_agent_fixed as triage_run_agent_fixed

__all__ = [
    "FakeLLM",
    "crash_run_agent",
    "crash_run_agent_fixed",
    "triage_run_agent",
    "triage_run_agent_fixed",
]
