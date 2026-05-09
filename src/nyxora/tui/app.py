"""NYXORA Textual TUI application."""
from __future__ import annotations

from pathlib import Path

from textual.app import App
from textual.binding import Binding

from nyxora.core.vault_store import EntryRecord


class NyxoraApp(App):
    """NYXORA Obsidian Tactical — interactive vault browser."""

    CSS_PATH = Path(__file__).parent / "theme.tcss"

    BINDINGS = [
        Binding("q",             "quit",        "Quit",     show=True),
        Binding("question_mark", "help_info",   "Help",     show=True),
        Binding("c",             "copy_pass",   "Copy",     show=True),
        Binding("t",             "totp_code",   "TOTP",     show=True),
        Binding("A",             "audit",       "Audit",    show=True),
        Binding("slash",         "search",      "Search",   show=True),
        Binding("escape",        "clear_search","Clear",    show=False),
        Binding("j",             "nav_down",    "Down",     show=False),
        Binding("k",             "nav_up",      "Up",       show=False),
        Binding("down",          "nav_down",    "Down",     show=False),
        Binding("up",            "nav_up",      "Up",       show=False),
        Binding("d",             "delete_entry","Delete",   show=False),
        Binding("p",             "profiles",    "Profiles", show=False),
    ]

    def __init__(self, entries, vault_path, session_id, **kwargs):
        super().__init__(**kwargs)
        self._entries = entries
        self._vault_path = vault_path
        self._session_id = session_id

    def on_mount(self) -> None:
        from nyxora.tui.screens.vault_browser import VaultBrowserScreen
        from nyxora.tui.screens.search_overlay import SearchScreen
        from nyxora.tui.screens.audit_screen import AuditScreen
        self.install_screen(
            VaultBrowserScreen(
                self._entries, self._vault_path, self._session_id
            ), name="browser"
        )
        self.install_screen(SearchScreen(), name="search")
        self.install_screen(AuditScreen(self._entries), name="audit")
        self.push_screen("browser")

    def _get_browser(self):
        """Return the VaultBrowserScreen if it is the active screen."""
        from nyxora.tui.screens.vault_browser import VaultBrowserScreen
        screen = self.screen
        if isinstance(screen, VaultBrowserScreen):
            return screen
        return None

    def action_nav_down(self) -> None:
        b = self._get_browser()
        if b:
            b.action_cursor_down()

    def action_nav_up(self) -> None:
        b = self._get_browser()
        if b:
            b.action_cursor_up()

    def action_copy_pass(self) -> None:
        b = self._get_browser()
        if b:
            b.action_copy_pass()

    def action_totp_code(self) -> None:
        b = self._get_browser()
        if b:
            b.action_totp()

    def action_audit(self) -> None:
        from nyxora.tui.screens.audit_screen import AuditScreen
        if not isinstance(self.screen, AuditScreen):
            self.push_screen("audit")

    def action_search(self) -> None:
        from nyxora.tui.screens.search_overlay import SearchScreen
        if not isinstance(self.screen, SearchScreen):
            self.push_screen("search")

    def action_clear_search(self) -> None:
        from nyxora.tui.screens.search_overlay import SearchScreen
        if isinstance(self.screen, SearchScreen):
            self.pop_screen()
        else:
            b = self._get_browser()
            if b:
                b.apply_filter("")

    def action_delete_entry(self) -> None:
        b = self._get_browser()
        if b:
            record = b._get_selected()
            if record:
                self.notify(
                    f"Delete '{record.title}'? Press D again to confirm.",
                    title="Confirm Delete",
                    severity="warning",
                    timeout=3,
                )

    def action_profiles(self) -> None:
        b = self._get_browser()
        if b:
            b.action_profiles()

    def action_help_info(self) -> None:
        self.notify(
            "j/k ↑↓ navigate  c copy  t TOTP  A audit  / search  Esc clear  q quit",
            title="NYXORA Keybindings",
            timeout=6,
        )
