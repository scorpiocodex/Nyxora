import os
from pathlib import Path

import pytest

from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.vault_store import VaultStore
from nyxora.utils.exceptions import NyxoraError


@pytest.fixture
def crypto():
    return CryptoEngine()

@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "vault.nyx"

def test_vault_init_open(crypto, db_path):
    store = VaultStore(crypto)
    key = bytearray(os.urandom(32))
    store.initialize(db_path, key)

    store.close()

    store2 = VaultStore(crypto)
    store2.open(db_path, key)
    assert store2.entry_count() == 0
    assert store2.get_vault_id() is not None
    store2.close()

def test_vault_open_invalid_path(crypto, db_path):
    store = VaultStore(crypto)
    with pytest.raises(NyxoraError):
        store.open(Path("does_not_exist"), bytearray(32))

def test_vault_crud(crypto, db_path):
    store = VaultStore(crypto)
    key = bytearray(os.urandom(32))
    store.initialize(db_path, key)

    eid = store.add_entry("My Bank", "secure_pass", "user", "https://bank.com")
    assert eid is not None

    rec = store.get_entry(eid)
    assert rec.title == "My Bank"
    assert rec.password == "secure_pass"
    assert rec.username == "user"
    assert rec.url == "https://bank.com"

    entries = store.list_entries()
    assert len(entries) == 1
    assert entries[0].id == eid

    store.update_entry(eid, password="new_pass", notes="Updated notes", tags=["bank", "finance"])
    rec2 = store.get_entry(eid)
    assert rec2.password == "new_pass"
    assert rec2.notes == "Updated notes"
    assert "bank" in rec2.tags

    # Soft delete using delete_entry
    store.delete_entry(eid)
    with pytest.raises(NyxoraError):
        store.get_entry(eid)

    entries_after_del = store.list_entries(include_deleted=False)
    assert len(entries_after_del) == 0

    entries_with_del = store.list_entries(include_deleted=True)
    assert len(entries_with_del) == 1

    events = store.get_all_audit_events()
    assert len(events) >= 3
    action_types = [e["event_type"] for e in events]
    assert "ADD" in action_types
    assert "UPDATE" in action_types
    assert "DELETE" in action_types

    store.close()

def test_vault_integrity(crypto, db_path):
    store = VaultStore(crypto)
    key = bytearray(os.urandom(32))
    store.initialize(db_path, key)

    store.add_entry("Test", "pass")

    report = store.verify_integrity()
    assert report.passed is True
    assert len(report.entries_failed) == 0

    store._conn.execute("UPDATE entries SET password_enc = ?", (b"tampered",))
    store._conn.commit()

    report = store.verify_integrity()
    assert report.passed is False
    assert len(report.details) > 0

    store.close()

def test_vault_search(crypto, db_path):
    store = VaultStore(crypto)
    key = bytearray(os.urandom(32))
    store.initialize(db_path, key)

    store.add_entry("Email Google", "p1", notes="important")
    store.add_entry("Personal Website", "p2", username="scorp")

    # Search
    results = store.search_entries("Google")
    assert len(results) == 1
    assert results[0].title == "Email Google"

    results = store.search_entries("scorp")
    assert len(results) == 1
    assert results[0].username == "scorp"

    store.close()

def test_vault_migrate_from_store(crypto, tmp_path):
    db1 = tmp_path / "old.nyx"
    store1 = VaultStore(crypto)
    key1 = bytearray(os.urandom(32))
    store1.initialize(db1, key1)
    store1.add_entry(
        "ToMigrate", "pass",
        username="u", url="u.com", notes="note", tags=["t"], custom={"c": 1}
    )
    store1.close()

    # Re-open old store read-only
    store1.open(db1, key1)

    # Create new store
    db2 = tmp_path / "new.nyx"
    store2 = VaultStore(crypto)
    key2 = bytearray(os.urandom(32))
    store2.initialize(db2, key2)

    # Migrate
    store2.migrate_from_store(store1)

    # Verify migration
    entries = store2.list_entries()
    assert len(entries) == 1
    assert entries[0].title == "ToMigrate"

    audit = store2.get_all_audit_events()
    # Ensure audit log was copied correctly: The ADD action should be in DB2 now.
    actions = [e["event_type"] for e in audit]
    assert "ADD" in actions

    store1.close()
    store2.close()

