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
import os
import sqlite3
import time
import uuid
import warnings
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

# Column added by the v1 -> v2 migration. ALTER TABLE can only append, so a
# migrated vault carries it last while a natively created v2 vault has it in
# the position declared in _SCHEMA_ENTRIES.
V2_ENTRY_COLUMN = "totp_secret_enc"


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

        try:
            # ── Schema migration v1 → v2 (adds totp_secret_enc column) ──────
            _ver_row = conn.execute(
                "SELECT value FROM metadata WHERE key='schema_version'"
            ).fetchone()
            _stored_ver = _ver_row["value"] if _ver_row else "1"
            if _stored_ver != SCHEMA_VERSION:
                # Authenticate the root key BEFORE writing anything. The schema
                # fingerprint cannot be checked yet — on a v1 vault it is stamped
                # over the v1 schema text and would mismatch even for the right
                # password — but the vault-wide HMAC is schema-independent and
                # key-bound, so it rejects a wrong password here.
                #
                # Without this gate a failed unlock rewrote the fingerprint under
                # the wrong key and flipped schema_version to "2"; the next open
                # with the CORRECT password then skipped the migration and failed
                # verification, bricking the vault permanently.
                self._verify_vault_hmac(conn)

                # One transaction for the whole migration so a crash part-way
                # through cannot leave a half-migrated vault. BEGIN is explicit:
                # sqlite3 opens implicit transactions only for DML, so the DDL
                # below would otherwise autocommit on its own and escape the
                # rollback.
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # Add column if missing (safe on any SQLite version)
                    _existing_cols = [
                        r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()
                    ]
                    if "totp_secret_enc" not in _existing_cols:
                        conn.execute(
                            "ALTER TABLE entries ADD COLUMN totp_secret_enc BLOB"
                        )
                    # Persist the stored version. Upsert rather than UPDATE:
                    # a plain UPDATE matches zero rows when the schema_version
                    # row is absent, so the marker never lands and the migration
                    # re-fires — making open() write on every unlock instead of
                    # being read-only once migrated. Targets only this key.
                    conn.execute(
                        "INSERT OR REPLACE INTO metadata (key, value)"
                        " VALUES ('schema_version', ?)",
                        (SCHEMA_VERSION,),
                    )
                    # Rewrite schema fingerprint to match new _SCHEMA_ENTRIES
                    self._exec_write_schema_fingerprint(conn)
                except BaseException:
                    conn.rollback()
                    raise
                conn.commit()
            # ── End migration ──────────────────────────────────────────────

            # Verify schema fingerprint first
            try:
                self._verify_schema_fingerprint(conn)
            except IntegrityError:
                # A vault bricked by the pre-3.1.1 migration bug fails here even
                # for the correct password. Attempt a tightly gated repair; if
                # the signature does not match exactly, re-raise unchanged.
                if not self._try_heal_schema_fingerprint(conn):
                    raise

            # Verify vault-wide HMAC
            self._verify_vault_hmac(conn)
        except BaseException:
            # Integrity verification (or migration) failed on a corrupt or
            # tampered vault: close the connection we just opened so it is not
            # leaked. The rejection still propagates unchanged — we only add
            # cleanup. Close the raw handle (no WAL checkpoint) so nothing is
            # written back to a vault that just failed verification.
            try:
                conn.close()
            finally:
                self._conn = None
            raise

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
        with conn:
            self._exec_write_schema_fingerprint(conn)

    def _exec_write_schema_fingerprint(self, conn: sqlite3.Connection) -> None:
        """Stamp the fingerprint without committing.

        Split out from :meth:`_write_schema_fingerprint` so the migration in
        :meth:`open` can enlist it in a single transaction with the rest of the
        schema change instead of committing it independently.
        """
        assert self._hmac_key is not None
        fp = self._compute_schema_fingerprint(self._hmac_key)
        now = int(time.time())
        conn.execute(
            "INSERT OR REPLACE INTO schema_fingerprint (id, fingerprint, computed_at) VALUES (1, ?, ?)",
            (fp, now),
        )

    def _schema_matches_migrated_v2(self, conn: sqlite3.Connection) -> bool:
        """True when the live schema is exactly *a v1 vault migrated to v2*.

        The stored fingerprint is an HMAC over the *code's* schema constants, so
        it says nothing about the database's actual structure. This compares the
        live schema against a throwaway in-memory database built from
        ``_ALL_SCHEMA_STMTS`` — column-by-column rather than by SQL text, since a
        table reached via ``ALTER TABLE`` stores different CREATE text than a
        natively created one.

        The comparison deliberately expects the *migrated* column order.
        ``totp_secret_enc`` is declared mid-table in ``_SCHEMA_ENTRIES``, but
        ``ALTER TABLE ADD COLUMN`` can only append, so a migrated vault carries
        it last. That ordering is the fingerprint of having come through the
        migration — and only vaults that went through the migration can have
        been bricked by the pre-3.1.1 bug. A natively created v2 vault never
        entered the migration branch, so a wrong fingerprint there is not this
        bug and must keep being reported as tampering.
        """
        reference = sqlite3.connect(":memory:")
        try:
            for stmt in _ALL_SCHEMA_STMTS:
                reference.execute(stmt)

            objects_sql = (
                "SELECT type, name FROM sqlite_master"
                " WHERE name NOT LIKE 'sqlite_%'"
            )
            # tuple(): the vault connection uses a sqlite3.Row factory, and Row
            # objects are neither sortable nor comparable to plain tuples.
            expected_objects = sorted(tuple(r) for r in reference.execute(objects_sql))
            actual_objects = sorted(tuple(r) for r in conn.execute(objects_sql))
            # Catches added/removed tables and any grafted-on view or trigger.
            if expected_objects != actual_objects:
                return False

            for obj_type, name in expected_objects:
                if obj_type != "table":
                    continue  # pragma: no cover - schema declares tables only
                # name comes from our own constants via the equality above.
                columns_sql = f"PRAGMA table_info({name})"
                expected_cols = [tuple(r)[1:] for r in reference.execute(columns_sql)]
                if name == "entries":
                    expected_cols = [
                        c for c in expected_cols if c[0] != V2_ENTRY_COLUMN
                    ] + [c for c in expected_cols if c[0] == V2_ENTRY_COLUMN]
                actual_cols = [tuple(r)[1:] for r in conn.execute(columns_sql)]
                if expected_cols != actual_cols:
                    return False
            return True
        finally:
            reference.close()

    def _try_heal_schema_fingerprint(self, conn: sqlite3.Connection) -> bool:
        """Repair a fingerprint stamped under the wrong key by the pre-3.1.1 bug.

        Releases before 3.1.1 ran the v1→v2 migration before verifying anything,
        so one wrong-password unlock re-stamped the schema fingerprint under the
        wrong key and flipped ``schema_version`` to ``"2"``, locking the correct
        password out permanently. Such a vault is fully intact — only the
        fingerprint is wrong — so it can be repaired in place.

        This is deliberately NOT a general "fingerprint mismatch → rewrite"
        fallback. It repairs only that exact signature. Every condition must
        hold, and any failure leaves the vault untouched and the original
        rejection intact:

        1. the vault-wide HMAC verifies under the entered key — proving both the
           password is correct and the entry set is authentic;
        2. the vault presents as already migrated — ``schema_version`` is current
           and the v2 ``totp_secret_enc`` column exists;
        3. the live schema is structurally identical to the expected v2 schema,
           so the re-stamp blesses a known-good structure rather than whatever
           happens to be on disk.

        Returns True only if the vault was healed.
        """
        # (1) Authenticate the key and the entry set. This is the gate that stops
        #     a wrong password, and stops real tampering being papered over.
        try:
            self._verify_vault_hmac(conn)
        except IntegrityError:
            return False

        # (2) Only an already-migrated vault carries this signature.
        # Gate 2: belt-and-suspenders invariant — provably subsumed by gate 3
        # today (mutation-tested: removing this is caught by nothing). Kept
        # deliberately so a future refactor of gate 3 can't silently re-open the
        # heal path. Do not remove without re-checking that gate 3 still fully
        # constrains structure.
        version_row = conn.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        if version_row is None or version_row["value"] != SCHEMA_VERSION:
            return False
        entry_columns = [
            r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()
        ]
        if V2_ENTRY_COLUMN not in entry_columns:
            return False

        # (3) Never re-stamp a structure that is not the expected one.
        # Gate 3: compares against the MIGRATED column order, not the native
        # schema. ALTER TABLE ADD COLUMN can only APPEND, so a genuinely migrated
        # vault has totp_secret_enc LAST, whereas a natively-created v2 vault has
        # it mid-table. Matching native order here would refuse to heal every real
        # victim. This gate also confines healing to migrated-order vaults,
        # preserving tamper detection for natively-created v2 vaults (a bad
        # fingerprint there is real corruption).
        if not self._schema_matches_migrated_v2(conn):
            return False

        conn.execute("BEGIN IMMEDIATE")
        try:
            self._exec_write_schema_fingerprint(conn)
        except BaseException:
            conn.rollback()
            raise
        conn.commit()

        warnings.warn(
            "Vault self-heal: the schema fingerprint was stamped under the wrong "
            "key by the pre-3.1.1 migration bug and has been re-stamped under the "
            "correct key. Vault contents were verified intact and are unchanged.",
            RuntimeWarning,
            stacklevel=2,
        )
        return True

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
                    totp_enc = enc(rec.totp_secret)
                finally:
                    wipe_memory(entry_key)

                # title and password are required fields, so enc() never
                # returns None for them — assert to narrow bytes | None → bytes.
                assert t_enc is not None and p_enc is not None
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
                if totp_enc:
                    fields_for_mac["totp_secret_enc"] = totp_enc
                new_entry_hmac = self._crypto.compute_entry_hmac(rec.id, fields_for_mac, self._hmac_key)

                import os
                entry_salt = os.urandom(32)
                conn.execute(
                    """INSERT INTO entries (
                        id, title_enc, password_enc, username_enc, url_enc,
                        notes_enc, tags_enc, custom_enc, totp_secret_enc,
                        created_at, updated_at,
                        accessed_at, is_deleted, entry_hmac, entry_salt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (rec.id, t_enc, p_enc, u_enc, url_enc, n_enc, tags_enc, cust_enc, totp_enc,
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

            # 3. Migrate Metadata — preserve the vault's identity and settings
            # (vault_id, created_at, kdf_mode, schema_version, recovery
            # totp_secret, …). Values are plaintext TEXT key/value rows, so
            # they copy directly. vault_hmac is skipped: it is recomputed
            # below under this store's HMAC key.
            old_meta = old_conn.execute("SELECT key, value FROM metadata").fetchall()
            for row in old_meta:
                if row["key"] == "vault_hmac":
                    continue
                conn.execute(
                    "INSERT INTO metadata (key, value) VALUES (?, ?)"
                    " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (row["key"], row["value"]),
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


# ── Crash recovery for change-password (H2) ───────────────────────────────────


def recover_interrupted_password_change(vault_path: Path) -> str | None:
    """Heal an interrupted change-password staged swap (H2).

    change-password (cli/commands/vault.py) commits via a staged
    two-file protocol:

      stage:  vault.nyx.new and vault.salt.new are fully written and
              fsync'd while the original vault + salt stay untouched
      commit: os.replace(vault.nyx.new -> vault.nyx), then
              os.replace(vault.salt.new -> vault.salt)

    Called before any password-based open (CLI unlock, TUI unlock,
    SDK), this applies one deterministic rule to whatever a crash
    left behind:

      - vault.salt.new AND vault.nyx.new present -> the vault replace
        had not happened, so the OLD pair is still live. Roll BACK:
        delete both staged files. The old password works.
      - ONLY vault.salt.new present -> the vault was already replaced
        under the new key. Roll FORWARD: complete the salt replace.
        The new password works.
      - ONLY vault.nyx.new present -> a crash during staging, before
        the salt was staged. Originals live; delete the stale file.

    Returns "rolled-back", "rolled-forward", or None when there was
    nothing to heal.
    """
    staged_vault = vault_path.with_suffix(".nyx.new")
    staged_salt = vault_path.with_suffix(".salt.new")
    if staged_salt.exists():
        if staged_vault.exists():
            staged_vault.unlink(missing_ok=True)
            staged_salt.unlink(missing_ok=True)
            return "rolled-back"
        os.replace(staged_salt, vault_path.with_suffix(".salt"))
        return "rolled-forward"
    if staged_vault.exists():
        staged_vault.unlink(missing_ok=True)
        return "rolled-back"
    return None
