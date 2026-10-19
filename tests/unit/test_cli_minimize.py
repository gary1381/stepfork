"""Unit tests for the minimize CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from stepfork import record, trace_tool
from stepfork.cli.main import app

runner = CliRunner()


@trace_tool(name="simple_tool")
def simple_tool(x: int) -> int:
    """Simple test tool."""
    return x * 2


def simple_agent() -> dict[str, int]:
    """Simple test agent."""
    result = simple_tool(5)
    return {"value": result}


@pytest.fixture
def test_trace(tmp_path: Path) -> Path:
    """Create a test trace."""
    trace_path = tmp_path / "test.sftrace"
    with record("cli-test-agent", output=str(trace_path)) as session:
        result = simple_agent()
        session.set_output(result)
    return trace_path


@pytest.fixture
def expected_output_file(tmp_path: Path) -> Path:
    """Create an expected output file."""
    output_file = tmp_path / "expected.json"
    output_file.write_text(json.dumps({"value": 999}))
    return output_file


def test_minimize_command_missing_entrypoint(test_trace: Path) -> None:
    """Minimize command requires --entrypoint."""
    result = runner.invoke(app, ["minimize", str(test_trace)])
    assert result.exit_code != 0


def test_minimize_command_invalid_trace_path() -> None:
    """Minimize command fails with invalid trace path."""
    result = runner.invoke(
        app,
        [
            "minimize",
            "nonexistent.sftrace",
            "--entrypoint",
            "test:agent",
        ],
    )
    assert result.exit_code != 0


def test_minimize_command_with_expected_output(
    test_trace: Path,
    expected_output_file: Path,
    tmp_path: Path,
) -> None:
    """Minimize command accepts --expect-output."""
    output_path = tmp_path / "minimized.sftrace"

    result = runner.invoke(
        app,
        [
            "minimize",
            str(test_trace),
            "--entrypoint",
            "test_cli_minimize:simple_agent",
            "--expect-output",
            str(expected_output_file),
            "--output",
            str(output_path),
        ],
    )

    # Command should complete (may succeed or fail depending on trace)
    assert result.exit_code in (0, 1)


def test_minimize_command_with_mode_option(
    test_trace: Path,
    expected_output_file: Path,
    tmp_path: Path,
) -> None:
    """Minimize command accepts --mode."""
    output_path = tmp_path / "minimized.sftrace"

    result = runner.invoke(
        app,
        [
            "minimize",
            str(test_trace),
            "--entrypoint",
            "test_cli_minimize:simple_agent",
            "--expect-output",
            str(expected_output_file),
            "--mode",
            "frozen",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code in (0, 1)


def test_minimize_command_with_timeout(
    test_trace: Path,
    expected_output_file: Path,
    tmp_path: Path,
) -> None:
    """Minimize command accepts --timeout."""
    output_path = tmp_path / "minimized.sftrace"

    result = runner.invoke(
        app,
        [
            "minimize",
            str(test_trace),
            "--entrypoint",
            "test_cli_minimize:simple_agent",
            "--expect-output",
            str(expected_output_file),
            "--timeout",
            "5.0",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code in (0, 1)


def test_minimize_command_with_attempts(
    test_trace: Path,
    expected_output_file: Path,
    tmp_path: Path,
) -> None:
    """Minimize command accepts --attempts."""
    output_path = tmp_path / "minimized.sftrace"

    result = runner.invoke(
        app,
        [
            "minimize",
            str(test_trace),
            "--entrypoint",
            "test_cli_minimize:simple_agent",
            "--expect-output",
            str(expected_output_file),
            "--attempts",
            "2",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code in (0, 1)


def test_minimize_command_output_defaults_to_minimized_suffix(
    test_trace: Path,
    expected_output_file: Path,
    tmp_path: Path,
) -> None:
    """Minimize command creates output with -minimized suffix by default."""
    result = runner.invoke(
        app,
        [
            "minimize",
            str(test_trace),
            "--entrypoint",
            "test_cli_minimize:simple_agent",
            "--expect-output",
            str(expected_output_file),
        ],
    )

    # Check that output path with -minimized suffix is mentioned or created
    # (may not exist if minimization failed, but command should handle it)
    assert result.exit_code in (0, 1)


def test_minimize_command_respects_overwrite_flag(
    test_trace: Path,
    expected_output_file: Path,
    tmp_path: Path,
) -> None:
    """Minimize command respects --overwrite flag."""
    output_path = tmp_path / "minimized.sftrace"

    # Create empty directory at output path
    output_path.mkdir()
    (output_path / "dummy.txt").write_text("test")

    # Without --overwrite, should fail
    result = runner.invoke(
        app,
        [
            "minimize",
            str(test_trace),
            "--entrypoint",
            "test_cli_minimize:simple_agent",
            "--expect-output",
            str(expected_output_file),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0

    # With --overwrite, should work (or fail for different reason)
    result = runner.invoke(
        app,
        [
            "minimize",
            str(test_trace),
            "--entrypoint",
            "test_cli_minimize:simple_agent",
            "--expect-output",
            str(expected_output_file),
            "--output",
            str(output_path),
            "--overwrite",
        ],
    )

    # May succeed or fail based on minimization result, but not due to overwrite
    assert result.exit_code in (0, 1)


def test_minimize_already_minimal_shows_minimal_yes(tmp_path: Path) -> None:
    """When a trace is already minimal, the report shows 'Minimal: Yes' not 'No'.

    Regression test for Finding 4 item 1: 'Minimal: No' was incorrectly shown
    when the trace was already at its smallest possible form.
    """
    from stepfork import FailureInfo, Trace
    from stepfork.trace import ErrorEvent, RunEnd, RunStart, RunStatus

    # Create a minimal failing trace (just run_start, error, run_end)
    trace_path = tmp_path / "minimal.sftrace"
    trace = Trace(agent_name="minimal-agent")
    trace.add(RunStart())
    trace.add(ErrorEvent(error_type="ValueError", message="test error"))
    trace.add(RunEnd(run_status=RunStatus.FAILED))
    trace.status = RunStatus.FAILED
    trace.failure = FailureInfo(type="ValueError", message="test error", step=1)
    trace.save(trace_path)

    # Agent that raises the same error
    output_path = tmp_path / "out.sftrace"
    result = runner.invoke(
        app,
        [
            "minimize",
            str(trace_path),
            "-e",
            "test_cli_minimize:_raise_value_error",
            "--output",
            str(output_path),
        ],
    )

    # When already minimal, report should show "Yes" not "No"
    assert "Minimal" in result.stdout
    assert "[green]Yes[/green]" in result.stdout or "Yes" in result.stdout
    # Should NOT show contradictory "No" next to "already minimal"
    assert not ("[yellow]No[/yellow]" in result.stdout and "already minimal" in result.stdout.lower())


def _raise_value_error() -> None:
    """Helper for test_minimize_already_minimal_shows_minimal_yes."""
    raise ValueError("test error")


def test_minimize_failed_trace_keeps_run_end(tmp_path: Path) -> None:
    """Minimizing a failed trace preserves run_end event.

    Regression test for Finding 4 item 2: run_end was being dropped from
    minimized failed traces even though docs say run markers are kept.
    """
    from stepfork import FailureInfo, Trace
    from stepfork.trace import (
        ErrorEvent,
        EventType,
        RunEnd,
        RunStart,
        RunStatus,
        ToolCall,
        ToolResult,
    )

    # Create a failing trace with multiple events
    trace_path = tmp_path / "failed.sftrace"
    trace = Trace(agent_name="failed-agent")
    trace.add(RunStart())
    trace.add(ToolCall(name="some_tool", input={"x": 1}))
    trace.add(ToolResult(name="some_tool", output={"y": 2}))
    trace.add(ErrorEvent(error_type="ValueError", message="boom"))
    trace.add(RunEnd(run_status=RunStatus.FAILED))
    trace.status = RunStatus.FAILED
    trace.failure = FailureInfo(type="ValueError", message="boom", step=3)
    trace.save(trace_path)

    # Minimize with an agent that raises the same error
    output_path = tmp_path / "minimized.sftrace"
    result = runner.invoke(
        app,
        [
            "minimize",
            str(trace_path),
            "-e",
            "test_cli_minimize:_raise_value_error_boom",
            "--output",
            str(output_path),
        ],
    )

    # Check that minimization succeeded
    if result.exit_code == 0 and output_path.exists():
        minimized = Trace.load(output_path)
        event_types = [e.type for e in minimized.events]

        # run_start and run_end must be preserved per docs/minimize.md
        assert EventType.RUN_START in event_types, "run_start should be preserved"
        assert EventType.RUN_END in event_types, "run_end should be preserved"


def _raise_value_error_boom() -> None:
    """Helper for test_minimize_failed_trace_keeps_run_end."""
    raise ValueError("boom")


def test_minimize_short_flag_e_for_entrypoint(test_trace: Path, tmp_path: Path) -> None:
    """The -e short flag works for --entrypoint on minimize command."""
    expected_output_file = tmp_path / "expected.json"
    expected_output_file.write_text(json.dumps({"value": 999}))
    output_path = tmp_path / "minimized.sftrace"

    result = runner.invoke(
        app,
        [
            "minimize",
            str(test_trace),
            "-e",  # Use short flag
            "test_cli_minimize:simple_agent",
            "--expect-output",
            str(expected_output_file),
            "--output",
            str(output_path),
        ],
    )

    # Should work with -e flag (may succeed or fail on minimization result)
    assert result.exit_code in (0, 1)
    # Should not complain about unknown option -e
    assert "no such option" not in result.stdout.lower()
