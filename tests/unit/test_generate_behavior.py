"""Behavioral tests for `nyx generate` — assert the real output contract.

Replaces the coverage-gaming `generate` cases from the removed
test_massive_coverage.py, which invoked the commands and asserted nothing. Each
test here asserts a real contract (length, charset, count, separator, prefix) and
fails if the generator misbehaves. JSON mode (`--json`) gives a deterministic,
parseable result to assert against.
"""
from __future__ import annotations

import json
import string

import pytest
from typer.testing import CliRunner

from nyxora.cli import ui
from nyxora.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_json_mode():
    # The --json flag flips a module-global in nyxora.cli.ui; reset it after each
    # test so JSON mode never leaks into the rest of the suite.
    yield
    ui.set_json_mode(False)


def _json_objects(output: str) -> list[dict]:
    return [
        json.loads(line)
        for line in output.splitlines()
        if line.strip().startswith("{")
    ]


def test_password_respects_length_count_and_charset():
    result = runner.invoke(
        app,
        ["--json", "generate", "password", "-l", "12", "-n", "3",
         "--no-symbols", "--no-digits", "--no-upper"],
    )
    assert result.exit_code == 0
    objs = _json_objects(result.output)
    assert len(objs) == 3  # --count honored
    for obj in objs:
        pw = obj["password"]
        assert len(pw) == 12  # --length honored
        # --no-symbols --no-digits --no-upper => lowercase ASCII only
        assert all(c in string.ascii_lowercase for c in pw), pw
        assert obj["entropy_bits"] > 0


def test_password_full_charset_default():
    result = runner.invoke(app, ["--json", "generate", "password", "-l", "30"])
    assert result.exit_code == 0
    objs = _json_objects(result.output)
    assert len(objs) == 1
    assert len(objs[0]["password"]) == 30
    assert objs[0]["strength"]  # a non-empty strength label


def test_passphrase_word_count_and_separator():
    result = runner.invoke(
        app, ["--json", "generate", "passphrase", "-w", "6", "-s", "."],
    )
    assert result.exit_code == 0
    objs = _json_objects(result.output)
    assert len(objs) == 1
    obj = objs[0]
    assert obj["word_count"] == 6
    # words are joined by the chosen separator; wordlist words are letters only
    parts = obj["passphrase"].split(".")
    assert len(parts) == 6
    assert all(p.isalpha() for p in parts), parts


def test_api_key_applies_prefix():
    result = runner.invoke(
        app, ["generate", "api-key", "-l", "16", "--prefix", "TESTPFX"]
    )
    assert result.exit_code == 0
    assert "TESTPFX_" in result.output  # prefix contract: f"{prefix}_{key}"
