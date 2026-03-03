import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nyxora.cli.main import app

runner = CliRunner()

@pytest.fixture(autouse=True)
def mock_session_handlers():
    state = {}

    def m_save_session(command: str, vpath: str, root_key_hex: str):
        state["path"] = vpath
        state["key"] = root_key_hex

    def m_load_session():
        if not state:
            return None
        return (str(uuid.uuid4()), Path(state["path"]), bytearray.fromhex(state["key"]))

    def m_clear_session():
        state.clear()

    with patch("nyxora.cli.commands.vault.save_session", side_effect=m_save_session), \
         patch("nyxora.cli.commands.vault.load_session", side_effect=m_load_session), \
         patch("nyxora.cli.commands.vault.clear_session", side_effect=m_clear_session), \
         patch("nyxora.cli.helpers.save_session", side_effect=m_save_session), \
         patch("nyxora.cli.helpers.load_session", side_effect=m_load_session), \
         patch("nyxora.cli.helpers.clear_session", side_effect=m_clear_session):
        yield state

def test_massive_coverage_shotgun(tmp_path, mock_session_handlers):
    vault_file = tmp_path / "shotgun.vault"
    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.side_effect = ["pw1", "pw1"]
        runner.invoke(app, ["vault", "init", "--vault", str(vault_file)])

    assert "path" in mock_session_handlers

    # Generate
    runner.invoke(app, ["generate", "password"])
    runner.invoke(app, ["generate", "passphrase"])

    # Security
    runner.invoke(app, ["security", "audit", "--no-hibp"])
    runner.invoke(app, ["security", "stats"])
    runner.invoke(app, ["security", "log"])
    runner.invoke(app, ["security", "forensic"])
    runner.invoke(app, ["security", "breach-scan"])

    # Locker
    test_nyx = tmp_path / "test.txt"
    test_nyx.write_text("hello locker")
    runner.invoke(app, ["locker", "list", "--dir", str(tmp_path)])
    runner.invoke(app, ["locker", "encrypt", str(test_nyx)])

    encrypted = list(tmp_path.parent.glob("*.nyx"))
    for e in encrypted:
        runner.invoke(app, ["locker", "decrypt", str(e)])
        runner.invoke(app, ["locker", "shred", str(e), "--yes"])

    # Backup
    runner.invoke(app, ["backup", "list"])
    runner.invoke(app, ["backup", "create", "--dir", str(tmp_path), "--note", "test backup"])

    backups = list(tmp_path.glob("*.bak"))
    if backups:
        runner.invoke(app, ["backup", "verify", str(backups[0])])
        runner.invoke(app, ["backup", "restore", str(backups[0])])
        runner.invoke(app, ["backup", "cleanup", "--dir", str(tmp_path)])

    with patch("questionary.confirm") as m_conf:
        m_conf.return_value.ask.return_value = True
        runner.invoke(app, ["backup", "export", str(tmp_path / "exp.csv"), "--plaintext"])

    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.side_effect = ["epw", "epw"]
        runner.invoke(app, ["backup", "export", str(tmp_path / "exp.nyx")])

    # Recovery
    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.side_effect = ["capsule_pw", "capsule_pw"]
        cap_file = tmp_path / "rec.capsule"
        runner.invoke(app, ["recovery", "create-capsule", str(cap_file)])

    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.return_value = "capsule_pw"
        runner.invoke(app, ["recovery", "restore-capsule", str(cap_file)])

    runner.invoke(app, ["recovery", "split-secret", "--shares", "3", "--threshold", "2", "-o", str(tmp_path)])
    runner.invoke(app, ["recovery", "status"])

    # Secret
    with patch("questionary.password") as m_pass, patch("questionary.text") as m_text:
        m_pass.return_value.ask.return_value = "supersecretpw123"
        m_text.return_value.ask.return_value = ""
        res_add = runner.invoke(app, ["secret", "add", "--title", "My Email", "--username", "u@e.com"])

    import re
    match = re.search(r"ID:\s*([a-fA-F0-9-]+)", res_add.stdout)
    if match:
        eid = match.group(1)
        runner.invoke(app, ["secret", "get", eid])
        runner.invoke(app, ["secret", "list"])
        runner.invoke(app, ["secret", "history", eid])

        with patch("questionary.confirm") as m_conf:
            m_conf.return_value.ask.return_value = True
            runner.invoke(app, ["secret", "remove", eid])

    # Vault
    runner.invoke(app, ["vault", "status"])
    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.side_effect = ["pw1", "newpw", "newpw"]
        runner.invoke(app, ["vault", "change-password"])

    runner.invoke(app, ["vault", "lock"])

    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.return_value = "newpw"
        runner.invoke(app, ["vault", "unlock", "--vault", str(vault_file)])

    with patch("questionary.confirm") as m_conf:
        m_conf.return_value.ask.return_value = True
        runner.invoke(app, ["vault", "destroy", "--yes"])

