import sqlite3

import pytest

from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import VaultStore
from nyxora.utils.exceptions import NyxoraError


def _make_vault(tmp_path, engine, root_key):
    """Helper: create a vault with one entry; return (path, entry_id)."""
    vault_path = tmp_path / "test.nyx"
    store = VaultStore(engine)
    store.initialize(vault_path, root_key)
    eid = store.add_entry("GitHub", "hunter2", username="alice")
    store.close()
    return vault_path, eid


def test_tamper_entry_ciphertext_detected(tmp_path):
    """Corrupting a raw ciphertext field does not affect entry_hmac, so open()
    succeeds but get_entry() detects the mismatch and raises NyxoraError."""
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("test-password", salt)

    try:
        vault_path, eid = _make_vault(tmp_path, engine, root_key)

        conn = sqlite3.connect(str(vault_path))
        conn.execute(
            "UPDATE entries SET password_enc = ? WHERE id = ?",
            (b"\xff" * 64, eid),
        )
        conn.commit()
        conn.close()

        store = VaultStore(engine)
        store.open(vault_path, root_key)  # must succeed — vault-wide HMAC is unaffected
        try:
            with pytest.raises(NyxoraError):
                store.get_entry(eid)
        finally:
            store.close()
    finally:
        wipe_memory(root_key)


def test_tamper_vault_hmac_detected(tmp_path):
    """Corrupting the vault_hmac metadata row is detected at open() time."""
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("test-password", salt)

    try:
        vault_path, _ = _make_vault(tmp_path, engine, root_key)

        conn = sqlite3.connect(str(vault_path))
        conn.execute(
            "UPDATE metadata SET value = ? WHERE key = 'vault_hmac'",
            ("00" * 64,),  # 64-byte all-zero hex string — invalid MAC
        )
        conn.commit()
        conn.close()

        store = VaultStore(engine)
        with pytest.raises(NyxoraError):
            store.open(vault_path, root_key)
    finally:
        wipe_memory(root_key)


def test_tamper_schema_fingerprint_detected(tmp_path):
    """Corrupting the schema_fingerprint row is detected at open() time."""
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("test-password", salt)

    try:
        vault_path, _ = _make_vault(tmp_path, engine, root_key)

        conn = sqlite3.connect(str(vault_path))
        conn.execute(
            "UPDATE schema_fingerprint SET fingerprint = ? WHERE id = 1",
            (b"\x00" * 64,),
        )
        conn.commit()
        conn.close()

        store = VaultStore(engine)
        with pytest.raises(NyxoraError):
            store.open(vault_path, root_key)
    finally:
        wipe_memory(root_key)


def test_open_closes_connection_on_integrity_failure(tmp_path):
    """#8: a vault that fails integrity verification at open() must have its
    DB connection closed — not leaked.

    Two guarantees in one test:
      (a) security behavior intact — the tampered vault is still rejected;
      (b) the connection open() opened is actually closed afterward, verified
          against the real connection object (executing on a closed sqlite3
          connection raises ProgrammingError) — independent of the idempotent
          close() workaround the integrity/H2 tests use to release the leak.
    """
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("test-password", salt)

    try:
        vault_path, _ = _make_vault(tmp_path, engine, root_key)

        # Tamper the vault_hmac so integrity verification raises at open().
        conn = sqlite3.connect(str(vault_path))
        conn.execute(
            "UPDATE metadata SET value = ? WHERE key = 'vault_hmac'",
            ("00" * 64,),
        )
        conn.commit()
        conn.close()

        store = VaultStore(engine)

        # Capture the real connection object open() creates so we can inspect
        # its state directly rather than trusting store._conn or close().
        captured: dict[str, sqlite3.Connection] = {}
        real_connect = store._connect

        def _spy_connect(path):
            c = real_connect(path)
            captured["conn"] = c
            return c

        store._connect = _spy_connect  # type: ignore[method-assign]

        # (a) rejection still happens
        with pytest.raises(NyxoraError):
            store.open(vault_path, root_key)

        # (b) the connection open() opened is actually closed (not leaked)
        assert "conn" in captured, "open() never opened a connection"
        leaked = captured["conn"]
        with pytest.raises(sqlite3.ProgrammingError):
            leaked.execute("SELECT 1")
        assert store._conn is None, "store still references a connection"
    finally:
        wipe_memory(root_key)


def test_open_success_keeps_connection_open(tmp_path):
    """#8 success-path guard: a valid vault still opens cleanly and returns an
    open, usable connection — the leak fix must not touch the normal path."""
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("test-password", salt)

    try:
        vault_path, eid = _make_vault(tmp_path, engine, root_key)

        store = VaultStore(engine)
        store.open(vault_path, root_key)
        try:
            assert store._conn is not None
            store._conn.execute("SELECT 1")  # open and usable
            assert store.get_entry(eid).password == "hunter2"  # normal API works
        finally:
            store.close()
    finally:
        wipe_memory(root_key)
