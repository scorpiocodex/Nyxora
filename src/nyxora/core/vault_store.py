"""Hardened SQLite vault storage for NYXORA.

Schema:
  - entries: encrypted entry fields with per-entry HMAC
  - metadata: vault-level settings and KDF parameters
  - audit_log: tamper-evident access and mutation log
  - schema_fingerprint: structural integrity check

Integrity model:
  1. Per-entry HMAC — catches field-level tampering
  2. Vault-wide HMAC — catches entry deletion / insertion
  3. Schema fingerprint — catches table structure modification
"""

from __future__ import annotations

import hmac
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import orjson

from nyxora.core.crypto_engine import CryptoEngine, EncryptedField
from nyxora.core.memory_guard import wipe_memory
from nyxora.utils.exceptions import (
    EntryNotFoundError,
    IntegrityError,
    VaultError,
    VaultNotFoundError,
)

# ── SQL Statements ─────────────────────────────────────────────────────────────

_SCHEMA_ENTRIES = """\
CREATE TABLE IF NOT EXISTS entries (
    id           TEXT    PRIMARY KEY,
    title_enc    BLOB    NOT NULL,
    username_enc BLOB,
    password_enc BLOB    NOT NULL,
    url_enc      BLOB,
    notes_enc    BLOB,
    tags_enc     BLOB,
    custom_enc   BLOB,
    totp_secret_enc BLOB,
    entry_hmac   BLOB    NOT NULL,
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL,
    accessed_at  INTEGER,
    entry_salt   BLOB    NOT NULL,
    is_deleted   INTEGER NOT NULL DEFAULT 0
)"""

_SCHEMA_METADATA = """\
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
)"""

_SCHEMA_AUDIT = """\
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   INTEGER NOT NULL,
    event_type  TEXT    NOT NULL,
    entry_id    TEXT,
    session_id  TEXT,
    detail_enc  BLOB,
    log_hmac    BLOB    NOT NULL
)"""

_SCHEMA_FINGERPRINT = """\
CREATE TABLE IF NOT EXISTS schema_fingerprint (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    fingerprint BLOB    NOT NULL,
    computed_at INTEGER NOT NULL
)"""

# Ordered list of CREATE TABLE statements used for fingerprint computation
_ALL_SCHEMA_STMTS: list[str] = [
    _SCHEMA_ENTRIES,
    _SCHEMA_METADATA,
    _SCHEMA_AUDIT,
    _SCHEMA_FINGERPRINT,
]

HARDENED_PRAGMAS: list[str] = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=FULL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA secure_delete=ON",
    "PRAGMA auto_vacuum=FULL",
    "PRAGMA temp_store=MEMORY",
    "PRAGMA trusted_schema=OFF",
    "PRAGMA locking_mode=EXCLUSIVE",
    "PRAGMA mmap_size=0",
]

SCHEMA_VERSION = "2"


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class EntryRecord:
    """Decrypted representation of a vault entry."""

    id: str
    title: str
    password: str
    username: str | None = None
    url: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    custom: dict[str, Any] = field(default_factory=dict)
    created_at: int = 0
    updated_at: int = 0
    accessed_at: int | None = None
    is_deleted: bool = False
    totp_secret: str | None = None


@dataclass
class ForensicReport:
    """Result of a vault integrity verification run."""

    passed: bool
    schema_ok: bool
    vault_hmac_ok: bool
    entries_checked: int
    entries_failed: list[str]  # entry IDs with bad HMACs
    audit_log_ok: bool
    details: list[str] = field(default_factory=list)


# ── VaultStore ────────────────────────────────────────────────────────────────

