import os
import sys
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from nyxora.cli import helpers, ui
from nyxora.cli.main import app, cli_main

runner = CliRunner()

def test_generate_branches():
    # Pass combinations to generate command
    with patch("nyxora.cli.commands.generate.ui"):
        runner.invoke(app, ["generate", "password", "-l", "12", "-n", "3", "--no-symbols", "--no-digits", "--no-upper"])
        runner.invoke(app, ["generate", "passphrase", "-w", "8", "-s", "-", "-n", "2", "--capitalize"])
        runner.invoke(app, ["generate", "api-key", "-l", "64", "--prefix", "TEST_", "-n", "2"])
        runner.invoke(app, ["generate", "ssh-key", "-t", "rsa", "-b", "4096", "--comment", "test@test.com", "--no-passphrase"])

def test_locker_branches(tmp_path):
    with patch("nyxora.cli.commands.locker.load_session") as m_load:
        from nyxora.core.crypto_engine import CryptoEngine
        engine = CryptoEngine()
        root_key = engine.derive_key(b"pw", os.urandom(16))
        m_load.return_value = ("id", tmp_path / "v.nyx", bytearray(root_key))

        target = tmp_path / "target.txt"
        target.write_text("secure data")
        target_out = tmp_path / "out.nyx"

        with patch("nyxora.cli.commands.locker.ui"):
            # Execute locker commands directly mimicking Typer inputs
            runner.invoke(app, ["locker", "encrypt", str(target), "--output", str(target_out), "--delete-original"])
            runner.invoke(app, ["locker", "decrypt", str(target_out), "--output", str(tmp_path / "recovered.txt")])

            # Sub-branches
            runner.invoke(app, ["locker", "list", str(tmp_path)])

            # Missing branches: target doesn't exist
            runner.invoke(app, ["locker", "encrypt", "doesnotexist.txt"])
            runner.invoke(app, ["locker", "decrypt", "doesnotexist.nyx"])

def test_main_cli_execution():
    with patch("nyxora.cli.main.app") as mock_app:
        # Mock sys.argv to trigger different branches
        with patch.object(sys, "argv", ["nyx"]):
            try:
                cli_main()
            except SystemExit:
                pass

        # Mock exceptions
        import click
        mock_app.side_effect = click.exceptions.UsageError("test usage error")
        with patch("nyxora.cli.ui.error_panel"):
            try:
                cli_main()
            except SystemExit:
                pass

def test_memory_guard_branches():
    from nyxora.core.memory_guard import try_mlock, try_munlock, wipe_memory

    # Mock platform functions to simulate failures and success
    buf = bytearray(16)
    with patch("sys.platform", "linux"):
        with patch("ctypes.CDLL") as m_cdll:
            try_mlock(buf)
            try_munlock(buf)
            m_cdll.return_value.mlock.side_effect = Exception("failed")
            try_mlock(buf)

    with patch("sys.platform", "win32"):
        with patch("ctypes.windll.kernel32") as m_win:
            try_mlock(buf)
            try_munlock(buf)
            m_win.VirtualLock.side_effect = Exception("failed")
            try_mlock(buf)

    # wipe_memory
    wipe_memory(buf)

def test_helpers_branches():
    from nyxora.utils.config import Config
    c = Config()
    c.set("vault.default_path", "/fake/path")
    helpers.get_vault_path(c)

    with patch("nyxora.cli.helpers.SESSION_FILE", Path("/does/not/exist/9999")):
        assert helpers.load_session() is None

    import tempfile
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("{}")
        f.close()

        with patch("nyxora.cli.helpers.SESSION_FILE", Path(f.name)):
            assert helpers.load_session() is None

        os.unlink(f.name)

def test_ui_branches():
    # Hit empty UI renders
    ui.success_panel("test")
    ui.error_panel("test")
    ui.warning_panel("test")
    ui.info_panel("test")
    ui.print_line("test")
    ui.print_kv("k", "v")

    # Tables
    from nyxora.core.vault_store import EntryRecord
    er = EntryRecord(id="1", title="test", password="test")
    ui.table_entries([er], show_passwords=True)
    ui.table_entries([er], show_passwords=False)
    ui.table_entries([])
