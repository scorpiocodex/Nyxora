import os
from unittest.mock import patch

from typer.testing import CliRunner

from nyxora.cli.main import app

runner = CliRunner()
MASTER_PW = "Thacheth7734"

@patch("questionary.password")
@patch("nyxora.cli.commands.vault.ui")
@patch("nyxora.cli.commands.vault.get_vault_path")
def test_vault_init_and_unlock(m_path, m_ui, m_pw, tmp_path):
    vpath = tmp_path / "test.nyx"
    m_path.return_value = vpath
    m_pw.return_value.ask.side_effect = [MASTER_PW, MASTER_PW, MASTER_PW, "NewPw123!", "NewPw123!"]

    runner.invoke(app, ["vault", "init"])
    runner.invoke(app, ["vault", "unlock"])

    from nyxora.core.crypto_engine import CryptoEngine
    engine = CryptoEngine()
    root_key = engine.derive_key(MASTER_PW.encode(), vpath.with_suffix(".salt").read_bytes())

    with patch("nyxora.cli.commands.vault.load_session") as m_load:
        m_load.return_value = ("session_id", vpath, root_key)
        runner.invoke(app, ["vault", "change-password"])

@patch("questionary.confirm")
@patch("questionary.password")
@patch("questionary.text")
@patch("nyxora.cli.commands.secret.ui")
@patch("nyxora.cli.commands.secret.open_vault")
@patch("nyxora.core.vault_store.VaultStore.close", return_value=None)
def test_secret_crud(m_close, m_open, m_ui, m_text, m_pw, m_conf, tmp_path):
    from nyxora.core.crypto_engine import CryptoEngine
    from nyxora.core.vault_store import VaultStore

    engine = CryptoEngine()
    store = VaultStore(engine)
    vp = tmp_path / "temp.nyx"
    salt = os.urandom(16)
    root_key = engine.derive_key(MASTER_PW.encode(), salt)
    store.initialize(vp, root_key)

    m_open.return_value = (store, "session", bytearray(root_key), vp)

    m_text.return_value.ask.side_effect = ["MyService", "user1", "https://url.com", "notes", "GenService", "user2", ""]
    m_pw.return_value.ask.return_value = "SecretPw123"
    m_conf.return_value.ask.return_value = True

    runner.invoke(app, ["secret", "add", "--tags", "tag1,tag2"])
    runner.invoke(app, ["secret", "add", "--generate"])

    entries = store.list_entries()
    id1 = entries[0].id

    runner.invoke(app, ["secret", "get", id1, "--no-copy"])
    with patch("typer.confirm", return_value=False):
        runner.invoke(app, ["secret", "update", id1, "--title", "UpdatedTitle"])
    runner.invoke(app, ["secret", "list", "--tag", "tag1"])
    runner.invoke(app, ["secret", "search", "UpdatedTitle"])
    runner.invoke(app, ["secret", "clone", id1, "--new-title", "ClonedEntry"])

    runner.invoke(app, ["secret", "delete", id1])

    store.close()

def test_generate_commands():
    with patch("nyxora.cli.commands.generate.ui"):
        runner.invoke(app, ["generate", "password"])
        runner.invoke(app, ["generate", "passphrase"])
        runner.invoke(app, ["generate", "api-key", "--prefix", "sk_test_"])
        runner.invoke(app, ["generate", "ssh-key", "--output", "test_key", "--no-passphrase"])
        runner.invoke(app, ["generate", "entropy", "password123"])

