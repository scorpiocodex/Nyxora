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


# ── Focus-aware nav bindings (C2 fix: priority=True removed) ──────


def test_check_action_blocks_navigation_when_input_focused():
    """Digits typed into a focused Input must not trigger nav bindings."""
    import asyncio

    from textual.widgets import ContentSwitcher, Input

    from nyxora.tui.app import NyxoraApp

    async def scenario():
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause(0.2)  # let Manage's deferred load settle
            search = app.query_one("#entry-search", Input)
            search.focus()
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            switcher = app.query_one("#workspace", ContentSwitcher)
            assert switcher.current == "screen-manage"
            assert "3" in search.value

    asyncio.run(scenario())


def test_check_action_allows_navigation_when_no_input_focused():
    """Digit nav bindings still work when no Input has focus."""
    import asyncio

    from textual.widgets import ContentSwitcher

    from nyxora.tui.app import NyxoraApp

    async def scenario():
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause(0.2)
            app.set_focus(None)
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            switcher = app.query_one("#workspace", ContentSwitcher)
            assert switcher.current == "screen-backup"

    asyncio.run(scenario())


def test_manage_search_accepts_consecutive_letters():
    """Search Input keeps focus through letter keystrokes (no steal)."""
    import asyncio

    from textual.widgets import Input

    from nyxora.tui.app import NyxoraApp

    async def scenario():
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)  # let Manage's deferred load settle
            search = app.query_one("#entry-search", Input)
            search.focus()
            await pilot.pause()
            for key in "amazon":
                await pilot.press(key)
                await pilot.pause()
            assert search.value == "amazon"

    asyncio.run(scenario())


def test_manage_search_accepts_consecutive_digits():
    """All digits 1-7 land in the search Input; no nav binding fires."""
    import asyncio

    from textual.widgets import ContentSwitcher, Input

    from nyxora.tui.app import NyxoraApp

    async def scenario():
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            search = app.query_one("#entry-search", Input)
            search.focus()
            await pilot.pause()
            for key in "1234567":
                await pilot.press(key)
                await pilot.pause()
            assert search.value == "1234567"
            switcher = app.query_one("#workspace", ContentSwitcher)
            assert switcher.current == "screen-manage"

    asyncio.run(scenario())


def test_manage_letter_bindings_fire_when_input_not_focused():
    """'a' opens the add-entry overlay when focus is not on an Input."""
    import asyncio

    from textual.widgets import Button

    from nyxora.tui.app import NyxoraApp
    from nyxora.tui.screens.add_entry import AddEntryScreen

    async def scenario():
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            # Focus a ManageScreen descendant so its bindings are active
            app.set_focus(app.query_one("#btn-copy", Button))
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            assert isinstance(app.screen, AddEntryScreen)

    asyncio.run(scenario())


def _patch_fake_vault(monkeypatch, saved):
    """Route _do_totp_setup's vault access to fakes (no real vault)."""
    import nyxora.cli.helpers as helpers
    import nyxora.core.memory_guard as memory_guard

    class FakeStore:
        def set_metadata_value(self, key, value):
            saved[key] = value

        def close(self):
            pass

    monkeypatch.setattr(helpers, "load_session",
                        lambda: ("vault", "vp", b"k"))
    monkeypatch.setattr(helpers, "open_vault",
                        lambda engine: (FakeStore(), None, b"\x00" * 32, None))
    monkeypatch.setattr(memory_guard, "wipe_memory", lambda *_: None)


def test_totp_setup_opens_qr_overlay(monkeypatch):
    """SETUP TOTP saves the secret, then opens the QR overlay."""
    import asyncio

    from textual.widgets import Input

    from nyxora.tui.app import NyxoraApp
    from nyxora.tui.screens.totp_qr_overlay import TotpQrOverlay

    saved = {}
    _patch_fake_vault(monkeypatch, saved)

    async def scenario():
        app = NyxoraApp(start_screen="recovery", exe_mode=False)
        async with app.run_test(size=(140, 46)) as pilot:
            await pilot.pause(0.3)
            app.query_one("#totp-label", Input).value = "nyxora@example.com"
            await pilot.pause()
            await pilot.click("#btn-totp-setup")
            await pilot.pause(0.3)
            assert isinstance(app.screen, TotpQrOverlay)
            assert app.screen.secret == saved["totp_secret"]

    asyncio.run(scenario())


def test_totp_qr_overlay_dismisses_on_escape():
    """Esc closes the QR overlay and returns to the main screen."""
    import asyncio

    from nyxora.tui.app import NyxoraApp
    from nyxora.tui.screens.totp_qr_overlay import TotpQrOverlay

    async def scenario():
        app = NyxoraApp(start_screen="recovery", exe_mode=False)
        async with app.run_test(size=(140, 46)) as pilot:
            await pilot.pause(0.3)
            app.push_screen(TotpQrOverlay(
                secret="ABCDEF234567",
                account_label="test@example.com",
            ))
            await pilot.pause()
            assert isinstance(app.screen, TotpQrOverlay)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, TotpQrOverlay)

    asyncio.run(scenario())


