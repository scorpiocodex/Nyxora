"""
NYXORA Python SDK.

Provides a clean, high-level interface for programmatic vault access
in automation scripts, CI pipelines, and developer tooling.

Usage::

    from nyxora import VaultClient

    with VaultClient() as client:
        entry = client.get("GitHub")
        print(entry.password)

    # Explicit path and password (bypasses session):
    with VaultClient(vault_path="/path/to/vault.nyx",
                     password="master-password") as client:
        for entry in client.list(tag="prod"):
            print(entry.title, entry.username)
"""
from __future__ import annotations

import builtins
from pathlib import Path
from typing import Any, Optional

from nyxora.core.crypto_engine import (
    ARGON2_MEMORY_COST,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    CryptoEngine,
)
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import (
    EntryRecord,
    VaultStore,
    recover_interrupted_password_change,
)
from nyxora.utils.exceptions import EntryNotFoundError, NyxoraError


class VaultClient:
    """High-level vault client for programmatic access.

    Can be used as a context manager (recommended) or manually via
    open() / close().

    Session-based (uses existing unlocked session if no password given)::

        with VaultClient() as client:
            entry = client.get("github")

    Password-based (derives key fresh — does not affect the CLI session)::

        with VaultClient(vault_path=Path("~/.nyxora/vault.nyx"),
                         password="my-master-password") as client:
            entries = client.list()
    """

    def __init__(
        self,
        vault_path: Optional[Path] = None,
        password: Optional[str] = None,
        argon2_memory: int = ARGON2_MEMORY_COST,
        argon2_time: int = ARGON2_TIME_COST,
        argon2_parallelism: int = ARGON2_PARALLELISM,
    ) -> None:
        """Initialise the client.

        Args:
            vault_path: Path to the .nyx vault file. If None, the active
                        profile / CLI session path is used.
            password:   Master password. If None, the current CLI session
                        key is used (vault must already be unlocked).
            argon2_memory: Argon2id memory parameter in KiB. Defaults to
                           the canonical CryptoEngine value the CLI uses,
                           so the SDK derives the identical key and can
                           open CLI-created vaults. Override only if your
                           vault was created with custom parameters.
            argon2_time:   Argon2id iteration count (canonical default).
            argon2_parallelism: Argon2id thread count (canonical default).
        """
        self._vault_path = vault_path
        self._password = password
        self._argon2_memory = argon2_memory
        self._argon2_time = argon2_time
        self._argon2_parallelism = argon2_parallelism
        self._engine: Optional[CryptoEngine] = None
        self._store: Optional[VaultStore] = None
        self._root_key: Optional[bytearray] = None

    # ── Context manager ────────────────────────────────────────────────────

    def __enter__(self) -> "VaultClient":
        self.open()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def open(self) -> None:
        """Open the vault. Called automatically by the context manager."""
        self._engine = CryptoEngine(
            argon2_memory=self._argon2_memory,
            argon2_time=self._argon2_time,
            argon2_parallelism=self._argon2_parallelism,
        )

        if self._password is not None:
            # Derive key from provided password
            vp = self._resolve_vault_path()
            # Heal any interrupted change-password swap before reading
            # the salt sidecar.
            recover_interrupted_password_change(vp)
            salt_file = vp.with_suffix(".salt")
            if not salt_file.exists():
                raise NyxoraError(f"Salt file not found at {salt_file}")
            salt = salt_file.read_bytes()
            self._root_key = self._engine.derive_key(self._password, salt)
            self._store = VaultStore(self._engine)
            self._store.open(vp, self._root_key)
        else:
            # Use existing CLI session
            from nyxora.cli.helpers import load_session
            session = load_session()
            if session is None:
                raise NyxoraError(
                    "No active session. Run 'nyx vault unlock' first, "
                    "or provide a password to VaultClient."
                )
            _, vault_path, root_key = session
            self._root_key = root_key
            vp = self._vault_path or vault_path
            self._store = VaultStore(self._engine)
            self._store.open(vp, self._root_key)

    def close(self) -> None:
        """Close the vault and wipe the root key."""
        if self._store is not None:
            try:
                self._store.close()
            except Exception:
                pass
            self._store = None
        if self._root_key is not None:
            wipe_memory(self._root_key)
            self._root_key = None

    def _resolve_vault_path(self) -> Path:
        if self._vault_path:
            return self._vault_path
        from nyxora.cli.helpers import load_profiles
        from nyxora.utils.config import Config
        data = load_profiles()
        active = data.get("active")
        if active and active in data.get("profiles", {}):
            vp = data["profiles"][active].get("vault_path")
            if vp:
                return Path(vp)
        config = Config()
        config.load()
        vp_cfg = config.get("vault.default_path")
        if vp_cfg:
            return Path(vp_cfg)
        return Path.home() / ".nyxora" / "vault.nyx"

    def _require_open(self) -> VaultStore:
        if self._store is None:
            raise NyxoraError(
                "VaultClient is not open. Use 'with VaultClient() as client:' "
                "or call client.open() first."
            )
        return self._store

    # ── Entry operations ───────────────────────────────────────────────────

    def get(self, entry_id: str) -> EntryRecord:
        """Get an entry by ID or title prefix.

        Args:
            entry_id: Full UUID or title prefix (case-insensitive search).

        Returns:
            EntryRecord with decrypted fields.

        Raises:
            EntryNotFoundError: if no matching entry is found.
        """
        store = self._require_open()
        # Try direct ID lookup first
        try:
            return store.get_entry(entry_id)
        except EntryNotFoundError:
            pass
        # Fall back to title search
        results = store.search_entries(entry_id)
        if not results:
            raise EntryNotFoundError(f"No entry found matching '{entry_id}'.")
        return results[0]

    def list(self, tag: Optional[str] = None) -> list[EntryRecord]:
        """List all (non-deleted) entries, optionally filtered by tag.

        Args:
            tag: If provided, only entries with this tag are returned.

        Returns:
            List of EntryRecord objects.
        """
        store = self._require_open()
        entries = store.list_entries()
        if tag:
            entries = [e for e in entries if tag in e.tags]
        return entries

    def search(self, query: str) -> builtins.list[EntryRecord]:
        """Search entries by title, username, URL, or tags.

        Args:
            query: Search string (case-insensitive substring match).

        Returns:
            List of matching EntryRecord objects.
        """
        return self._require_open().search_entries(query)

    def add(
        self,
        title: str,
        password: str,
        username: Optional[str] = None,
        url: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[builtins.list[str]] = None,
        custom: Optional[dict[str, str]] = None,
        totp_secret: Optional[str] = None,
    ) -> str:
        """Add a new entry to the vault.

        Returns:
            The new entry's UUID string.
        """
        return self._require_open().add_entry(
            title=title, password=password, username=username,
            url=url, notes=notes, tags=tags, custom=custom,
            totp_secret=totp_secret,
        )

    def update(
        self,
        entry_id: str,
        title: Optional[str] = None,
        password: Optional[str] = None,
        username: Optional[str] = None,
        url: Optional[str] = None,
        notes: Optional[str] = None,
        tags: Optional[builtins.list[str]] = None,
        custom: Optional[dict[str, str]] = None,
        totp_secret: Optional[str] = None,
    ) -> None:
        """Update one or more fields on an existing entry."""
        self._require_open().update_entry(
            entry_id, title=title, password=password,
            username=username, url=url, notes=notes,
            tags=tags, custom=custom, totp_secret=totp_secret,
        )

    def delete(self, entry_id: str) -> None:
        """Soft-delete an entry."""
        self._require_open().delete_entry(entry_id)

    def get_totp(self, entry_id: str) -> str:
        """Return the current TOTP code for an entry.

        Args:
            entry_id: Entry ID or title prefix.

        Returns:
            6-digit TOTP code string.

        Raises:
            NyxoraError: if the entry has no TOTP secret.
        """
        import pyotp
        record = self.get(entry_id)
        if not record.totp_secret:
            raise NyxoraError(
                f"Entry '{record.title}' has no TOTP secret configured."
            )
        return pyotp.TOTP(record.totp_secret).now()

    def health(self) -> Any:
        """Compute and return the vault health score.

        Returns:
            VaultHealthScore dataclass.
        """
        from nyxora.core.intel_engine import IntelEngine
        entries = self.list()
        intel = IntelEngine(self._engine)  # type: ignore[arg-type]
        return intel.compute_health_score(entries)

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def entry_count(self) -> int:
        """Number of non-deleted entries."""
        return self._require_open().entry_count()

    @property
    def vault_id(self) -> str:
        """The vault's UUID."""
        return self._require_open().get_vault_id()
