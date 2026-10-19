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
        # Mode is valid, but this trace has no failure to minimize: frozen
        # reports "no failure", the other modes refuse the policy error.
        # Neither may exit 0 or write a bundle from a harness refusal.
        assert cli_result.exit_code == 1, f"Mode {mode} exited {cli_result.exit_code}"
        assert "Minimized trace saved" not in cli_result.stdout


def test_minimize_forbidden_refuses_policy_error(tmp_path: Path) -> None:
    """A replay policy refusal is never used as a failure signature."""
    trace_path = tmp_path / "test.sftrace"
    with record("cli-test-agent", output=str(trace_path)) as session:
        output = simple_agent()
        session.set_output(output)

    expect_path = tmp_path / "expect.json"
    expect_path.write_text('{"value": 99}')

    frozen_result = runner.invoke(
        app,
        [
            "minimize",
            str(trace_path),
            "--entrypoint",
            "test_minimize_mode_validation:simple_agent",
            "--expect-output",
            str(expect_path),
            "--output",
            str(tmp_path / "frozen.sftrace"),
        ],
    )
    assert frozen_result.exit_code == 0
    assert "Minimized trace saved" in frozen_result.stdout

    forbidden_result = runner.invoke(
        app,
        [
            "minimize",
            str(trace_path),
            "--entrypoint",
            "test_minimize_mode_validation:simple_agent",
            "--expect-output",
            str(expect_path),
            "--mode",
            "forbidden",
            "--output",
            str(tmp_path / "forbidden.sftrace"),
        ],
    )
    assert forbidden_result.exit_code == 1
    assert "Minimized trace saved" not in forbidden_result.stdout
    flattened = " ".join(forbidden_result.stdout.split())
    assert "replay policy refused the attempt" in flattened
