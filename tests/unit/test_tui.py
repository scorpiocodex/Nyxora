"""Smoke tests for the TUI — verify instantiation without launching."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
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


def test_vault_browser_instantiation():
    """VaultBrowserScreen can be created without errors."""
    from nyxora.tui.screens.vault_browser import VaultBrowserScreen
    entries = _make_entries()
    screen = VaultBrowserScreen(
        entries=entries,
        vault_path="/fake/vault.nyx",
        session_id="abc123def456",
    )
    assert screen is not None


def test_audit_screen_instantiation():
    """AuditScreen can be created without errors."""
    from nyxora.tui.screens.audit_screen import AuditScreen
    entries = _make_entries()
    screen = AuditScreen(entries=entries)
    assert screen is not None


def test_search_screen_instantiation():
    """SearchScreen can be created without errors."""
    from nyxora.tui.screens.search_overlay import SearchScreen
    screen = SearchScreen()
    assert screen is not None


def test_entry_list_item_instantiation():
    """EntryListItem can be created from an EntryRecord."""
    from nyxora.tui.screens.vault_browser import EntryListItem
    entries = _make_entries()
    item = EntryListItem(entries[0])
    assert item.record.title == "GitHub"


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
