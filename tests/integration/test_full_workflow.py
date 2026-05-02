import pytest
from pathlib import Path

from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import VaultStore


def test_full_vault_lifecycle(tmp_path):
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("integration-test-password", salt)
    new_root_key = None

    try:
        # ── STEP 1: Initialize ────────────────────────────────────────────────
        vault_path = tmp_path / "test.nyx"
        store = VaultStore(engine)
        store.initialize(vault_path, root_key)
        store.close()
        assert vault_path.exists()

        # ── STEP 2: Open and add entries ──────────────────────────────────────
        store.open(vault_path, root_key)
        eid1 = store.add_entry("GitHub", "hunter2", username="alice", tags=["dev"])
        eid2 = store.add_entry("Gmail", "pass123", username="alice@example.com")
        eid3 = store.add_entry("AWS", "secret!", tags=[])  # empty tags — tests migrate_from_store fix
        assert store.entry_count() == 3
        store.close()

        # ── STEP 3: Re-open and verify (simulates re-unlock) ──────────────────
        store.open(vault_path, root_key)
        rec = store.get_entry(eid1)
        assert rec.title == "GitHub"
        assert rec.password == "hunter2"
        assert rec.username == "alice"
        assert rec.tags == ["dev"]
        rec3 = store.get_entry(eid3)
        assert rec3.tags == []
        store.close()

        # ── STEP 4: Update and delete ─────────────────────────────────────────
        store.open(vault_path, root_key)
        store.update_entry(eid1, password="new-secure-pw")
        rec_updated = store.get_entry(eid1)
        assert rec_updated.password == "new-secure-pw"
        store.delete_entry(eid2)
        entries = store.list_entries()
        assert len(entries) == 2  # eid2 soft-deleted
        store.close()

        # ── STEP 5: Search ────────────────────────────────────────────────────
        store.open(vault_path, root_key)
        results = store.search_entries("github")
        assert len(results) == 1
        assert results[0].id == eid1
        store.close()

        # ── STEP 6: Change password ───────────────────────────────────────────
        new_salt = engine.generate_salt()
        new_root_key = engine.derive_key("new-password-456", new_salt)
        new_vault = tmp_path / "test.nyx.new"

        new_store = VaultStore(engine)
        new_store.initialize(new_vault, new_root_key)
        old_store = VaultStore(engine)
        old_store.open(vault_path, root_key)
        new_store.migrate_from_store(old_store)
        new_store.close()
        old_store.close()

        bak = tmp_path / "test.nyx.bak"
        vault_path.rename(bak)
        new_vault.rename(vault_path)
        bak.unlink()

        verify = VaultStore(engine)
        verify.open(vault_path, new_root_key)
        assert verify.entry_count() == 2
        verify.close()

        from nyxora.utils.exceptions import NyxoraError
        broken = VaultStore(engine)
        with pytest.raises(NyxoraError):
            broken.open(vault_path, root_key)

        # ── STEP 7: Integrity check ───────────────────────────────────────────
        final = VaultStore(engine)
        final.open(vault_path, new_root_key)
        report = final.verify_integrity()
        assert report.passed is True
        assert report.schema_ok is True
        assert report.vault_hmac_ok is True
        assert len(report.entries_failed) == 0
        final.close()

    finally:
        wipe_memory(root_key)
        if new_root_key is not None:
            wipe_memory(new_root_key)
