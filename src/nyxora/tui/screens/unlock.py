"""
Nyxora TUI v3.0.0 — UnlockScreen and CreateVaultScreen.

These are pushed as full-screen overlays by NyxoraApp.on_mount()
when the exe launches without an active session.

UnlockScreen   — shown when vault exists but is locked
CreateVaultScreen — shown when no vault file exists yet
"""
from __future__ import annotations

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static


# ── Shared helpers ───────────────────────────────────────────────

def _get_default_vault_path() -> Path:
    return Path.home() / ".nyxora" / "vault.nyx"


# ── Unlock screen ────────────────────────────────────────────────

class UnlockScreen(Screen):
    """
    Full-screen vault unlock overlay.

    Shown by NyxoraApp when the vault exists but no session is active.
    On success, dismisses itself; the app then shows the main layout.
    On failure, shows an inline error and allows retry.
    """

    BINDINGS = [
        Binding("escape", "app.quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="unlock-box"):
            yield Static(
                "\n  ◆  NYXORA\n",
                id="unlock-icon",
            )
            yield Static("Tactical Secrets Vault", id="unlock-title")
            yield Static(
                "Enter your master password to unlock",
                id="unlock-subtitle",
            )
            yield Input(
                placeholder="Master password…",
                password=True,
                id="unlock-password",
            )
            yield Static("", id="unlock-error", classes="form-error")
            with Horizontal():
                yield Button(
                    "  UNLOCK",
                    id="btn-unlock",
                    classes="primary",
                )
                yield Button(
                    "  QUIT",
                    id="btn-quit-unlock",
                )

    def on_mount(self) -> None:
        self.query_one("#unlock-password", Input).focus()

    # ── Events ──────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "unlock-password":
            self._attempt_unlock()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-unlock":
            self._attempt_unlock()
        elif event.button.id == "btn-quit-unlock":
            self.app.exit()

    # ── Unlock logic ─────────────────────────────────────────────

    def _attempt_unlock(self) -> None:
        pw_input = self.query_one("#unlock-password", Input)
        error_label = self.query_one("#unlock-error", Static)
        password = pw_input.value.strip()

        if not password:
            error_label.update("  Password cannot be empty.")
            pw_input.focus()
            return

        error_label.update("  Unlocking…")

        try:
            vault_path = _get_default_vault_path()
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.vault_store import VaultStore
            from nyxora.core.session_core import SessionManager

            engine = CryptoEngine()
            store = VaultStore(engine)
            root_key = store.open(vault_path, password)
            store.close()

            sm = SessionManager()
            sm.create_session(vault_path, password, root_key)

            from nyxora.core.memory_guard import wipe_memory
            wipe_memory(root_key)

            error_label.update("")
            self.dismiss(True)

        except Exception as exc:
            err = str(exc)
            if "wrong password" in err.lower() or "mac" in err.lower() or "decrypt" in err.lower():
                msg = "  Wrong password — please try again."
            else:
                msg = f"  Error: {err[:60]}"
            error_label.update(msg)
            pw_input.value = ""
            pw_input.focus()


# ── Create vault screen ───────────────────────────────────────────

class CreateVaultScreen(Screen):
    """
    Full-screen vault creation overlay.

    Shown by NyxoraApp when no vault file exists yet.
    Guides the user through creating their first vault.
    On success, dismisses itself; the app then shows the main layout.
    """

    BINDINGS = [
        Binding("escape", "app.quit", "Quit", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="unlock-box"):
            yield Static(
                "\n  ◆  NYXORA\n",
                id="unlock-icon",
            )
            yield Static("Create Your Vault", id="unlock-title")
            yield Static(
                "Choose a master password — store it somewhere safe",
                id="unlock-subtitle",
            )
            yield Label("Master password", classes="form-label")
            yield Input(
                placeholder="Enter master password…",
                password=True,
                id="create-password",
            )
            yield Label("Confirm password", classes="form-label")
            yield Input(
                placeholder="Confirm master password…",
                password=True,
                id="create-confirm",
            )
            yield Static("", id="create-error", classes="form-error")
            yield Static(
                "  Min 8 characters · Stored locally · Never uploaded",
                id="unlock-subtitle",
            )
            with Horizontal():
                yield Button(
                    "  CREATE VAULT",
                    id="btn-create",
                    classes="primary",
                )
                yield Button(
                    "  QUIT",
                    id="btn-quit-create",
                )

    def on_mount(self) -> None:
        self.query_one("#create-password", Input).focus()

    # ── Events ──────────────────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "create-password":
            self.query_one("#create-confirm", Input).focus()
        elif event.input.id == "create-confirm":
            self._attempt_create()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            self._attempt_create()
        elif event.button.id == "btn-quit-create":
            self.app.exit()

    # ── Create logic ─────────────────────────────────────────────

    def _attempt_create(self) -> None:
        pw_input = self.query_one("#create-password", Input)
        confirm_input = self.query_one("#create-confirm", Input)
        error_label = self.query_one("#create-error", Static)

        password = pw_input.value
        confirm = confirm_input.value

        # Validation
        if len(password) < 8:
            error_label.update("  Password must be at least 8 characters.")
            pw_input.focus()
            return

        if password != confirm:
            error_label.update("  Passwords do not match.")
            confirm_input.value = ""
            confirm_input.focus()
            return

        error_label.update("  Creating vault…")

        try:
            vault_path = _get_default_vault_path()
            vault_path.parent.mkdir(parents=True, exist_ok=True)

            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.vault_store import VaultStore
            from nyxora.core.session_core import SessionManager

            engine = CryptoEngine()
            store = VaultStore(engine)
            root_key = store.create(vault_path, password)
            store.close()

            sm = SessionManager()
            sm.create_session(vault_path, password, root_key)

            from nyxora.core.memory_guard import wipe_memory
            wipe_memory(root_key)

            error_label.update("")
            self.dismiss(True)

        except Exception as exc:
            error_label.update(f"  Failed: {str(exc)[:60]}")
            pw_input.value = ""
            confirm_input.value = ""
            pw_input.focus()
