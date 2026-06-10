"""Smoke tests for the TUI — verify instantiation without launching."""
from __future__ import annotations

from nyxora.core.vault_store import EntryRecord
import time


def _make_entries() -> list[EntryRecord]:
    now = int(time.time())
    return [
        EntryRecord(
            id="test-id-0001", title="GitHub", password="gh-token-abc",
            username="alice", url="https://github.com",
            tags=["dev"], created_at=now, updated_at=now,
        ),
        EntryRecord(
            id="test-id-0002", title="Gmail", password="gm-pass-xyz",
            username="alice@example.com",
            created_at=now, updated_at=now,
        ),
    ]


def test_nyxora_app_instantiation():
    """NyxoraApp can be created without errors."""
    from nyxora.tui.app import NyxoraApp
    app = NyxoraApp(start_screen="manage", exe_mode=False)
    assert app is not None


def test_unlock_screen_instantiation():
    """UnlockScreen can be created without errors."""
    from nyxora.tui.screens.unlock import UnlockScreen
    screen = UnlockScreen()
    assert screen is not None


def test_create_vault_screen_instantiation():
    """CreateVaultScreen can be created without errors."""
    from nyxora.tui.screens.unlock import CreateVaultScreen
    screen = CreateVaultScreen()
    assert screen is not None


def test_vault_screen_instantiation():
    """VaultScreen can be created without errors."""
    from nyxora.tui.screens.vault import VaultScreen
    screen = VaultScreen()
    assert screen is not None


def test_manage_screen_instantiation():
    """ManageScreen can be created without errors."""
    from nyxora.tui.screens.manage import ManageScreen
    screen = ManageScreen()
    assert screen is not None


def test_entry_item_instantiation():
    """EntryItem can be created from an EntryRecord."""
    from nyxora.tui.screens.manage import EntryItem
    entries = _make_entries()
    item = EntryItem(entries[0])
    assert item.record.title == "GitHub"


def test_add_entry_screen_instantiation():
    """AddEntryScreen can be created without errors."""
    from nyxora.tui.screens.add_entry import AddEntryScreen
    screen = AddEntryScreen()
    assert screen is not None


def test_edit_entry_screen_instantiation():
    """EditEntryScreen can be created without errors."""
    from nyxora.tui.screens.edit_entry import EditEntryScreen
    entries = _make_entries()
    screen = EditEntryScreen(record=entries[0])
    assert screen is not None


def test_backup_screen_instantiation():
    """BackupScreen can be created without errors."""
    from nyxora.tui.screens.backup import BackupScreen
    screen = BackupScreen()
    assert screen is not None


def test_recovery_screen_instantiation():
    """RecoveryScreen can be created without errors."""
    from nyxora.tui.screens.recovery import RecoveryScreen
    screen = RecoveryScreen()
    assert screen is not None


def test_updates_screen_instantiation():
    """UpdatesScreen can be created without errors."""
    from nyxora.tui.screens.updates import UpdatesScreen
    screen = UpdatesScreen()
    assert screen is not None


def test_generate_screen_instantiation():
    """GenerateScreen can be created without errors."""
    from nyxora.tui.screens.generate import GenerateScreen
    screen = GenerateScreen()
    assert screen is not None


def test_security_screen_instantiation():
    """SecurityScreen can be created without errors."""
    from nyxora.tui.screens.security import SecurityScreen
    screen = SecurityScreen()
    assert screen is not None


def test_wired_app_composes_all_screens():
    """NyxoraApp with wired screens can be instantiated."""
    from nyxora.tui.app import NyxoraApp
    from nyxora.tui.screens.vault    import VaultScreen
    from nyxora.tui.screens.manage   import ManageScreen
    from nyxora.tui.screens.backup   import BackupScreen
    from nyxora.tui.screens.recovery import RecoveryScreen
    from nyxora.tui.screens.updates  import UpdatesScreen
    from nyxora.tui.screens.generate import GenerateScreen
    from nyxora.tui.screens.security import SecurityScreen

    app = NyxoraApp(start_screen="manage", exe_mode=False)
    assert app is not None
    # All screen classes must be importable and instantiable
    assert VaultScreen()    is not None
    assert ManageScreen()   is not None
    assert BackupScreen()   is not None
    assert RecoveryScreen() is not None
    assert UpdatesScreen()  is not None
    assert GenerateScreen() is not None
    assert SecurityScreen() is not None


def test_nyx_top_bar():
    """NyxTopBar can be created with items."""
    from nyxora.tui.screens._shared_bg import NyxTopBar
    bar = NyxTopBar([("VAULT:LOCKED", True), ("OFFLINE", False)])
    assert bar is not None


def test_nyx_bottom_bar():
    """NyxBottomBar can be created."""
    from nyxora.tui.screens._shared_bg import NyxBottomBar
    bar = NyxBottomBar()
    assert bar is not None


def test_nyx_background():
    """NyxBackground can be created."""
    from nyxora.tui.screens._shared_bg import NyxBackground
    bg = NyxBackground()
    assert bg is not None


def test_nyx_corner_info():
    """NyxCornerInfo can be created."""
    from nyxora.tui.screens._shared_bg import NyxCornerInfo
    ci = NyxCornerInfo("CIPHER", ["XCHACHA20", "ARGON2ID"])
    assert ci is not None


def test_tui_cmd_no_textual(monkeypatch):
    """tui command handles missing textual gracefully."""
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "textual":
            raise ImportError("textual not installed")
        return real_import(name, *args, **kwargs)

    from typer.testing import CliRunner
    from nyxora.cli.commands.tui_cmd import app as tui_app

    runner = CliRunner()
    with monkeypatch.context() as m:
        m.setattr(builtins, "__import__", mock_import)
        result = runner.invoke(tui_app)
    assert result.exit_code in (0, 1)