@patch("questionary.password")
@patch("nyxora.cli.commands.recovery.ui")
@patch("nyxora.cli.commands.recovery.load_session")
def test_recovery_capsule(m_load, m_ui, m_pw, tmp_path):
    from nyxora.core.crypto_engine import CryptoEngine
    from nyxora.core.vault_store import VaultStore
    engine = CryptoEngine()
    store = VaultStore(engine)
    vp = tmp_path / "temp.nyx"
    salt = os.urandom(16)
    root_key = engine.derive_key(MASTER_PW.encode(), salt)
    store.initialize(vp, root_key)
    store.close()

    m_load.return_value = ("session", vp, bytearray(root_key))

    capsule_path = tmp_path / "recovery.capsule"
    m_pw.return_value.ask.side_effect = ["CapsulePw1!", "CapsulePw1!", "CapsulePw1!"]

    runner.invoke(app, ["recovery", "create-capsule", str(capsule_path), "--hint", "hint"])
    runner.invoke(app, ["recovery", "restore-capsule", str(capsule_path)])
    runner.invoke(app, ["recovery", "split-secret", str(tmp_path), "--shares", "3", "--threshold", "2"])
    runner.invoke(app, ["recovery", "status"])

@patch("nyxora.cli.commands.security.open_vault")
@patch("nyxora.cli.commands.security.ui")
@patch("nyxora.core.vault_store.VaultStore.close", return_value=None)
def test_security_commands(m_close, m_ui, m_open, tmp_path):
    from nyxora.core.crypto_engine import CryptoEngine
    from nyxora.core.vault_store import VaultStore
    engine = CryptoEngine()
    store = VaultStore(engine)
    vp = tmp_path / "temp.nyx"
    salt = os.urandom(16)
    root_key = engine.derive_key(MASTER_PW.encode(), salt)
    store.initialize(vp, root_key)
    store.add_entry("test", "weakpw")

    m_open.return_value = (store, "sess", bytearray(root_key), vp)

    runner.invoke(app, ["security", "audit", "--no-hibp"])
    runner.invoke(app, ["security", "stats"])
    runner.invoke(app, ["security", "log"])
    runner.invoke(app, ["security", "forensic"])

    with patch("nyxora.core.intel_engine.IntelEngine.check_breach_hibp", return_value=(False, 0)):
        runner.invoke(app, ["security", "breach-scan"])

    store.close()

def test_locker_commands(tmp_path):
    with patch("nyxora.cli.commands.locker.load_session") as m_load:
        from nyxora.core.crypto_engine import CryptoEngine
        engine = CryptoEngine()
        root_key = engine.derive_key(MASTER_PW.encode(), os.urandom(16))
        m_load.return_value = ("id", tmp_path / "v.nyx", bytearray(root_key))

        f = tmp_path / "test.txt"
        f.write_text("locker test")

        with patch("nyxora.cli.commands.locker.ui"):
            runner.invoke(app, ["locker", "encrypt", str(f)])
            enc = list(tmp_path.glob("*.nyx"))[0]
            runner.invoke(app, ["locker", "decrypt", str(enc)])
            runner.invoke(app, ["locker", "list", str(tmp_path)])

            with patch("questionary.confirm") as mq:
                mq.return_value.ask.return_value = True
                runner.invoke(app, ["locker", "shred", str(f)])

@patch("nyxora.core.vault_store.VaultStore.close", return_value=None)
def test_backup_commands(m_close, tmp_path):
    with patch("nyxora.cli.commands.backup.open_vault") as m_open:
        from nyxora.core.crypto_engine import CryptoEngine
        from nyxora.core.vault_store import VaultStore
        engine = CryptoEngine()
        store = VaultStore(engine)
        vp = tmp_path / "temp.nyx"
        salt = os.urandom(16)
        root_key = engine.derive_key(MASTER_PW.encode(), salt)
        store.initialize(vp, root_key)
        store.add_entry("b", "p")

        m_open.return_value = (store, "sess", bytearray(root_key), vp)

        with patch("nyxora.cli.commands.backup.ui"), patch("questionary.text"), patch("questionary.password"):
            runner.invoke(app, ["backup", "create", str(tmp_path), "--note", "test"])
            outs = list(tmp_path.glob("*.bak"))
            if outs:
                runner.invoke(app, ["backup", "verify", str(outs[0])])
                runner.invoke(app, ["backup", "restore", str(outs[0])])
            runner.invoke(app, ["backup", "cleanup", str(tmp_path), "--keep", "1"])

        store.close()