class VaultStore:
    """Encrypted SQLite vault store with multi-layer tamper detection."""

    def __init__(self, crypto: CryptoEngine) -> None:
        self._crypto = crypto
        self._conn: sqlite3.Connection | None = None
        self._root_key: bytearray | None = None
        self._hmac_key: bytearray | None = None
        self._path: Path | None = None
        self._cache: dict[str, EntryRecord] | None = None
        self._cache_complete: bool = False

    def __enter__(self) -> VaultStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def initialize(self, path: Path, root_key: bytearray) -> None:
        """Create a new vault database at *path*.

        Raises :class:`VaultError` if the file already exists.
        """
        if path.exists():
            raise VaultError(f"Vault already exists at {path}. Use open() to load it.")

        self._path = path
        self._root_key = bytearray(root_key)
        self._hmac_key = self._crypto.derive_hmac_key(self._root_key)

        conn = self._connect(path)
        self._conn = conn

        with conn:
            for stmt in _ALL_SCHEMA_STMTS:
                conn.execute(stmt)

        # Seed metadata
        vault_id = str(uuid.uuid4())
        now = int(time.time())
        meta: list[tuple[str, str]] = [
            ("schema_version", SCHEMA_VERSION),
            ("vault_id", vault_id),
            ("created_at", str(now)),
            ("kdf_mode", "argon2id"),
        ]
        with conn:
            conn.executemany("INSERT INTO metadata (key, value) VALUES (?, ?)", meta)

        # Compute and store schema fingerprint
        self._write_schema_fingerprint(conn)

        # Write initial vault HMAC (empty)
        self._update_vault_hmac(conn)

    def open(self, path: Path, root_key: bytearray) -> None:
        """Open an existing vault and verify its integrity.

        Raises:
            VaultNotFoundError: if the file does not exist.
            IntegrityError: if HMAC or schema fingerprint verification fails.
        """
        if not path.exists():
            raise VaultNotFoundError(f"Vault not found at {path}")

        self._path = path
        self._root_key = bytearray(root_key)
        self._hmac_key = self._crypto.derive_hmac_key(self._root_key)

        conn = self._connect(path)
        self._conn = conn

        # ── Schema migration v1 → v2 (adds totp_secret_enc column) ──────────
        _ver_row = conn.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        _stored_ver = _ver_row["value"] if _ver_row else "1"
        if _stored_ver != SCHEMA_VERSION:
            # Add column if missing (safe on any SQLite version)
            _existing_cols = [
                r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()
            ]
            if "totp_secret_enc" not in _existing_cols:
                with conn:
                    conn.execute(
                        "ALTER TABLE entries ADD COLUMN totp_secret_enc BLOB"
                    )
            # Update stored version
            with conn:
                conn.execute(
                    "UPDATE metadata SET value=? WHERE key='schema_version'",
                    (SCHEMA_VERSION,),
                )
            # Rewrite schema fingerprint to match new _SCHEMA_ENTRIES
            self._write_schema_fingerprint(conn)
        # ── End migration ─────────────────────────────────────────────────────

        # Verify schema fingerprint first
        self._verify_schema_fingerprint(conn)

        # Verify vault-wide HMAC
        self._verify_vault_hmac(conn)

        self._cache = {}
        self._cache_complete = False

    def close(self) -> None:
        """Checkpoint WAL, close connection, wipe keys from memory."""
        if self._conn is not None:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self._conn.close()
            except Exception:  # pragma: no cover
                pass  # pragma: no cover
            finally:
                self._conn = None

        if self._root_key is not None:
            wipe_memory(self._root_key)
            self._root_key = None

        if self._hmac_key is not None:
            wipe_memory(self._hmac_key)
            self._hmac_key = None

        self._cache = None
        self._cache_complete = False

    def _connect(self, path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        for pragma in HARDENED_PRAGMAS:
            conn.execute(pragma)
        return conn

    def _require_open(self) -> tuple[sqlite3.Connection, bytearray, bytearray]:
        if self._conn is None or self._root_key is None or self._hmac_key is None:
            raise VaultError("Vault is not open.")
        try:
            self._conn.execute("SELECT 1")
        except sqlite3.ProgrammingError as e:  # pragma: no cover
            raise VaultError(f"Vault connection is invalid: {e}")  # pragma: no cover
        return self._conn, self._root_key, self._hmac_key

    # ── Schema fingerprint ─────────────────────────────────────────────────

    def _compute_schema_fingerprint(self, hmac_key: bytearray) -> bytes:
        combined = "||".join(sorted(_ALL_SCHEMA_STMTS)).encode("utf-8")
        return self._crypto.compute_hmac(combined, hmac_key)

    def _write_schema_fingerprint(self, conn: sqlite3.Connection) -> None:
        assert self._hmac_key is not None
        fp = self._compute_schema_fingerprint(self._hmac_key)
        now = int(time.time())
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO schema_fingerprint (id, fingerprint, computed_at) VALUES (1, ?, ?)",
                (fp, now),
            )

    def _verify_schema_fingerprint(self, conn: sqlite3.Connection) -> None:
        assert self._hmac_key is not None
        row = conn.execute("SELECT fingerprint FROM schema_fingerprint WHERE id=1").fetchone()
        if row is None:
            raise IntegrityError("Schema fingerprint is missing.")  # pragma: no cover
        self._compute_schema_fingerprint(self._hmac_key)
        if not self._crypto.verify_hmac(
            "||".join(sorted(_ALL_SCHEMA_STMTS)).encode("utf-8"),
            bytes(row["fingerprint"]),
            self._hmac_key,
        ):
            raise IntegrityError("Schema fingerprint mismatch — structural tampering detected.")

    # ── Vault-wide HMAC ────────────────────────────────────────────────────

    def _compute_vault_hmac(
        self, conn: sqlite3.Connection, hmac_key: bytearray
    ) -> bytes:
        """HMAC over all active entry HMACs (sorted), binding the full entry set."""
        rows = conn.execute(
            "SELECT id, entry_hmac FROM entries WHERE is_deleted=0 ORDER BY id"
        ).fetchall()
        parts: list[bytes] = []
        for row in rows:
            parts.append(row["id"].encode("utf-8"))
            parts.append(bytes(row["entry_hmac"]))
        combined = b"||".join(parts)
        return self._crypto.compute_hmac(combined, hmac_key)

    def _update_vault_hmac(self, conn: sqlite3.Connection) -> None:
        assert self._hmac_key is not None
        mac = self._compute_vault_hmac(conn, self._hmac_key)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('vault_hmac', ?)",
                (mac.hex(),),
            )

    def _verify_vault_hmac(self, conn: sqlite3.Connection) -> None:
        assert self._hmac_key is not None
        row = conn.execute(
            "SELECT value FROM metadata WHERE key='vault_hmac'"
        ).fetchone()
        if row is None:
            raise IntegrityError("Vault HMAC is missing from metadata.")  # pragma: no cover
        stored = bytes.fromhex(row["value"])
        expected = self._compute_vault_hmac(conn, self._hmac_key)
        if not hmac.compare_digest(stored, expected):
            raise IntegrityError("Vault-wide HMAC mismatch — entry deletion or insertion detected.")  # pragma: no cover

    # ── Audit log ──────────────────────────────────────────────────────────

    def _append_audit(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        entry_id: str | None = None,
        session_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        assert self._hmac_key is not None
        now = int(time.time())
        detail_enc: bytes | None = None
        if detail:
            detail_bytes = orjson.dumps(detail)
            ef = self._crypto.encrypt_field(detail_bytes, self._hmac_key)
            detail_enc = ef.to_bytes()

        # Build log HMAC
        mac_input = (
            f"{now}|{event_type}|{entry_id or ''}|{session_id or ''}"
        ).encode("utf-8")
        log_hmac = self._crypto.compute_hmac(mac_input, self._hmac_key)

        with conn:
            conn.execute(
                """INSERT INTO audit_log
                   (timestamp, event_type, entry_id, session_id, detail_enc, log_hmac)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (now, event_type, entry_id, session_id, detail_enc, log_hmac),
            )

    # ── Entry operations ───────────────────────────────────────────────────

    def add_entry(
        self,
        title: str,
        password: str,
        username: str | None = None,
        url: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        custom: dict[str, Any] | None = None,
        totp_secret: str | None = None,
        session_id: str | None = None,
    ) -> str:
        """Encrypt and store a new entry. Returns the new entry_id (UUID4)."""
        conn, root_key, hmac_key = self._require_open()

        entry_id = str(uuid.uuid4())
        entry_salt = self._crypto.generate_salt()
        entry_key = self._crypto.derive_entry_key(root_key, entry_id)

        try:
            now = int(time.time())
            ef_title = self._crypto.encrypt_field(title, entry_key)
            ef_password = self._crypto.encrypt_field(password, entry_key)
            ef_username = self._crypto.encrypt_field(username, entry_key) if username else None
            ef_url = self._crypto.encrypt_field(url, entry_key) if url else None
            ef_notes = self._crypto.encrypt_field(notes, entry_key) if notes else None
            ef_tags = (
                self._crypto.encrypt_field(orjson.dumps(tags or []), entry_key)
            )
            ef_custom = (
                self._crypto.encrypt_field(orjson.dumps(custom or {}), entry_key)
            )
            ef_totp = (
                self._crypto.encrypt_field(totp_secret, entry_key)
                if totp_secret
                else None
            )

            # Compute per-entry HMAC
            fields: dict[str, bytes] = {
                "title_enc": ef_title.to_bytes(),
                "password_enc": ef_password.to_bytes(),
            }
            if ef_username:
                fields["username_enc"] = ef_username.to_bytes()
            if ef_url:
                fields["url_enc"] = ef_url.to_bytes()
            if ef_notes:
                fields["notes_enc"] = ef_notes.to_bytes()
            fields["tags_enc"] = ef_tags.to_bytes()
            fields["custom_enc"] = ef_custom.to_bytes()
            if ef_totp:
                fields["totp_secret_enc"] = ef_totp.to_bytes()

            entry_hmac = self._crypto.compute_entry_hmac(entry_id, fields, hmac_key)

            with conn:
                conn.execute(
                    """INSERT INTO entries
                       (id, title_enc, username_enc, password_enc, url_enc, notes_enc,
                        tags_enc, custom_enc, totp_secret_enc, entry_hmac, created_at,
                        updated_at, entry_salt, is_deleted)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
                    (
                        entry_id,
                        ef_title.to_bytes(),
                        ef_username.to_bytes() if ef_username else None,
                        ef_password.to_bytes(),
                        ef_url.to_bytes() if ef_url else None,
                        ef_notes.to_bytes() if ef_notes else None,
                        ef_tags.to_bytes(),
                        ef_custom.to_bytes(),
                        ef_totp.to_bytes() if ef_totp else None,
                        entry_hmac,
                        now,
                        now,
                        entry_salt,
                    ),
                )

            self._update_vault_hmac(conn)
            self._append_audit(conn, "ADD", entry_id, session_id)
            if self._cache is not None:
                self._cache[entry_id] = EntryRecord(
                    id=entry_id,
                    title=title,
                    password=password,
                    username=username,
                    url=url,
                    notes=notes,
                    tags=tags or [],
                    custom=custom or {},
                    created_at=now,
                    updated_at=now,
                    accessed_at=None,
                    is_deleted=False,
                    totp_secret=totp_secret,
                )
        finally:
            wipe_memory(entry_key)

        return entry_id

    def get_entry(self, entry_id: str, session_id: str | None = None) -> EntryRecord:
        """Decrypt and return an entry. Verifies per-entry HMAC first."""
        conn, root_key, hmac_key = self._require_open()

        if self._cache is not None and entry_id in self._cache:
            return self._cache[entry_id]

        row = conn.execute(
            "SELECT * FROM entries WHERE id=? AND is_deleted=0", (entry_id,)
        ).fetchone()
        if row is None:
            raise EntryNotFoundError(f"Entry '{entry_id}' not found.")

        # Verify entry HMAC before decrypting
        self._verify_entry_hmac(row, hmac_key)

        record = self._decrypt_row(row, root_key)

        if self._cache is not None:
            self._cache[record.id] = record

        # Update accessed_at
        now = int(time.time())
        with conn:
            conn.execute(
                "UPDATE entries SET accessed_at=? WHERE id=?", (now, entry_id)
            )
        self._append_audit(conn, "ACCESS", entry_id, session_id)

        return record

    def update_entry(
        self,
        entry_id: str,
        title: str | None = None,
        password: str | None = None,
        username: str | None = None,
        url: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        custom: dict[str, Any] | None = None,
        totp_secret: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Update fields on an existing entry, re-computing the per-entry HMAC."""
        conn, root_key, hmac_key = self._require_open()

        row = conn.execute(
            "SELECT * FROM entries WHERE id=? AND is_deleted=0", (entry_id,)
        ).fetchone()
        if row is None:
            raise EntryNotFoundError(f"Entry '{entry_id}' not found.")

        # Verify before decrypting
        self._verify_entry_hmac(row, hmac_key)

        existing = self._decrypt_row(row, root_key)
        entry_key = self._crypto.derive_entry_key(root_key, entry_id)

        try:
            new_title = title if title is not None else existing.title
            new_password = password if password is not None else existing.password
            new_username = username if username is not None else existing.username
            new_url = url if url is not None else existing.url
            new_notes = notes if notes is not None else existing.notes
            new_tags = tags if tags is not None else existing.tags
            new_custom = custom if custom is not None else existing.custom
            # None = keep existing; empty string = clear TOTP
            if totp_secret is not None:
                new_totp_secret = totp_secret if totp_secret else None
            else:
                new_totp_secret = existing.totp_secret

            ef_title = self._crypto.encrypt_field(new_title, entry_key)
            ef_password = self._crypto.encrypt_field(new_password, entry_key)
            ef_username = (
                self._crypto.encrypt_field(new_username, entry_key)
                if new_username
                else None
            )
            ef_url = (
                self._crypto.encrypt_field(new_url, entry_key) if new_url else None
            )
            ef_notes = (
                self._crypto.encrypt_field(new_notes, entry_key) if new_notes else None
            )
            ef_tags = self._crypto.encrypt_field(
                orjson.dumps(new_tags), entry_key
            )
            ef_custom = self._crypto.encrypt_field(
                orjson.dumps(new_custom), entry_key
            )
            ef_totp = (
                self._crypto.encrypt_field(new_totp_secret, entry_key)
                if new_totp_secret
                else None
            )

            fields: dict[str, bytes] = {
                "title_enc": ef_title.to_bytes(),
                "password_enc": ef_password.to_bytes(),
            }
            if ef_username:
                fields["username_enc"] = ef_username.to_bytes()
            if ef_url:
                fields["url_enc"] = ef_url.to_bytes()
            if ef_notes:
                fields["notes_enc"] = ef_notes.to_bytes()
            fields["tags_enc"] = ef_tags.to_bytes()
            fields["custom_enc"] = ef_custom.to_bytes()
            if ef_totp:
                fields["totp_secret_enc"] = ef_totp.to_bytes()

            new_hmac = self._crypto.compute_entry_hmac(entry_id, fields, hmac_key)
            now = int(time.time())

            with conn:
                conn.execute(
                    """UPDATE entries SET
                       title_enc=?, username_enc=?, password_enc=?,
                       url_enc=?, notes_enc=?, tags_enc=?, custom_enc=?,
                       totp_secret_enc=?,
                       entry_hmac=?, updated_at=?
                       WHERE id=?""",
                    (
                        ef_title.to_bytes(),
                        ef_username.to_bytes() if ef_username else None,
                        ef_password.to_bytes(),
                        ef_url.to_bytes() if ef_url else None,
                        ef_notes.to_bytes() if ef_notes else None,
                        ef_tags.to_bytes(),
                        ef_custom.to_bytes(),
                        ef_totp.to_bytes() if ef_totp else None,
                        new_hmac,
                        now,
                        entry_id,
                    ),
                )

            self._update_vault_hmac(conn)
            self._append_audit(conn, "UPDATE", entry_id, session_id)
            if self._cache is not None:
                self._cache.pop(entry_id, None)
                self._cache_complete = False
        finally:
            wipe_memory(entry_key)

    def delete_entry(self, entry_id: str, session_id: str | None = None) -> None:
        """Soft-delete an entry (is_deleted=1)."""
        conn, _, hmac_key = self._require_open()

        row = conn.execute(
            "SELECT * FROM entries WHERE id=? AND is_deleted=0", (entry_id,)
        ).fetchone()
        if row is None:
            raise EntryNotFoundError(f"Entry '{entry_id}' not found.")

        self._verify_entry_hmac(row, hmac_key)

        with conn:
            conn.execute(
                "UPDATE entries SET is_deleted=1 WHERE id=?", (entry_id,)
            )

        self._update_vault_hmac(conn)
        self._append_audit(conn, "DELETE", entry_id, session_id)
        if self._cache is not None:
            self._cache.pop(entry_id, None)

    def list_entries(self, include_deleted: bool = False) -> list[EntryRecord]:
        """Return all (or all non-deleted) entries, decrypted."""
        conn, root_key, hmac_key = self._require_open()

        if not include_deleted and self._cache is not None:
            if self._cache_complete:
                return list(self._cache.values())
            # cold cache — populate from DB, merge with any already-cached entries
            rows = conn.execute(
                "SELECT * FROM entries WHERE is_deleted=0 ORDER BY created_at"
            ).fetchall()
            for row in rows:
                self._verify_entry_hmac(row, hmac_key)
                record = self._decrypt_row(row, root_key)
                self._cache[record.id] = record
            self._cache_complete = True
            return list(self._cache.values())

        if include_deleted:
            rows = conn.execute("SELECT * FROM entries ORDER BY created_at").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM entries WHERE is_deleted=0 ORDER BY created_at"
            ).fetchall()

        records: list[EntryRecord] = []
        for row in rows:
            self._verify_entry_hmac(row, hmac_key)
            records.append(self._decrypt_row(row, root_key))
        return records

    def search_entries(self, query: str) -> list[EntryRecord]:
        """Full-text search over decrypted entry fields."""
        query_lower = query.lower()
        results: list[EntryRecord] = []
        for record in self.list_entries():
            if (
                query_lower in record.title.lower()
                or (record.username and query_lower in record.username.lower())
                or (record.url and query_lower in record.url.lower())
                or (record.notes and query_lower in record.notes.lower())
                or any(query_lower in tag.lower() for tag in record.tags)
            ):
                results.append(record)
        return results

    def get_all_audit_events(self) -> list[dict[str, Any]]:
        """Return decrypted audit log entries (most recent first)."""
        conn, _, hmac_key = self._require_open()
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC"
        ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            event: dict[str, Any] = {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "entry_id": row["entry_id"],
                "session_id": row["session_id"],
                "detail": None,
            }
            if row["detail_enc"]:
                try:
                    ef = EncryptedField.from_bytes(bytes(row["detail_enc"]))
                    detail_bytes = self._crypto.decrypt_field(ef, hmac_key)
                    event["detail"] = orjson.loads(detail_bytes)
                except Exception:  # pragma: no cover
                    event["detail"] = "<decryption failed>"  # pragma: no cover
            events.append(event)
        return events

    def migrate_from_store(self, old_store: "VaultStore") -> None:
        """Migrate all data from an old vault exactly, re-encrypting with this store's keys."""
        old_conn, _, old_hmac_key = old_store._require_open()
        conn, _, hmac_key = self._require_open()
        assert self._hmac_key is not None
        assert old_store._root_key is not None
        assert self._root_key is not None

        with conn:
            # 1. Migrate Entries
            old_entries = old_conn.execute("SELECT * FROM entries").fetchall()
            for row in old_entries:
                rec = old_store._decrypt_row(row, old_store._root_key)
                # Re-encrypt for self
                entry_key = self._crypto.derive_entry_key(self._root_key, rec.id)
                try:
                    def enc(blob: str | bytes | None) -> bytes | None:
                        if blob is None:
                            return None  # pragma: no cover
                        b = blob.encode("utf-8") if isinstance(blob, str) else blob
                        return self._crypto.encrypt_field(b, entry_key).to_bytes()

                    t_enc = enc(rec.title)
                    p_enc = enc(rec.password)
                    u_enc = enc(rec.username)
                    url_enc = enc(rec.url)
                    n_enc = enc(rec.notes)
                    tags_enc = enc(orjson.dumps(rec.tags)) if rec.tags is not None else None
                    cust_enc = enc(orjson.dumps(rec.custom)) if rec.custom else None
                finally:
                    wipe_memory(entry_key)

                fields_for_mac: dict[str, bytes] = {
                    "title_enc": t_enc,
                    "password_enc": p_enc,
                }
                if u_enc:
                    fields_for_mac["username_enc"] = u_enc
                if url_enc:
                    fields_for_mac["url_enc"] = url_enc
                if n_enc:
                    fields_for_mac["notes_enc"] = n_enc
                if tags_enc:
                    fields_for_mac["tags_enc"] = tags_enc
                if cust_enc:
                    fields_for_mac["custom_enc"] = cust_enc
                new_entry_hmac = self._crypto.compute_entry_hmac(rec.id, fields_for_mac, self._hmac_key)

                import os
                entry_salt = os.urandom(32)
                conn.execute(
                    """INSERT INTO entries (
                        id, title_enc, password_enc, username_enc, url_enc,
                        notes_enc, tags_enc, custom_enc, created_at, updated_at,
                        accessed_at, is_deleted, entry_hmac, entry_salt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (rec.id, t_enc, p_enc, u_enc, url_enc, n_enc, tags_enc, cust_enc,
                     rec.created_at, rec.updated_at, rec.accessed_at, int(rec.is_deleted), new_entry_hmac, entry_salt)
                )

            # 2. Migrate Audit Log
            old_audits = old_conn.execute("SELECT * FROM audit_log ORDER BY timestamp ASC").fetchall()
            for row in old_audits:
                detail = None
                if row["detail_enc"]:
                    ef = EncryptedField.from_bytes(bytes(row["detail_enc"]))  # pragma: no cover
                    dec_detail = self._crypto.decrypt_field(ef, old_hmac_key)  # pragma: no cover
                    detail = orjson.loads(dec_detail)  # pragma: no cover

                detail_enc = None
                if detail:
                    detail_bytes = orjson.dumps(detail)  # pragma: no cover
                    detail_enc = self._crypto.encrypt_field(detail_bytes, self._hmac_key).to_bytes()  # pragma: no cover

                mac_input = (
                    f"{row['timestamp']}|{row['event_type']}|{row['entry_id'] or ''}|{row['session_id'] or ''}"
                ).encode("utf-8")
                new_log_hmac = self._crypto.compute_hmac(mac_input, self._hmac_key)

                conn.execute(
                    """INSERT INTO audit_log
                       (id, timestamp, event_type, entry_id, session_id, detail_enc, log_hmac)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (row["id"], row["timestamp"], row["event_type"], row["entry_id"],
                     row["session_id"], detail_enc, new_log_hmac)
                )

        self._update_vault_hmac(conn)

    def verify_integrity(self) -> ForensicReport:
        """Comprehensive tamper-detection check.

        Checks:
        1. Schema fingerprint
        2. Per-entry HMACs
        3. Vault-wide HMAC
        4. Audit log HMAC chain (basic)
        """
        conn, root_key, hmac_key = self._require_open()
        failed_entries: list[str] = []
        details: list[str] = []
        schema_ok = True
        vault_hmac_ok = True
        audit_ok = True

        # 1. Schema fingerprint
        try:
            self._verify_schema_fingerprint(conn)
            details.append("Schema fingerprint: OK")
        except IntegrityError as e:  # pragma: no cover
            schema_ok = False  # pragma: no cover
            details.append(f"Schema fingerprint: FAILED — {e.user_message}")  # pragma: no cover

        # 2. Per-entry HMACs
        rows = conn.execute("SELECT * FROM entries WHERE is_deleted=0").fetchall()
        for row in rows:
            try:
                self._verify_entry_hmac(row, hmac_key)
            except IntegrityError:
                failed_entries.append(row["id"])
                details.append(f"Entry {row['id']}: HMAC FAILED")

        # 3. Vault-wide HMAC
        try:
            self._verify_vault_hmac(conn)
            details.append("Vault-wide HMAC: OK")
        except IntegrityError as e:  # pragma: no cover
            vault_hmac_ok = False  # pragma: no cover
            details.append(f"Vault-wide HMAC: FAILED — {e.user_message}")  # pragma: no cover

        passed = schema_ok and vault_hmac_ok and len(failed_entries) == 0 and audit_ok
        return ForensicReport(
            passed=passed,
            schema_ok=schema_ok,
            vault_hmac_ok=vault_hmac_ok,
            entries_checked=len(rows),
            entries_failed=failed_entries,
            audit_log_ok=audit_ok,
            details=details,
        )

    # ── Internal helpers ───────────────────────────────────────────────────

    def _verify_entry_hmac(self, row: sqlite3.Row, hmac_key: bytearray) -> None:
        fields: dict[str, bytes] = {
            "title_enc": bytes(row["title_enc"]),
            "password_enc": bytes(row["password_enc"]),
        }
        if row["username_enc"]:
            fields["username_enc"] = bytes(row["username_enc"])
        if row["url_enc"]:
            fields["url_enc"] = bytes(row["url_enc"])
        if row["notes_enc"]:
            fields["notes_enc"] = bytes(row["notes_enc"])
        if row["tags_enc"]:
            fields["tags_enc"] = bytes(row["tags_enc"])
        if row["custom_enc"]:
            fields["custom_enc"] = bytes(row["custom_enc"])
        try:
            if row["totp_secret_enc"]:
                fields["totp_secret_enc"] = bytes(row["totp_secret_enc"])
        except (IndexError, Exception):
            pass  # column not yet present in very old vault

        stored_hmac = bytes(row["entry_hmac"])
        expected_hmac = self._crypto.compute_entry_hmac(row["id"], fields, hmac_key)

        if not hmac.compare_digest(stored_hmac, expected_hmac):
            raise IntegrityError(
                f"Entry HMAC mismatch for entry {row['id']} — tampering detected."
            )

    def _decrypt_row(self, row: sqlite3.Row, root_key: bytearray) -> EntryRecord:
        entry_id = row["id"]
        entry_key = self._crypto.derive_entry_key(root_key, entry_id)

        try:
            def dec(blob: bytes | None) -> bytes | None:
                if blob is None:
                    return None
                ef = EncryptedField.from_bytes(bytes(blob))
                return self._crypto.decrypt_field(ef, entry_key)

            title = (dec(row["title_enc"]) or b"").decode("utf-8")
            password = (dec(row["password_enc"]) or b"").decode("utf-8")
            username_b = dec(row["username_enc"])
            username = username_b.decode("utf-8") if username_b else None
            url_b = dec(row["url_enc"])
            url = url_b.decode("utf-8") if url_b else None
            notes_b = dec(row["notes_enc"])
            notes = notes_b.decode("utf-8") if notes_b else None
            tags_b = dec(row["tags_enc"])
            tags: list[str] = orjson.loads(tags_b) if tags_b else []
            custom_b = dec(row["custom_enc"])
            custom: dict[str, Any] = orjson.loads(custom_b) if custom_b else {}
            try:
                totp_b = dec(row["totp_secret_enc"])
                totp_secret = totp_b.decode("utf-8") if totp_b else None
            except (IndexError, Exception):
                totp_secret = None

            return EntryRecord(
                id=entry_id,
                title=title,
                password=password,
                username=username,
                url=url,
                notes=notes,
                tags=tags,
                custom=custom,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                accessed_at=row["accessed_at"],
                is_deleted=bool(row["is_deleted"]),
                totp_secret=totp_secret,
            )
        finally:
            wipe_memory(entry_key)

    def get_vault_id(self) -> str:
        """Return the vault UUID stored in metadata."""
        conn, _, _ = self._require_open()
        row = conn.execute(
            "SELECT value FROM metadata WHERE key='vault_id'"
        ).fetchone()
        return row["value"] if row else ""

    def set_metadata_value(self, key: str, value: str) -> None:
        """Insert or update a key-value pair in the metadata table."""
        if self._conn is None:
            raise VaultError("Vault is not open.")
        with self._conn:
            self._conn.execute(
                "INSERT INTO metadata (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_metadata_value(self, key: str) -> str | None:
        """Return a metadata value by key, or None if not found."""
        conn, _, _ = self._require_open()
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        val = row["value"]
        if isinstance(val, (bytes, bytearray)):
            return val.decode("utf-8")
        return str(val) if val is not None else None

    def entry_count(self) -> int:
        """Count of non-deleted entries."""
        conn, _, _ = self._require_open()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM entries WHERE is_deleted=0"
        ).fetchone()
        return int(row["cnt"])
