"""Regression tests for the schema-v1 → v2 migration in ``VaultStore.open()``.

Core invariant: **a failed unlock must not write to the vault.**

Before the fix, ``open()`` ran the v1→v2 migration — ``ALTER TABLE``, the
``schema_version`` bump, and a schema-fingerprint rewrite — in its own
auto-committing transactions *before* verifying either integrity tag. The
fingerprint is ``HMAC(schema_text, hmac_key)`` and ``hmac_key`` is derived from
the password, so a single wrong-password attempt on a v1 vault stamped a
fingerprint under the wrong key and flipped ``schema_version`` to ``"2"``. The
next open with the *correct* password then skipped the migration, went straight
to verification, and failed with "structural tampering detected" — permanently.

These tests drive the same code path ``cli/commands/vault.py`` and ``sdk.py``
use to unlock: ``derive_key(password, salt)`` then ``VaultStore.open()``.
"""
from __future__ import annotations

import hashlib
import shutil
import sqlite3
import time
from pathlib import Path

import pytest

from nyxora.core import vault_store as vs
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.vault_store import SCHEMA_VERSION, VaultStore
from nyxora.utils.exceptions import IntegrityError

GOOD_PASSWORD = "correct-horse-battery-staple"
WRONG_PASSWORD = "wrong-password-typo"

# The exact pre-2.6.0 (schema v1) entries table: identical to v2 minus the
# totp_secret_enc column. Kept verbatim so the v1 fixture is a genuine v1
# vault rather than a v2 vault with a rewritten version marker.
V1_SCHEMA_ENTRIES = """\
CREATE TABLE IF NOT EXISTS entries (
    id           TEXT    PRIMARY KEY,
    title_enc    BLOB    NOT NULL,
    username_enc BLOB,
    password_enc BLOB    NOT NULL,
    url_enc      BLOB,
    notes_enc    BLOB,
    tags_enc     BLOB,
    custom_enc   BLOB,
    entry_hmac   BLOB    NOT NULL,
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL,
    accessed_at  INTEGER,
    entry_salt   BLOB    NOT NULL,
    is_deleted   INTEGER NOT NULL DEFAULT 0
)"""

V1_COLUMNS = [
    "id", "title_enc", "username_enc", "password_enc", "url_enc", "notes_enc",
    "tags_enc", "custom_enc", "entry_hmac", "created_at", "updated_at",
    "accessed_at", "entry_salt", "is_deleted",
]


def _fast_engine() -> CryptoEngine:
    """Argon2 tuned down — these tests exercise ordering, not KDF strength."""
    return CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)


def _attempt_open(path: Path, password: str, salt: bytes) -> VaultStore:
    """Unlock exactly as cli/commands/vault.py and sdk.py do."""
    engine = _fast_engine()
    root_key = engine.derive_key(password, salt)
    store = VaultStore(engine)
    store.open(path, root_key)
    return store


def _vault_digest(path: Path) -> dict[str, str]:
    """SHA-256 of every on-disk byte belonging to the vault.

    The WAL file must be included: the failed-open path closes the raw handle
    without checkpointing, so migration writes land in ``<vault>-wal`` and a
    digest of the main file alone would miss them entirely. ``-shm`` is a
    volatile shared-memory index, rebuildable from the WAL, so it is excluded.
    """
    digests: dict[str, str] = {}
    for candidate in (path, path.with_name(path.name + "-wal")):
        if candidate.exists():
            digests[candidate.name] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return digests


def _version_row(path: Path) -> str | None:
    """Return the stored schema_version, or None if the row is absent."""
    conn = sqlite3.connect(str(path))
    try:
        row = conn.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _read_state(path: Path) -> tuple[str, bytes, list[str]]:
    """Read (schema_version, fingerprint, entries columns) via a fresh handle."""
    conn = sqlite3.connect(str(path))
    try:
        version = conn.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()[0]
        fingerprint = bytes(
            conn.execute(
                "SELECT fingerprint FROM schema_fingerprint WHERE id=1"
            ).fetchone()[0]
        )
        columns = [r[1] for r in conn.execute("PRAGMA table_info(entries)").fetchall()]
        return version, fingerprint, columns
    finally:
        conn.close()


