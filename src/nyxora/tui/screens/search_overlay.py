"""Search overlay screen for live filtering."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label


class SearchScreen(ModalScreen[None]):
    """Modal search overlay — filters the entry list in real time."""

    DEFAULT_CSS = """
    SearchScreen {
        align: center top;
    }
    #search-overlay {
        background: #0F1218;
        border: tall #C89A30;
        width: 60;
        height: 5;
        margin-top: 3;
        padding: 1 2;
    }
    #search-prompt {
        color: #C89A30;
        height: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="search-overlay"):
            yield Label("⟨/⟩  Filter entries", id="search-prompt")
            yield Input(placeholder="type to filter…", id="search-input")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        # Apply filter to browser screen in real time
        from nyxora.tui.screens.vault_browser import VaultBrowserScreen
        for screen in self.app.screen_stack:
            if isinstance(screen, VaultBrowserScreen):
                screen.apply_filter(event.value)
                break

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.app.pop_screen()

    def action_cancel(self) -> None:
        # Clear filter on cancel
        from nyxora.tui.screens.vault_browser import VaultBrowserScreen
        for screen in self.app.screen_stack:
            if isinstance(screen, VaultBrowserScreen):
                screen.apply_filter("")
                break
        self.app.pop_screen()
