"""Behavioral tests for nyxora.cli.helpers path + session resolution.

Replaces the coverage-gaming `test_helpers_branches` from the removed
test_massive_coverage.py with assertions on the real contract: get_vault_path
falls back to the config default, and load_session degrades to None on a missing
or malformed session file rather than raising.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from nyxora.cli import helpers
from nyxora.utils.config import Config


def test_get_vault_path_falls_back_to_config_default():
    c = Config()
    c.set("vault.default_path", "/fake/vault/path.nyx")
    # No active profile => the config default is used.
    with patch(
        "nyxora.cli.helpers.load_profiles",
        return_value={"profiles": {}, "active": None},
    ):
        assert helpers.get_vault_path(c) == Path("/fake/vault/path.nyx")


def test_load_session_returns_none_when_file_missing(tmp_path):
    with patch("nyxora.cli.helpers.SESSION_FILE", tmp_path / "nope.json"):
        assert helpers.load_session() is None


def test_load_session_returns_none_on_malformed_session(tmp_path):
    sess = tmp_path / "session.json"
    sess.write_text("{}")  # valid JSON but missing session_id
    with patch("nyxora.cli.helpers.SESSION_FILE", sess):
        assert helpers.load_session() is None
