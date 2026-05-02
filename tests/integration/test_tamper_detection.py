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