def test_change_password_preserves_totp_and_metadata(crypto, tmp_path):
    """C1 regression: change-password must keep TOTP secrets and metadata.

    Drives the real `nyx vault change-password` command (CliRunner with
    the suite's interactive mocks) against a real on-disk vault.
    """
    from unittest.mock import patch

    from typer.testing import CliRunner

    from nyxora.cli.main import app

    vp = tmp_path / "vault.nyx"
    old_key = bytearray(os.urandom(32))

    store = VaultStore(crypto)
    store.initialize(vp, old_key)
    store.add_entry("GitHub", "gh-pass", username="alice")
    store.add_entry(
        "Gmail", "gm-pass", username="bob",
        totp_secret="JBSWY3DPEHPK3PXP",
    )
    # Vault-level recovery TOTP — same path the recovery commands use
    store.set_metadata_value("totp_secret", "JBSWY3DPEHPK3PXP")
    vault_id_before = store.get_vault_id()
    created_at_before = store.get_metadata_value("created_at")
    kdf_mode_before = store.get_metadata_value("kdf_mode")
    store.close()

    runner = CliRunner()
    with patch("questionary.password") as m_pw, \
         patch("nyxora.cli.commands.vault.ui"), \
         patch("nyxora.cli.commands.vault.load_session") as m_load, \
         patch("nyxora.cli.commands.vault.save_session"):
        m_pw.return_value.ask.side_effect = ["NewPass-67890", "NewPass-67890"]
        m_load.return_value = ("session-id", vp, bytearray(old_key))
        result = runner.invoke(app, ["vault", "change-password"])
    assert result.exit_code == 0

    new_salt = vp.with_suffix(".salt").read_bytes()
    new_key = crypto.derive_key("NewPass-67890".encode(), new_salt)

    reopened = VaultStore(crypto)
    reopened.open(vp, new_key)
    assert reopened.get_vault_id() == vault_id_before
    entries = {e.title: e for e in reopened.list_entries()}
    assert entries["GitHub"].password == "gh-pass"
    assert entries["GitHub"].username == "alice"
    assert entries["Gmail"].password == "gm-pass"
    assert entries["Gmail"].username == "bob"
    # Core C1 assertions: both TOTP storage locations survive
    assert entries["Gmail"].totp_secret == "JBSWY3DPEHPK3PXP"
    assert reopened.get_metadata_value("totp_secret") == "JBSWY3DPEHPK3PXP"
    assert reopened.get_metadata_value("created_at") == created_at_before
    assert reopened.get_metadata_value("kdf_mode") == kdf_mode_before
    reopened.close()

    # The old key must no longer open the vault
    stale = VaultStore(crypto)
    with pytest.raises(NyxoraError):
        stale.open(vp, old_key)

def test_change_password_preserves_all_metadata_keys(crypto, tmp_path):
    """Every metadata row survives migration; vault_hmac is recomputed."""
    db1 = tmp_path / "old.nyx"
    store1 = VaultStore(crypto)
    key1 = bytearray(os.urandom(32))
    store1.initialize(db1, key1)
    store1.add_entry("Entry", "pw")
    store1.set_metadata_value("totp_secret", "JBSWY3DPEHPK3PXP")

    meta_before = {
        row["key"]: row["value"]
        for row in store1._conn.execute("SELECT key, value FROM metadata")
    }

    db2 = tmp_path / "new.nyx"
    store2 = VaultStore(crypto)
    key2 = bytearray(os.urandom(32))
    store2.initialize(db2, key2)
    store2.migrate_from_store(store1)
    store1.close()

    meta_after = {
        row["key"]: row["value"]
        for row in store2._conn.execute("SELECT key, value FROM metadata")
    }
    store2.close()

    assert set(meta_after) == set(meta_before)
    for key, value in meta_before.items():
        if key == "vault_hmac":
            continue  # recomputed under the new HMAC key by design
        assert meta_after[key] == value, key

    # The migrated vault must reopen cleanly under its new key
    store3 = VaultStore(crypto)
    store3.open(db2, key2)
    assert store3.get_vault_id() == meta_before["vault_id"]
    store3.close()