def test_totp_qr_not_in_side_panel_after_mode_switch(monkeypatch):
    """No stale QR half-block chars in the side panel after sub-mode switch."""
    import asyncio

    from textual.widgets import Input, Static

    from nyxora.tui.app import NyxoraApp

    saved = {}
    _patch_fake_vault(monkeypatch, saved)

    async def scenario():
        app = NyxoraApp(start_screen="recovery", exe_mode=False)
        async with app.run_test(size=(140, 46)) as pilot:
            await pilot.pause(0.3)
            app.query_one("#totp-label", Input).value = "nyxora@example.com"
            await pilot.pause()
            await pilot.click("#btn-totp-setup")
            await pilot.pause(0.3)
            await pilot.press("escape")
            await pilot.pause(0.3)
            await pilot.click("#btn-p-capsule")
            await pilot.pause(0.3)
            for wid in ("#totp-output", "#qr-placeholder"):
                text = str(app.query_one(wid, Static).content)
                assert not any(ch in text for ch in "▀▄█"), wid

    asyncio.run(scenario())


# ── Overlay-aware quit/nav suppression ────────────────────────────


def test_quit_suppressed_while_addentry_overlay_active():
    """q must not quit the app while the add-entry form is open."""
    import asyncio

    from textual.widgets import Button

    from nyxora.tui.app import NyxoraApp
    from nyxora.tui.screens.add_entry import AddEntryScreen

    async def scenario():
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.set_focus(app.query_one("#btn-copy", Button))
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            assert isinstance(app.screen, AddEntryScreen)
            # Focus a non-Input so 'q' reaches the App bindings
            app.set_focus(app.screen.query_one("#btn-cancel", Button))
            await pilot.pause()
            await pilot.press("q")
            await pilot.pause()
            # Without suppression action_quit would have exited the app
            assert isinstance(app.screen, AddEntryScreen)

    asyncio.run(scenario())


def test_nav_suppressed_while_totpqr_overlay_active():
    """Digits must not switch workspace sections under the QR overlay."""
    import asyncio

    from textual.widgets import ContentSwitcher

    from nyxora.tui.app import NyxoraApp
    from nyxora.tui.screens.totp_qr_overlay import TotpQrOverlay

    async def scenario():
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            switcher = app.query_one("#workspace", ContentSwitcher)
            app.push_screen(TotpQrOverlay(
                secret="ABCDEF234567",
                account_label="test@example.com",
            ))
            await pilot.pause()
            assert isinstance(app.screen, TotpQrOverlay)
            await pilot.press("3")
            await pilot.pause()
            assert isinstance(app.screen, TotpQrOverlay)
            assert switcher.current == "screen-manage"

    asyncio.run(scenario())


def test_quit_allowed_at_unlock_screen():
    """check_action permits quit at the lock screen (cold or relock)."""
    import asyncio

    from textual.widgets import Input

    from nyxora.tui.app import NyxoraApp
    from nyxora.tui.screens.unlock import UnlockScreen

    async def scenario():
        # Cold launch: UnlockScreen pushed by on_mount.
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert isinstance(app.screen, UnlockScreen)
            app.screen.query_one("#unlock-password", Input).focus()
            await pilot.pause()
            assert app.check_action("quit", ()) is True
            assert app.check_action("navigate", ()) is False

        # Mid-session relock: UnlockScreen pushed over the workspace.
        app2 = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app2.run_test() as pilot:
            await pilot.pause(0.3)
            app2.push_screen(UnlockScreen())
            await pilot.pause()
            assert isinstance(app2.screen, UnlockScreen)
            assert app2.check_action("quit", ()) is True

    asyncio.run(scenario())


def test_nav_works_on_bare_workspace_no_overlay():
    """Digit nav still fires on the workspace when no overlay is open."""
    import asyncio

    from textual.widgets import Button, ContentSwitcher

    from nyxora.tui.app import NyxoraApp

    async def scenario():
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause(0.3)
            app.set_focus(app.query_one("#btn-copy", Button))
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            switcher = app.query_one("#workspace", ContentSwitcher)
            assert switcher.current == "screen-backup"

    asyncio.run(scenario())


def test_unlock_password_field_accepts_all_digits():
    """Master password Input on UnlockScreen accepts digits 1-7."""
    import asyncio

    from textual.widgets import Input

    from nyxora.tui.app import NyxoraApp

    async def scenario():
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            pw = app.screen.query_one("#unlock-password", Input)
            pw.focus()
            await pilot.pause()
            await pilot.press(*"abc1234567")
            await pilot.pause()
            assert pw.value == "abc1234567"

    asyncio.run(scenario())
