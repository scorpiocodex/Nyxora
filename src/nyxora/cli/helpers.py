"""Shared CLI helpers for NYXORA."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import keyring
import typer

from nyxora.cli import ui
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.vault_store import VaultStore
from nyxora.utils.config import Config

SERVICE_NAME = "nyxora_vault_session"


SESSION_FILE = Path.home() / ".nyxora" / "session.json"
PROFILES_FILE = Path.home() / ".nyxora" / "profiles.json"


def get_vault_path(config: Config) -> Path:
    # Check active profile first
    data = load_profiles()
    active = data.get("active")
    if active and active in data.get("profiles", {}):
        profile_path = data["profiles"][active].get("vault_path")
        if profile_path:
            return Path(profile_path)
    # Fall back to config
    vp = config.get("vault.default_path")
    if vp:
        return Path(vp)
    return Path.home() / ".nyxora" / "vault.nyx"  # pragma: no cover


def save_session(session_id: str, vault_path: str, root_key_hex: str) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps({
        "session_id": session_id,
        "vault_path": vault_path,
    })

    try:
        keyring.set_password(SERVICE_NAME, session_id, root_key_hex)
    except Exception as e:  # pragma: no cover
        ui.error_panel(f"Failed to securely store session key in OS keyring: {e}")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOINHERIT"):
        flags |= getattr(os, "O_NOINHERIT")

    try:
        fd = os.open(str(SESSION_FILE), flags, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(data)
    except Exception as e:  # pragma: no cover
        ui.error_panel(f"Failed to save session securely: {e}")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover


def load_session() -> tuple[str, Path, bytearray] | None:
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text())
        session_id = data["session_id"]
        vault_path = Path(data["vault_path"])

        root_key_hex = keyring.get_password(SERVICE_NAME, session_id)
        if not root_key_hex:
            return None

        return (
            session_id,
            vault_path,
            bytearray.fromhex(root_key_hex),
        )
    except Exception:
        return None


def clear_session() -> None:
    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text())
            session_id = data.get("session_id")
            if session_id:
                try:
                    keyring.delete_password(SERVICE_NAME, session_id)
                except Exception:  # pragma: no cover
                    pass  # pragma: no cover
        except Exception:  # pragma: no cover
            pass  # pragma: no cover
        SESSION_FILE.unlink(missing_ok=True)


def load_profiles() -> dict:
    """Load the profiles registry from disk."""
    if not PROFILES_FILE.exists():
        return {"profiles": {}, "active": None}
    try:
        import json as _json
        return _json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"profiles": {}, "active": None}


def save_profiles(data: dict) -> None:
    """Persist the profiles registry to disk."""
    import json as _json
    PROFILES_FILE.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOINHERIT"):
        flags |= getattr(os, "O_NOINHERIT")
    fd = os.open(str(PROFILES_FILE), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(_json.dumps(data, indent=2))


def get_active_profile() -> str | None:
    """Return the name of the active profile, or None if not set."""
    return load_profiles().get("active")


def set_active_profile(name: str) -> None:
    """Set the active profile by name. Raises ValueError if not found."""
    data = load_profiles()
    if name not in data.get("profiles", {}):
        raise ValueError(f"Profile '{name}' not found.")
    data["active"] = name
    save_profiles(data)


def complete_entry_ids(
    ctx: Any, incomplete: str
) -> list[str]:
    """Shell completion callback — returns entry titles matching incomplete."""
    try:
        from nyxora.core.crypto_engine import CryptoEngine
        from nyxora.core.vault_store import VaultStore
        session = load_session()
        if session is None:
            return []
        _, vault_path, root_key = session
        engine = CryptoEngine(
            argon2_memory=8192, argon2_time=1, argon2_parallelism=1
        )
        store = VaultStore(engine)
        store.open(vault_path, root_key)
        entries = store.list_entries()
        store.close()
        from nyxora.core.memory_guard import wipe_memory
        wipe_memory(root_key)
        return [
            e.title for e in entries
            if incomplete.lower() in e.title.lower()
        ]
    except Exception:
        return []


def open_vault(crypto: CryptoEngine) -> tuple[VaultStore, str, bytearray, Path]:
    """Load session and open the vault, returning (store, session_id, root_key, vault_path).

    The caller is responsible for wiping the root_key (or passing it to finally block)
    and calling store.close().
    """
    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked. Run 'nyx vault unlock' first.")  # pragma: no cover
        raise typer.Exit(2)  # pragma: no cover

    session_id, vault_path, root_key = session_data
    store = VaultStore(crypto)
    try:
        store.open(vault_path, root_key)
    except Exception as e:  # pragma: no cover
        from nyxora.core.memory_guard import wipe_memory  # pragma: no cover
        wipe_memory(root_key)  # pragma: no cover
        ui.error_panel(str(e))  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover

    return store, session_id, root_key, vault_path