def _make_v1_vault(path: Path, salt: bytes) -> str:
    """Build a genuine schema-v1 vault. Returns the seeded entry's id."""
    engine = _fast_engine()
    root_key = engine.derive_key(GOOD_PASSWORD, salt)

    store = VaultStore(engine)
    store.initialize(path, root_key)
    entry_id = store.add_entry(title="prod-db", password="hunter2", username="svc")
    store.close()

    # Downgrade to v1: drop totp_secret_enc, set schema_version='1', and stamp
    # the fingerprint over the *v1* schema text using the CORRECT hmac key —
    # which is what a real pre-2.6.0 vault carries.
    hmac_key = engine.derive_hmac_key(engine.derive_key(GOOD_PASSWORD, salt))
    v1_statements = [
        V1_SCHEMA_ENTRIES,
        vs._SCHEMA_METADATA,
        vs._SCHEMA_AUDIT,
        vs._SCHEMA_FINGERPRINT,
    ]
    v1_fingerprint = engine.compute_hmac(
        "||".join(sorted(v1_statements)).encode("utf-8"), hmac_key
    )

    columns = ", ".join(V1_COLUMNS)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            f"""
            PRAGMA foreign_keys=OFF;
            BEGIN;
            ALTER TABLE entries RENAME TO entries_v2_tmp;
            {V1_SCHEMA_ENTRIES};
            INSERT INTO entries ({columns}) SELECT {columns} FROM entries_v2_tmp;
            DROP TABLE entries_v2_tmp;
            UPDATE metadata SET value='1' WHERE key='schema_version';
            COMMIT;
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO schema_fingerprint (id, fingerprint, computed_at)"
            " VALUES (1, ?, ?)",
            (v1_fingerprint, int(time.time())),
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    version, _, columns_now = _read_state(path)
    assert version == "1", "fixture is not a v1 vault"
    assert "totp_secret_enc" not in columns_now, "fixture still has the v2 column"
    return entry_id


@pytest.fixture()
def v1_vault(tmp_path: Path) -> tuple[Path, bytes, str]:
    path = tmp_path / "v1.nyx"
    salt = _fast_engine().generate_salt()
    entry_id = _make_v1_vault(path, salt)
    return path, salt, entry_id


def test_failed_unlock_does_not_touch_v1_vault_bytes(v1_vault):
    """A wrong password must not write a single byte to a v1 vault."""
    path, salt, _ = v1_vault
    before = _vault_digest(path)
    version_before, fingerprint_before, columns_before = _read_state(path)

    with pytest.raises(IntegrityError):
        _attempt_open(path, WRONG_PASSWORD, salt)

    version_after, fingerprint_after, columns_after = _read_state(path)
    # Logical assertions first — they name exactly what the migration mutated.
    assert version_after == version_before, "schema_version was bumped by a failed unlock"
    assert fingerprint_after == fingerprint_before, (
        "schema fingerprint was rewritten under the WRONG key by a failed unlock — "
        "this permanently bricks the vault"
    )
    assert columns_after == columns_before, "entries table was altered by a failed unlock"
    # The headline invariant.
    assert _vault_digest(path) == before, "failed unlock mutated vault bytes on disk"


def test_v1_vault_still_opens_after_a_failed_attempt(v1_vault):
    """The brick: one typo must not lock the correct password out forever."""
    path, salt, entry_id = v1_vault

    with pytest.raises(IntegrityError):
        _attempt_open(path, WRONG_PASSWORD, salt)

    store = _attempt_open(path, GOOD_PASSWORD, salt)
    try:
        record = store.get_entry(entry_id)
        assert record.title == "prod-db"
        assert record.password == "hunter2"
        assert record.username == "svc"
    finally:
        store.close()


def test_v1_vault_migrates_on_a_correct_unlock(v1_vault):
    """The migration must still happen — for an authenticated open."""
    path, salt, entry_id = v1_vault
    assert _read_state(path)[0] == "1"

    store = _attempt_open(path, GOOD_PASSWORD, salt)
    try:
        assert store.get_entry(entry_id).password == "hunter2"
    finally:
        store.close()

    version, _, columns = _read_state(path)
    assert version == "2", "correct-password open did not migrate the vault"
    assert "totp_secret_enc" in columns, "migration did not add the v2 column"

    # And it stays openable afterwards.
    store = _attempt_open(path, GOOD_PASSWORD, salt)
    store.close()


def test_v2_vault_unaffected_by_wrong_password(tmp_path: Path):
    """Control: a v2 vault never enters the migration branch.

    This also validates the byte-digest method itself — if reading a vault with
    the wrong password perturbed the file for unrelated reasons (WAL churn,
    pragma side effects), this control would fail too.
    """
    path = tmp_path / "v2.nyx"
    engine = _fast_engine()
    salt = engine.generate_salt()
    root_key = engine.derive_key(GOOD_PASSWORD, salt)

    store = VaultStore(engine)
    store.initialize(path, root_key)
    entry_id = store.add_entry(title="prod-db", password="hunter2")
    store.close()

    before = _vault_digest(path)
    with pytest.raises(IntegrityError):
        _attempt_open(path, WRONG_PASSWORD, salt)
    assert _vault_digest(path) == before, "failed unlock mutated a v2 vault"

    store = _attempt_open(path, GOOD_PASSWORD, salt)
    try:
        assert store.get_entry(entry_id).password == "hunter2"
    finally:
        store.close()


def test_repeated_failed_attempts_do_not_degrade_v1_vault(v1_vault):
    """Several typos in a row must still leave the vault openable."""
    path, salt, entry_id = v1_vault
    before = _vault_digest(path)

    for _ in range(3):
        with pytest.raises(IntegrityError):
            _attempt_open(path, WRONG_PASSWORD, salt)

    assert _vault_digest(path) == before
    store = _attempt_open(path, GOOD_PASSWORD, salt)
    try:
        assert store.get_entry(entry_id).title == "prod-db"
    finally:
        store.close()


def test_missing_schema_version_row_is_not_a_write_trigger(tmp_path: Path):
    """A v2 vault whose schema_version row is gone falls into the migration
    branch (``_stored_ver`` defaults to ``"1"``). A wrong password there must
    still not write."""
    path = tmp_path / "noversion.nyx"
    engine = _fast_engine()
    salt = engine.generate_salt()
    root_key = engine.derive_key(GOOD_PASSWORD, salt)

    store = VaultStore(engine)
    store.initialize(path, root_key)
    store.add_entry(title="prod-db", password="hunter2")
    store.close()

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("DELETE FROM metadata WHERE key='schema_version'")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    before = _vault_digest(path)
    with pytest.raises(IntegrityError):
        _attempt_open(path, WRONG_PASSWORD, salt)
    assert _vault_digest(path) == before, (
        "failed unlock wrote to a vault with a missing schema_version row"
    )


def test_v1_fixture_is_genuinely_v1(tmp_path: Path):
    """Guard the fixture itself — a toothless fixture makes every test above
    vacuous."""
    path = tmp_path / "fixture.nyx"
    salt = _fast_engine().generate_salt()
    _make_v1_vault(path, salt)

    version, fingerprint, columns = _read_state(path)
    assert version == "1"
    assert "totp_secret_enc" not in columns
    assert len(fingerprint) == 64  # HMAC-SHA512

    # The stored fingerprint is over the v1 schema text, so it must NOT match
    # the current (v2) schema statements — otherwise the migration is a no-op
    # and the regression could not occur.
    engine = _fast_engine()
    hmac_key = engine.derive_hmac_key(engine.derive_key(GOOD_PASSWORD, salt))
    v2_fingerprint = engine.compute_hmac(
        "||".join(sorted(vs._ALL_SCHEMA_STMTS)).encode("utf-8"), hmac_key
    )
    assert fingerprint != v2_fingerprint


_WRITE_KEYWORDS = ("insert", "update", "delete", "replace", "alter", "drop", "create")


def _open_capturing_sql(
    path: Path, password: str, salt: bytes, monkeypatch: pytest.MonkeyPatch
) -> tuple[VaultStore, list[str]]:
    """Open the vault, returning the SQL ``open()`` itself ran.

    The returned list is a snapshot taken the moment ``open()`` returns.
    Statements from later calls are deliberately excluded — reads such as
    ``get_entry`` legitimately write (``accessed_at`` refresh, audit row), and
    this helper is about whether *opening* mutates the vault.
    """
    statements: list[str] = []
    original_connect = VaultStore._connect

    def traced(self: VaultStore, p: Path) -> sqlite3.Connection:
        conn = original_connect(self, p)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(VaultStore, "_connect", traced)
    engine = _fast_engine()
    store = VaultStore(engine)
    store.open(path, engine.derive_key(password, salt))
    return store, list(statements)


def _write_statements(statements: list[str]) -> list[str]:
    out = []
    for sql in statements:
        head = sql.strip().split(None, 1)[0].lower() if sql.strip() else ""
        if head in _WRITE_KEYWORDS:
            out.append(" ".join(sql.split())[:80])
    return out


def test_schema_version_persists_after_first_open(tmp_path: Path, monkeypatch):
    """A vault missing its schema_version row must gain one on first unlock,
    and the migration must not re-fire on subsequent unlocks.

    A plain UPDATE matches zero rows when the marker is absent, which left
    open() writing to the vault on *every* successful unlock.
    """
    path = tmp_path / "noversion.nyx"
    engine = _fast_engine()
    salt = engine.generate_salt()

    store = VaultStore(engine)
    store.initialize(path, engine.derive_key(GOOD_PASSWORD, salt))
    entry_id = store.add_entry(title="prod-db", password="hunter2")
    store.close()

    conn = sqlite3.connect(str(path))
    try:
        conn.execute("DELETE FROM metadata WHERE key='schema_version'")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
    assert _version_row(path) is None, "fixture still has a schema_version row"

    # (b) first open with the correct password succeeds...
    store = _attempt_open(path, GOOD_PASSWORD, salt)
    try:
        assert store.get_entry(entry_id).password == "hunter2"
    finally:
        store.close()

    # (c) ...and the marker now exists.
    assert _version_row(path) == SCHEMA_VERSION, (
        "schema_version was not persisted — migration will re-fire on every open"
    )

    # (d) a second open must not migrate again: no writes, no byte churn.
    after_first = _vault_digest(path)
    store, statements = _open_capturing_sql(path, GOOD_PASSWORD, salt, monkeypatch)
    store.close()

    assert _write_statements(statements) == [], (
        "post-migration open executed write statements: "
        f"{_write_statements(statements)}"
    )
    assert _vault_digest(path) == after_first, "second open mutated the vault"
    assert _version_row(path) == SCHEMA_VERSION


def test_migrated_v1_vault_open_is_read_only(v1_vault, monkeypatch):
    """After a v1 vault has been migrated, opening it is a pure read."""
    path, salt, entry_id = v1_vault

    store = _attempt_open(path, GOOD_PASSWORD, salt)  # migrates
    store.close()
    assert _version_row(path) == SCHEMA_VERSION

    version_before, fingerprint_before, columns_before = _read_state(path)

    store, statements = _open_capturing_sql(path, GOOD_PASSWORD, salt, monkeypatch)
    assert store.get_entry(entry_id).title == "prod-db"  # data survived intact
    store.close()

    assert _write_statements(statements) == [], (
        f"re-open of a migrated vault wrote: {_write_statements(statements)}"
    )
    # get_entry refreshes accessed_at and appends an audit row, so raw bytes are
    # expected to move here. Assert instead that the schema state the migration
    # owns — version marker, fingerprint, columns — is untouched.
    version_after, fingerprint_after, columns_after = _read_state(path)
    assert version_after == version_before == SCHEMA_VERSION
    assert fingerprint_after == fingerprint_before
    assert columns_after == columns_before


def test_backup_copy_of_v1_vault_is_independent(v1_vault, tmp_path: Path):
    """Sanity: the fixture is a real file that can be copied and opened."""
    path, salt, entry_id = v1_vault
    copy_path = tmp_path / "copy.nyx"
    shutil.copy2(path, copy_path)

    store = _attempt_open(copy_path, GOOD_PASSWORD, salt)
    try:
        assert store.get_entry(entry_id).title == "prod-db"
    finally:
        store.close()