def test_vault_context_manager(crypto, db_path):
    key = bytearray(os.urandom(32))
    with VaultStore(crypto) as store:
        store.initialize(db_path, key)
        assert store._conn is not None
    assert store._conn is None

def test_vault_init_exists(crypto, db_path):
    store = VaultStore(crypto)
    key = bytearray(os.urandom(32))
    store.initialize(db_path, key)
    store.close()

    store2 = VaultStore(crypto)
    with pytest.raises(NyxoraError):
        store2.initialize(db_path, key)

def test_vault_update_delete_not_found(crypto, db_path):
    store = VaultStore(crypto)
    key = bytearray(os.urandom(32))
    store.initialize(db_path, key)

    with pytest.raises(NyxoraError):
        store.update_entry("fake-uuid-123", password="123")

    with pytest.raises(NyxoraError):
        store.delete_entry("fake-uuid-123")

    store.close()

def test_vault_require_open(crypto):
    store = VaultStore(crypto)

    with pytest.raises(NyxoraError):
        store.add_entry("Fail", "pass")

    with pytest.raises(NyxoraError):
        store.list_entries()

    with pytest.raises(NyxoraError):
        store.update_entry("fail-id")

    with pytest.raises(NyxoraError):
        store.delete_entry("fail-id")

def test_vault_audit_details_encryption(crypto, db_path):
    store = VaultStore(crypto)
    import os
    key = bytearray(os.urandom(32))
    store.initialize(db_path, key)

    # Passing custom detail directly to private `_append_audit` to trigger encryption paths (lines 331-333)
    with store._conn:
        store._append_audit(store._conn, "CUSTOM", "fake-id", "session-id", {"ip": "127.0.0.1"})

    # Verify the detail payload is seamlessly encrypted/decrypted
    events = store.get_all_audit_events()
    assert events[0]["detail"] == {"ip": "127.0.0.1"}

    store.close()


def test_vault_totp_field(tmp_path):
    """TOTP secret stores, retrieves, and migrates correctly."""
    from nyxora.core.crypto_engine import CryptoEngine
    from nyxora.core.vault_store import VaultStore
    from nyxora.core.memory_guard import wipe_memory

    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("test-totp", salt)
    vault_path = tmp_path / "totp.nyx"

    store = VaultStore(engine)
    store.initialize(vault_path, root_key)

    # Add entry with TOTP secret
    eid = store.add_entry("GitHub", "hunter2",
                          totp_secret="JBSWY3DPEHPK3PXP")
    rec = store.get_entry(eid)
    assert rec.totp_secret == "JBSWY3DPEHPK3PXP"

    # Update TOTP secret
    store.update_entry(eid, totp_secret="NEWBASE32SECRET2")
    rec2 = store.get_entry(eid)
    assert rec2.totp_secret == "NEWBASE32SECRET2"

    # Clear TOTP secret with empty string
    store.update_entry(eid, totp_secret="")
    rec3 = store.get_entry(eid)
    assert rec3.totp_secret is None

    # Entry without TOTP has totp_secret=None
    eid2 = store.add_entry("Gmail", "pass123")
    rec4 = store.get_entry(eid2)
    assert rec4.totp_secret is None

    store.close()
    wipe_memory(root_key)
