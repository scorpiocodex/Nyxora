from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import VaultStore


def test_entry_cache_hit_and_invalidation(tmp_path):
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("cache-test", salt)
    vault_path = tmp_path / "cache.nyx"
    store = VaultStore(engine)
    store.initialize(vault_path, root_key)
    store.close()
    store.open(vault_path, root_key)

    # Cache starts empty after open
    eid = store.add_entry("CacheTest", "pw123")
    assert store._cache is not None
    assert eid in store._cache          # add_entry populates cache

    # get_entry returns from cache (no DB read)
    rec = store.get_entry(eid)
    assert rec.password == "pw123"
    assert eid in store._cache

    # update_entry invalidates cache entry
    store.update_entry(eid, password="new-pw")
    assert eid not in store._cache      # invalidated

    # After update, get_entry re-fetches and re-caches
    rec2 = store.get_entry(eid)
    assert rec2.password == "new-pw"
    assert eid in store._cache

    # delete_entry removes from cache
    store.delete_entry(eid)
    assert eid not in store._cache

    # close() clears cache
    store.close()
    assert store._cache is None

    wipe_memory(root_key)


def test_get_metadata_value(tmp_path):
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("meta-test", salt)
    vault_path = tmp_path / "meta.nyx"
    store = VaultStore(engine)
    store.initialize(vault_path, root_key)

    # vault_id is always set
    vault_id = store.get_metadata_value("vault_id")
    assert vault_id is not None
    assert len(vault_id) > 0

    # Non-existent key returns None
    missing = store.get_metadata_value("totp_secret")
    assert missing is None

    store.close()
    wipe_memory(root_key)


def test_import_csv_round_trip(tmp_path):
    import csv as csv_mod

    from nyxora.cli.commands.import_ import _parse_csv

    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)

    # Write a test CSV
    csv_file = tmp_path / "import.csv"
    with open(csv_file, "w", newline="") as f:
        w = csv_mod.DictWriter(
            f, fieldnames=["title", "username", "password", "url", "notes"]
        )
        w.writeheader()
        w.writerow({"title": "GitHub", "username": "alice",
                    "password": "gh-token", "url": "https://github.com",
                    "notes": "work account"})
        w.writerow({"title": "Gmail", "username": "alice@example.com",
                    "password": "gm-pass", "url": "", "notes": ""})

    entries = _parse_csv(csv_file)
    assert len(entries) == 2
    assert entries[0]["title"] == "GitHub"
    assert entries[0]["password"] == "gh-token"
    assert entries[1]["title"] == "Gmail"

    # Import into real vault
    salt = engine.generate_salt()
    root_key = engine.derive_key("import-test", salt)
    vault_path = tmp_path / "import.nyx"
    store = VaultStore(engine)
    store.initialize(vault_path, root_key)
    for e in entries:
        store.add_entry(
            title=e["title"], password=e["password"],
            username=e.get("username"), url=e.get("url"),
            notes=e.get("notes"),
        )
    assert store.entry_count() == 2
    results = store.search_entries("GitHub")
    assert len(results) == 1
    assert results[0].username == "alice"
    store.close()
    wipe_memory(root_key)
