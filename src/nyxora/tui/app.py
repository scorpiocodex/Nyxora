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
        Binding("q", "quit", "Quit", show=True),
        Binding("question_mark", "help_info", "Help", show=True),
    ]

    SCREENS = {}  # registered in on_mount

    def __init__(
        self,
        entries: list[EntryRecord],
        vault_path: str,
        session_id: str,
        **kwargs,
    ) -> None:
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
            ),
            name="browser",
        )
        self.install_screen(SearchScreen(), name="search")
        self.install_screen(
            AuditScreen(self._entries), name="audit"
        )
        self.push_screen("browser")

    def action_help_info(self) -> None:
        self.notify(
            "j/k navigate  /  search  c copy  t TOTP  A audit  q quit",
            title="NYXORA Keybindings",
            timeout=6,
        )
