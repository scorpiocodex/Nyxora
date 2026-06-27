from pathlib import Path

import pytest

from nyxora import VaultClient, __version__
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import VaultStore
from nyxora.utils.exceptions import EntryNotFoundError, NyxoraError


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
    assert __version__ == "3.1.0"


# ── C3: CLI ↔ SDK KDF cross-compatibility ──────────────────────────────


def test_sdk_opens_cli_created_vault(tmp_path):
    """C3 regression: the SDK's default KDF params must match the CLI's.

    Creates a vault through the real `nyx vault unlock --create` command
    (canonical CryptoEngine defaults), then opens it with VaultClient
    using NO explicit Argon2 parameters. Pre-fix the SDK defaulted to
    64MB/t=1 and derived a different root key, so this open failed.
    """
    from unittest.mock import patch

    from typer.testing import CliRunner

    from nyxora.cli.main import app

    vp = tmp_path / "cli-created.nyx"
    pw = "Cross-Compat-Pw-1"

    runner = CliRunner()
    with patch("questionary.password") as m_pw, \
         patch("nyxora.cli.commands.vault.ui"), \
         patch("nyxora.cli.commands.vault.save_session"):
        m_pw.return_value.ask.return_value = pw
        result = runner.invoke(
            app, ["vault", "unlock", "--create", "--vault", str(vp)]
        )
    assert result.exit_code == 0
    assert vp.exists()
    assert vp.with_suffix(".salt").exists()

    # Add a known entry through the CLI's mechanism: a default-constructed
    # CryptoEngine, the same as cli/commands/vault.py's module engine.
    cli_engine = CryptoEngine()
    salt = vp.with_suffix(".salt").read_bytes()
    root_key = cli_engine.derive_key(pw, salt)
    store = VaultStore(cli_engine)
    store.open(vp, root_key)
    store.add_entry("CrossCompat", "cli-secret-42", username="cli-user")
    store.close()
    wipe_memory(root_key)

    # THE C3 assertion: the SDK, with its DEFAULT parameters, must derive
    # the identical key and open the CLI's vault.
    with VaultClient(vault_path=vp, password=pw) as client:
        entry = client.get("CrossCompat")
        assert entry.password == "cli-secret-42"
        assert entry.username == "cli-user"


def test_cli_opens_sdk_created_vault(tmp_path):
    """C3 symmetry: a vault created with the SDK's default KDF params
    must open through the CLI's default-constructed CryptoEngine.

    The SDK has no initialize() API, so "created via SDK" means: vault
    file initialised with whatever Argon2 defaults VaultClient ships,
    then the entry added through VaultClient itself. Guards against
    future divergence in either direction.
    """
    vp = tmp_path / "sdk-created.nyx"
    pw = "Cross-Compat-Pw-2"

    probe = VaultClient(vault_path=vp, password=pw)
    sdk_engine = CryptoEngine(
        argon2_memory=probe._argon2_memory,
        argon2_time=probe._argon2_time,
        argon2_parallelism=probe._argon2_parallelism,
    )
    salt = sdk_engine.generate_salt()
    root_key = sdk_engine.derive_key(pw, salt)
    store = VaultStore(sdk_engine)
    store.initialize(vp, root_key)
    store.close()
    wipe_memory(root_key)
    vp.with_suffix(".salt").write_bytes(salt)

    with VaultClient(vault_path=vp, password=pw) as client:
        client.add("SdkEntry", "sdk-secret-77", username="sdk-user")

    # CLI mechanism: default-constructed engine (canonical parameters)
    cli_engine = CryptoEngine()
    cli_key = cli_engine.derive_key(pw, vp.with_suffix(".salt").read_bytes())
    cli_store = VaultStore(cli_engine)
    cli_store.open(vp, cli_key)
    entries = {e.title: e for e in cli_store.list_entries()}
    assert entries["SdkEntry"].password == "sdk-secret-77"
    assert entries["SdkEntry"].username == "sdk-user"
    cli_store.close()
    wipe_memory(cli_key)
