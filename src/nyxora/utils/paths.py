"""Base-directory resolution for all Nyxora runtime data.

Every file Nyxora writes (session state, the vault, recovery/backup artifacts,
the update-state file, the locker, …) lives under a single base directory. That
directory resolves to ``$NYXORA_HOME`` when set, otherwise ``~/.nyxora`` — so the
default behavior is unchanged for existing users, while tests (and isolated
deployments) can redirect everything by exporting ``NYXORA_HOME``.

All other modules derive their paths from :func:`nyxora_home` so there is a
single source of truth.
"""
from __future__ import annotations

import os
from pathlib import Path


def nyxora_home() -> Path:
    """Return the base directory for Nyxora runtime data.

    Resolves to ``$NYXORA_HOME`` when set (enabling isolated integration tests),
    else ``~/.nyxora`` (unchanged for existing users).
    """
    override = os.environ.get("NYXORA_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".nyxora"


def default_vault_path() -> Path:
    """Return the default vault path, ``<nyxora_home>/vault.nyx``."""
    return nyxora_home() / "vault.nyx"
