"""Tests for the ``botmarket`` command-line interface.

These run the real installed command as a subprocess. The behaviour that
matters here — exit codes, what lands on stdout, and how it copes with a
pipeline that stops reading — only exists at the process boundary, so calling
``main()`` in-process would test something else.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def cli(tmp_path):
    """Return a runner for the CLI, pointed at a database of its own."""
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{tmp_path / 'cli.db'}",
        "ENVIRONMENT": "test",
    }
    binary = Path(sys.executable).parent / "botmarket"

    def _run(*args: str, pipe_to: list[str] | None = None) -> subprocess.CompletedProcess:
        if pipe_to is None:
            return subprocess.run(
                [str(binary), *args], env=env, capture_output=True, text=True, timeout=120
            )
        # Reproduce a real pipeline, so a downstream reader really can hang up.
        first = subprocess.Popen(
            [str(binary), *args], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        second = subprocess.Popen(pipe_to, stdin=first.stdout, stdout=subprocess.PIPE)
        first.stdout.close()
        out, _ = second.communicate(timeout=120)
        stderr = first.stderr.read().decode()
        first.wait(timeout=30)
        return subprocess.CompletedProcess(
            args, first.returncode, out.decode(), stderr
        )

    return _run


def test_reset_reports_the_resolved_database(cli):
    """The default DATABASE_URL is relative, so the path has to be unambiguous."""
    result = cli("reset")
    assert result.returncode == 0
    assert "Reset complete" in result.stdout
    assert "cli.db" in result.stdout


def test_seed_then_tick_then_state(cli):
    cli("reset")

    seeded = cli("seed")
    assert seeded.returncode == 0
    assert "Created 6 new agent(s)" in seeded.stdout

    ticked = cli("tick", "--count", "3")
    assert ticked.returncode == 0
    assert ticked.stdout.count("tick ") == 3

    state = cli("state")
    assert state.returncode == 0
    assert "agents 6" in state.stdout


def test_seeding_twice_creates_nothing_new(cli):
    cli("reset")
    cli("seed")
    assert "Created 0 new agent(s)" in cli("seed").stdout


def test_ticking_an_empty_world_explains_itself(cli):
    cli("reset")
    result = cli("tick")
    assert result.returncode == 1
    assert "run `botmarket seed` first" in result.stderr


def test_keygen_prints_a_usable_key(cli):
    result = cli("keygen")
    assert result.returncode == 0
    assert result.stdout.startswith("VENUE_ENCRYPTION_KEY=")

    from cryptography.fernet import Fernet

    key = result.stdout.splitlines()[0].split("=", 1)[1]
    Fernet(key.encode())  # raises if the key is not usable


@pytest.mark.parametrize("command", [("seed",), ("state",), ("reset",), ("keygen",)])
def test_a_closed_pipe_is_not_an_error(cli, command):
    """`botmarket seed | head -1` is a normal way to end a pipeline.

    Every command that prints more than one line can have its reader hang up
    part-way through; none of them should answer that with a traceback.
    """
    cli("reset")
    cli("seed")

    result = cli(*command, pipe_to=["head", "-1"])
    assert "BrokenPipeError" not in result.stderr
    assert "Traceback" not in result.stderr
    assert result.returncode == 0


def test_an_unknown_command_is_rejected(cli):
    assert cli("frobnicate").returncode != 0
