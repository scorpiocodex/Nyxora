import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
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

        # Any non-NyxoraError must flow through the generic Exception
        # handler: error panel shown, exit code 1
        mock_app.side_effect = RuntimeError("test generic error")
        with patch("nyxora.cli.ui.error_panel") as m_panel:
            with pytest.raises(SystemExit) as exc_info:
                cli_main()
            assert exc_info.value.code == 1
            m_panel.assert_called_once()

def test_memory_guard_branches():
    from unittest.mock import MagicMock

    from nyxora.core import memory_guard
    from nyxora.core.memory_guard import try_mlock, try_munlock, wipe_memory

    # memory_guard selects its branch from platform.system() and the
    # module-level _libc/_kernel32 globals bound at import time, so patch
    # those seams — they exist on every OS (ctypes.windll does not exist
    # on Linux, and sys.platform is not what the product reads).
    buf = bytearray(16)

    # Linux branch: mlock/munlock return 0 on success
    fake_libc = MagicMock()
    fake_libc.mlock.return_value = 0
    fake_libc.munlock.return_value = 0
    with patch.object(memory_guard.platform, "system", return_value="Linux"), \
         patch.object(memory_guard, "_MLOCK_AVAILABLE", True), \
         patch.object(memory_guard, "_libc", fake_libc):
        assert try_mlock(buf) is True
        assert try_munlock(buf) is True
        fake_libc.mlock.side_effect = Exception("failed")
        assert try_mlock(buf) is False
    assert fake_libc.mlock.call_count == 2
    fake_libc.munlock.assert_called_once()

    # Windows branch: VirtualLock/VirtualUnlock return nonzero on success
    fake_k32 = MagicMock()
    fake_k32.VirtualLock.return_value = 1
    fake_k32.VirtualUnlock.return_value = 1
    with patch.object(memory_guard.platform, "system", return_value="Windows"), \
         patch.object(memory_guard, "_MLOCK_AVAILABLE", True), \
         patch.object(memory_guard, "_kernel32", fake_k32):
        assert try_mlock(buf) is True
        assert try_munlock(buf) is True
        fake_k32.VirtualLock.side_effect = Exception("failed")
        assert try_mlock(buf) is False
    assert fake_k32.VirtualLock.call_count == 2
    fake_k32.VirtualUnlock.assert_called_once()

    # wipe_memory zeroes the buffer in place
    buf[:] = b"\xaa" * 16
    wipe_memory(buf)
    assert buf == bytearray(16)

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
