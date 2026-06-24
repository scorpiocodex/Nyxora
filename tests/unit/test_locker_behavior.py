"""Behavioral tests for `nyx locker` — encrypt/decrypt round-trip and errors.

Replaces the coverage-gaming `locker` cases from the removed
test_massive_coverage.py (which invoked encrypt/decrypt/list and asserted
nothing). These assert the real contract: ciphertext round-trips back to the
original bytes, the on-disk header matches the documented format, and missing
files / a locked vault fail with the right exit codes.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nyxora.cli.main import app
from nyxora.core.crypto_engine import CryptoEngine

runner = CliRunner()


@pytest.fixture
def session_key() -> bytes:
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    return bytes(engine.derive_key("locker-pw", engine.generate_salt()))


def _patch_session(master: bytes, vault_path):
    # Return a FRESH copy of the key on every call — the locker commands wipe the
    # bytearray they receive, so a shared object would be zeroed after encrypt and
    # break the subsequent decrypt.
    return patch(
        "nyxora.cli.commands.locker.load_session",
        side_effect=lambda: ("sid", vault_path, bytearray(master)),
    )


def test_encrypt_then_decrypt_round_trips(tmp_path, session_key):
    secret = b"top secret locker payload \x00\x01\xfe"
    src = tmp_path / "target.txt"
    src.write_bytes(secret)
    enc = tmp_path / "out.nyx"
    dec = tmp_path / "recovered.txt"
    vp = tmp_path / "v.nyx"

    with _patch_session(session_key, vp):
        r1 = runner.invoke(app, ["locker", "encrypt", str(src), "--output", str(enc)])
        assert r1.exit_code == 0, r1.output
        assert enc.exists()
        # Documented header: [4-byte name length][name][16-byte salt][blob].
        raw = enc.read_bytes()
        name_len = int.from_bytes(raw[:4], "big")
        assert name_len == len("target.txt")
        assert raw[4:4 + name_len] == b"target.txt"
        assert raw[4 + name_len:] != secret  # body is ciphertext, not plaintext

        r2 = runner.invoke(app, ["locker", "decrypt", str(enc), "--output", str(dec)])
        assert r2.exit_code == 0, r2.output
        assert dec.read_bytes() == secret  # exact byte round-trip


def test_encrypt_missing_file_exits_1(tmp_path, session_key):
    vp = tmp_path / "v.nyx"
    missing = tmp_path / "nope.txt"
    with _patch_session(session_key, vp):
        r = runner.invoke(app, ["locker", "encrypt", str(missing)])
    assert r.exit_code == 1
    assert not missing.with_suffix(".txt.nyx").exists()


def test_decrypt_missing_file_exits_1(tmp_path, session_key):
    vp = tmp_path / "v.nyx"
    with _patch_session(session_key, vp):
        r = runner.invoke(app, ["locker", "decrypt", str(tmp_path / "nope.nyx")])
    assert r.exit_code == 1


def test_encrypt_locked_vault_exits_2(tmp_path):
    src = tmp_path / "f.txt"
    src.write_text("data")
    with patch("nyxora.cli.commands.locker.load_session", return_value=None):
        r = runner.invoke(app, ["locker", "encrypt", str(src)])
    assert r.exit_code == 2  # locked vault => exit code 2
