"""End-to-end tests for export→pytest with agent fixtures.

These tests exercise the frozen-replay-based pytest export behavior when
the fix changes instrumented call inputs or order. They demonstrate the
documented limitation: failure-trace exports diverge when the fix changes
what happens in subsequent tool calls.

Test scenarios from the stepfork test report Finding #1:
1. triage_agent: fix changes tool arguments → ReplayMismatchError
2. crash_agent: fix enables tool call not in recording → ReplayExhaustedError

Both agents use a deterministic offline fake LLM (no API keys, no network).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from stepfork import record
from stepfork.export import export_pytest_test
from stepfork.inspect import inspect_bundle
from stepfork.replay import ReplayExhaustedError, ReplayMismatchError, ReplaySession
from stepfork.trace import RunStatus, Trace, validate_bundle

REPO_ROOT = Path(__file__).resolve().parents[2]


def _triage_agent() -> Any:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tests.golden.agents import triage_agent

    return triage_agent


def _crash_agent() -> Any:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tests.golden.agents import crash_agent

    return crash_agent


def _run_pytest(test_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "-q",
            str(test_file),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class TestTriageAgentChangedArgs:
    """Tests for triage agent demonstrating changed-arguments divergence."""

    def test_buggy_refunds_wrong_amount(self, tmp_path: Path) -> None:
        """The buggy agent refunds 49 cents instead of 4999."""
        agent = _triage_agent()
        result = agent.run_agent()

        assert result["refunded_cents"] == 49
        assert result["priority"] == "high"

    def test_fixed_refunds_correct_amount(self, tmp_path: Path) -> None:
        """The fixed agent refunds 4999 cents."""
        agent = _triage_agent()
        result = agent.run_agent_fixed()

        assert result["refunded_cents"] == 4999
        assert result["priority"] == "high"

    def test_recording_captures_buggy_tool_args(self, tmp_path: Path) -> None:
        """Recording the buggy run captures the wrong amount in tool call."""
        agent = _triage_agent()
        trace_path = tmp_path / "triage_failure.sftrace"

        with record("triage-agent", output=trace_path) as session:
            result = agent.run_agent()
            session.set_output(result)

        validation = validate_bundle(trace_path, strict=True, verify_integrity=True)
        assert validation.valid, validation.issues
        assert Trace.load(trace_path).status is RunStatus.COMPLETED

        inspection = inspect_bundle(trace_path)
        assert inspection.agent_name == "triage-agent"

    def test_frozen_replay_diverges_on_changed_args(self, tmp_path: Path) -> None:
        """Frozen replay of buggy trace diverges when run against fixed code.

        The fixed code calls issue_refund(amount_cents=4999) but the recording
        captured issue_refund(amount_cents=49). This causes ReplayMismatchError.
        """
        agent = _triage_agent()
        trace_path = tmp_path / "triage_failure.sftrace"

        with record("triage-agent", output=trace_path) as session:
            session.set_output(agent.run_agent())

        with (
            pytest.raises(ReplayMismatchError, match="input diverged"),
            ReplaySession.from_trace(trace_path, mode="frozen"),
        ):
            agent.run_agent_fixed()

    def test_exported_test_fails_on_buggy_code(self, tmp_path: Path) -> None:
        """Exported test correctly fails when run against buggy code."""
        agent = _triage_agent()
        trace_path = tmp_path / "triage_failure.sftrace"

        with record("triage-agent", output=trace_path) as session:
            session.set_output(agent.run_agent())

        expected = {"priority": "high", "refunded_cents": 4999}
        test_file = export_pytest_test(
            trace_path=trace_path,
            output_path=tmp_path / "test_triage_buggy.py",
            entrypoint="tests.golden.agents.triage_agent:run_agent",
            expectation=expected,
            has_expectation=True,
            import_root=REPO_ROOT,
        )

        proc = _run_pytest(test_file)

        assert proc.returncode != 0, proc.stdout
        assert "behavior mismatch" in proc.stdout
        assert "refunded_cents" in proc.stdout

    def test_failure_trace_export_cannot_pass_on_fix(self, tmp_path: Path) -> None:
        """A failure-trace export never goes green when fix changes tool args.

        This is the core demonstration: exporting from the buggy recording
        creates a test that diverges when run against the fixed code because
        the fixed code calls issue_refund with different arguments.
        """
        agent = _triage_agent()
        trace_path = tmp_path / "triage_failure.sftrace"

        with record("triage-agent", output=trace_path) as session:
            session.set_output(agent.run_agent())

        expected = {"priority": "high", "refunded_cents": 4999}
        test_file = export_pytest_test(
            trace_path=trace_path,
            output_path=tmp_path / "test_triage_fixed.py",
            entrypoint="tests.golden.agents.triage_agent:run_agent_fixed",
            expectation=expected,
            has_expectation=True,
            import_root=REPO_ROOT,
        )

        proc = _run_pytest(test_file)

        assert proc.returncode != 0, proc.stdout
        assert "diverged" in proc.stdout.lower() or "mismatch" in proc.stdout.lower()


class TestCrashAgentExtraCalls:
    """Tests for crash agent demonstrating extra-calls divergence."""

    def test_buggy_crashes_on_json_parse(self, tmp_path: Path) -> None:
        """The buggy agent crashes trying to parse markdown-fenced JSON."""
        agent = _crash_agent()

        with pytest.raises(json.JSONDecodeError):
            agent.run_agent()

    def test_fixed_parses_correctly(self, tmp_path: Path) -> None:
        """The fixed agent strips the fence and parses correctly."""
        agent = _crash_agent()
        result = agent.run_agent_fixed()

        assert result["action"] == "escalate"
        assert result["ticket"] == "ESC-1"

    def test_recording_captures_crash(self, tmp_path: Path) -> None:
        """Recording a crashed run still produces a valid trace bundle."""
        agent = _crash_agent()
        trace_path = tmp_path / "crash_failure.sftrace"

        with (
            pytest.raises(json.JSONDecodeError),
            record("crash-agent", output=trace_path),
        ):
            agent.run_agent()

        validation = validate_bundle(trace_path, strict=False, verify_integrity=True)
        assert validation.valid, validation.issues

        trace = Trace.load(trace_path)
        assert trace.status is RunStatus.FAILED

    def test_frozen_replay_diverges_on_extra_call(self, tmp_path: Path) -> None:
        """Frozen replay of crash trace diverges when fix enables a new tool call.

        The fixed code calls escalate() which isn't in the recording, so
        replay raises ReplayExhaustedError for the unexpected tool call.
        """
        agent = _crash_agent()
        trace_path = tmp_path / "crash_failure.sftrace"

        with (
            pytest.raises(json.JSONDecodeError),
            record("crash-agent", output=trace_path),
        ):
            agent.run_agent()

        with (
            pytest.raises(ReplayExhaustedError, match="unexpected tool call"),
            ReplaySession.from_trace(trace_path, mode="frozen"),
        ):
            agent.run_agent_fixed()

    def test_failure_trace_export_cannot_pass_on_fix(self, tmp_path: Path) -> None:
        """A failure-trace export never goes green when fix makes extra calls.

        Exporting from the crash recording creates a test that diverges when
        run against the fixed code because the fixed code calls escalate()
        which was never reached in the buggy run.
        """
        agent = _crash_agent()
        trace_path = tmp_path / "crash_failure.sftrace"

        with (
            pytest.raises(json.JSONDecodeError),
            record("crash-agent", output=trace_path),
        ):
            agent.run_agent()

        expected = {"action": "escalate", "ticket": "ESC-1"}
        test_file = export_pytest_test(
            trace_path=trace_path,
            output_path=tmp_path / "test_crash_fixed.py",
            entrypoint="tests.golden.agents.crash_agent:run_agent_fixed",
            expectation=expected,
            has_expectation=True,
            import_root=REPO_ROOT,
        )

        proc = _run_pytest(test_file)

        assert proc.returncode != 0, proc.stdout
        assert (
            "unexpected" in proc.stdout.lower()
            or "exhausted" in proc.stdout.lower()
            or "diverged" in proc.stdout.lower()
        )


class TestRedaction:
    """Tests for secret redaction in agent traces."""

    def test_crash_agent_redacts_secrets(self, tmp_path: Path) -> None:
        """Secrets in LLM output and tool output are redacted in the trace."""
        agent = _crash_agent()
        trace_path = tmp_path / "crash_redaction.sftrace"

        with (
            pytest.raises(json.JSONDecodeError),
            record("crash-agent", output=trace_path),
        ):
            agent.run_agent()

        for path in trace_path.glob("*"):
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                assert "sk-proj-ABCDEF" not in content
                assert "sk-proj-ZYXW98" not in content
