from pathlib import Path
import pytest
from nyxora import VaultClient, __version__
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.vault_store import VaultStore
from nyxora.core.memory_guard import wipe_memory
from nyxora.utils.exceptions import NyxoraError, EntryNotFoundError


def _make_vault(tmp_path: Path, password: str = "sdk-test-pw") -> Path:
    engine = CryptoEngine(
        argon2_memory=8192, argon2_time=1, argon2_parallelism=1
    )
    salt = engine.generate_salt()
    root_key = engine.derive_key(password, salt)
    vault_path = tmp_path / "sdk.nyx"
    store = VaultStore(engine)
    store.initialize(vault_path, root_key)
    store.add_entry("GitHub", "gh-token", username="alice", tags=["dev"])
    store.add_entry("Gmail", "gm-pass", username="alice@example.com")
    store.close()
    wipe_memory(root_key)
    salt_file = vault_path.with_suffix(".salt")
    salt_file.write_bytes(salt)
    return vault_path


def test_vault_client_context_manager(tmp_path):
    vp = _make_vault(tmp_path)
    with VaultClient(vault_path=vp, password="sdk-test-pw",
                     argon2_memory=8192, argon2_time=1,
                     argon2_parallelism=1) as client:
        assert client.entry_count == 2


def test_vault_client_list(tmp_path):
    vp = _make_vault(tmp_path)
    with VaultClient(vault_path=vp, password="sdk-test-pw",
                     argon2_memory=8192, argon2_time=1,
                     argon2_parallelism=1) as client:
        entries = client.list()
        assert len(entries) == 2
        titles = {e.title for e in entries}
        assert "GitHub" in titles
        assert "Gmail" in titles


def test_vault_client_list_by_tag(tmp_path):
    vp = _make_vault(tmp_path)
    with VaultClient(vault_path=vp, password="sdk-test-pw",
                     argon2_memory=8192, argon2_time=1,
                     argon2_parallelism=1) as client:
        dev_entries = client.list(tag="dev")
        assert len(dev_entries) == 1
        assert dev_entries[0].title == "GitHub"


def test_vault_client_get_by_id(tmp_path):
    vp = _make_vault(tmp_path)
    with VaultClient(vault_path=vp, password="sdk-test-pw",
                     argon2_memory=8192, argon2_time=1,
                     argon2_parallelism=1) as client:
        entries = client.list()
        eid = entries[0].id
        record = client.get(eid)
        assert record.id == eid


def test_vault_client_get_by_title_search(tmp_path):
    vp = _make_vault(tmp_path)
    with VaultClient(vault_path=vp, password="sdk-test-pw",
                     argon2_memory=8192, argon2_time=1,
                     argon2_parallelism=1) as client:
        record = client.get("GitHub")
        assert record.title == "GitHub"
        assert record.password == "gh-token"
        assert record.username == "alice"


def test_vault_client_search(tmp_path):
    vp = _make_vault(tmp_path)
    with VaultClient(vault_path=vp, password="sdk-test-pw",
                     argon2_memory=8192, argon2_time=1,
                     argon2_parallelism=1) as client:
        results = client.search("git")
        assert len(results) == 1
        assert results[0].title == "GitHub"


def test_vault_client_add_update_delete(tmp_path):
    vp = _make_vault(tmp_path)
    with VaultClient(vault_path=vp, password="sdk-test-pw",
                     argon2_memory=8192, argon2_time=1,
                     argon2_parallelism=1) as client:
        # Add
        eid = client.add("AWS", "aws-secret", username="root")
        assert client.entry_count == 3

        # Update
        client.update(eid, password="new-aws-secret")
        rec = client.get(eid)
        assert rec.password == "new-aws-secret"

        # Delete
        client.delete(eid)
        assert client.entry_count == 2
        with pytest.raises(EntryNotFoundError):
            client.get(eid)


def test_vault_client_not_open_raises(tmp_path):
    vp = _make_vault(tmp_path)
    client = VaultClient(vault_path=vp, password="sdk-test-pw",
                         argon2_memory=8192, argon2_time=1,
                         argon2_parallelism=1)
    with pytest.raises(NyxoraError):
        client.list()  # not opened yet


def test_vault_client_wrong_password(tmp_path):
    vp = _make_vault(tmp_path)
    with pytest.raises(Exception):  # DecryptionError or IntegrityError
        with VaultClient(vault_path=vp, password="wrong-password",
                         argon2_memory=8192, argon2_time=1,
                         argon2_parallelism=1) as client:
            client.list()


def test_vault_client_health(tmp_path):
    vp = _make_vault(tmp_path)
    with VaultClient(vault_path=vp, password="sdk-test-pw",
                     argon2_memory=8192, argon2_time=1,
                     argon2_parallelism=1) as client:
        score = client.health()
        assert 0 <= score.total <= 100
        assert score.grade in ("A", "B", "C", "D", "F")
        assert score.total_entries == 2


def test_version_export():
    assert __version__ == "2.6.0"
