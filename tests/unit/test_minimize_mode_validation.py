"""Unit tests for minimize mode validation."""

from __future__ import annotations

from pathlib import Path

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


def test_minimize_rejects_hybrid_mode(tmp_path: Path) -> None:
    """Minimize rejects unsupported 'hybrid' mode."""
    trace_path = tmp_path / "test.sftrace"
    with record("cli-test-agent", output=str(trace_path)) as session:
        output = simple_agent()
        session.set_output(output)

    cli_result = runner.invoke(
        app,
        [
            "minimize",
            str(trace_path),
            "--entrypoint",
            "test_minimize_mode_validation:simple_agent",
            "--mode",
            "hybrid",
        ],
    )
    assert cli_result.exit_code == 2
    assert "Invalid replay mode" in cli_result.stdout


def test_minimize_rejects_bogus_mode(tmp_path: Path) -> None:
    """Minimize rejects invalid mode values."""
    trace_path = tmp_path / "test.sftrace"
    with record("cli-test-agent", output=str(trace_path)) as session:
        output = simple_agent()
        session.set_output(output)

    cli_result = runner.invoke(
        app,
        [
            "minimize",
            str(trace_path),
            "--entrypoint",
            "test_minimize_mode_validation:simple_agent",
            "--mode",
            "bogus",
        ],
    )
    assert cli_result.exit_code == 2
    assert "Invalid replay mode" in cli_result.stdout


def test_minimize_accepts_valid_modes(tmp_path: Path) -> None:
    """Valid modes are accepted by minimize."""
    trace_path = tmp_path / "test.sftrace"
    with record("cli-test-agent", output=str(trace_path)) as session:
        output = simple_agent()
        session.set_output(output)

    for mode in ("frozen", "live", "forbidden", "manual", "derived"):
        cli_result = runner.invoke(
            app,
            [
                "minimize",
                str(trace_path),
                "--entrypoint",
                "test_minimize_mode_validation:simple_agent",
                "--mode",
                mode,
            ],
        )
        # Valid modes may still fail minimization if trace doesn't fail as expected,
        # but should not be rejected with exit 2 for invalid mode
        assert cli_result.exit_code != 2, f"Mode {mode} was incorrectly rejected"
