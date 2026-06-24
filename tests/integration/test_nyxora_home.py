"""v3.1.0 #9 — NYXORA_HOME base-directory override for test isolation.

The base directory for all runtime data (session, vault, recovery/backup, …)
must resolve to $NYXORA_HOME when set, else ~/.nyxora (unchanged for existing
users). This lets real-CLI integration tests run isolated from the user's actual
~/.nyxora.
"""
from __future__ import annotations

import importlib
from pathlib import Path


def test_nyxora_home_env_override(monkeypatch, tmp_path):
    """NYXORA_HOME redirects the base dir (and derived paths) into a temp dir."""
    monkeypatch.setenv("NYXORA_HOME", str(tmp_path))
    from nyxora.utils import paths

    assert paths.nyxora_home() == tmp_path
    assert paths.default_vault_path() == tmp_path / "vault.nyx"


def test_nyxora_home_default_when_unset(monkeypatch):
    """Unset NYXORA_HOME defaults to ~/.nyxora — zero change for existing users."""
    monkeypatch.delenv("NYXORA_HOME", raising=False)
    from nyxora.utils import paths

    assert paths.nyxora_home() == Path.home() / ".nyxora"
    assert paths.default_vault_path() == Path.home() / ".nyxora" / "vault.nyx"


def test_module_path_constants_follow_nyxora_home(monkeypatch, tmp_path):
    """The import-time path constants (SESSION_FILE, STATE_FILE, …) derive from
    the resolver, so an integration test that sets NYXORA_HOME before the process
    imports them lands every file inside the temp dir."""
    monkeypatch.setenv("NYXORA_HOME", str(tmp_path))
    import nyxora.cli.commands.locker as locker
    import nyxora.cli.helpers as helpers
    import nyxora.core.update_engine as update_engine

    importlib.reload(helpers)
    importlib.reload(update_engine)
    importlib.reload(locker)
    try:
        assert helpers.SESSION_FILE == tmp_path / "session.json"
        assert helpers.SESSION_KEY_FILE == tmp_path / "session.key"
        assert helpers.PROFILES_FILE == tmp_path / "profiles.json"
        assert update_engine.STATE_FILE == tmp_path / "update_state.json"
        assert locker.LOCKER_DIR == tmp_path / "locker"
    finally:
        # Restore the module constants to their default-env values so later
        # tests that patch these attributes are unaffected.
        monkeypatch.delenv("NYXORA_HOME", raising=False)
        importlib.reload(helpers)
        importlib.reload(update_engine)
        importlib.reload(locker)
