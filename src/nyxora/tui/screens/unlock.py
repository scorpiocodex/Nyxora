"""
Nyxora TUI v3.0.0 — UnlockScreen and CreateVaultScreen.
Obsidian Tactical design with ambient background.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from nyxora.tui.screens._shared_bg import (
    BG_PATTERN, NyxBackground, NyxBottomBar,
    NyxCornerInfo, NyxSep, NyxTopBar,
)


def _get_default_vault_path() -> Path:
    return Path.home() / ".nyxora" / "vault.nyx"


def _read_kdf_salt(vault_path: Path) -> bytes | None:
    salt_path = vault_path.parent / (vault_path.stem + ".salt")
    try:
        return salt_path.read_bytes() if salt_path.exists() else None
    except Exception:
        return None


# ── Unlock screen ─────────────────────────────────────────────────

class UnlockScreen(Screen):
    """Full-screen vault unlock overlay with Obsidian Tactical design."""

    BINDINGS = [Binding("escape", "app.quit", "Quit", show=True)]

    DEFAULT_CSS = """
    UnlockScreen {
        background: #060810;
    }
    #unlock-center {
        width: 100%;
        height: 1fr;
        align: center middle;
    }
    #unlock-box {
        width: 52;
        height: auto;
        background: #08111A;
        border: tall #1C2A3A;
        padding: 2 3;
        align: center middle;
    }
    #unlock-box-top-accent {
        width: 100%;
        height: 1;
        background: transparent;
        color: #C89A30;
        text-align: center;
        margin-bottom: 1;
    }
    #unlock-icon {
        width: 100%;
        text-align: center;
        color: #C89A30;
        margin-bottom: 1;
    }
    #unlock-title {
        width: 100%;
        text-align: center;
        color: #C89A30;
        text-style: bold;
        margin-bottom: 0;
    }
    #unlock-subtitle {
        width: 100%;
        text-align: center;
        color: #243342;
        margin-bottom: 1;
    }
    #unlock-ver {
        width: 100%;
        text-align: center;
        color: #3A4A2A;
        margin-bottom: 1;
    }
    #unlock-password {
        width: 100%;
        margin-bottom: 0;
    }
    #unlock-error {
        width: 100%;
        color: #9A3A3A;
        min-height: 1;
    }
    #unlock-btns {
        width: 100%;
        height: auto;
        margin-top: 1;
    }
    #btn-unlock {
        width: 1fr;
    }
    #btn-quit-unlock {
        width: 8;
    }
    #unlock-hint {
        width: 100%;
        text-align: center;
        color: #141E28;
        margin-top: 1;
    }
    .nyx-corners-top {
        width: 100%;
        height: auto;
    }
    .nyx-corners-bot {
        width: 100%;
        height: auto;
    }
    .corner-spacer {
        width: 1fr;
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        from nyxora import __version__

        with Vertical(id="unlock-ui"):
            yield NyxTopBar([
                ("VAULT:LOCKED", True),
                ("SESSION:CLEARED", False),
                ("KEYRING:ACTIVE", False),
                ("OFFLINE", True),
            ])

            # Corner info top
            with Horizontal(classes="nyx-corners-top"):
                yield NyxCornerInfo(
                    "CIPHER SUITE",
                    ["XCHACHA20-POLY1305", "ARGON2ID · 64MB", "AES-256-GCM"],
                )
                yield Static("", classes="corner-spacer")
                yield NyxCornerInfo(
                    "SESSION STATUS",
                    ["KEYRING: ACTIVE", "SESSION: NONE", "VAULT: LOCKED"],
                )

            # Centre form
            with Vertical(id="unlock-center"):
                with Vertical(id="unlock-box"):
                    yield Static(
                        "[#C89A30]──────────────────────────────[/#C89A30]",
                        id="unlock-box-top-accent",
                    )
                    yield Static(
                        "[bold #C89A30]◆  NYXORA[/bold #C89A30]",
                        id="unlock-icon",
                    )
                    yield Static(
                        "[bold]Tactical Secrets Vault[/bold]",
                        id="unlock-title",
                    )
                    yield Static(
                        "Enter your master password to unlock",
                        id="unlock-subtitle",
                    )
                    yield Static(
                        f"[#1A2838]v{__version__} · NEXUS[/#1A2838]",
                        id="unlock-ver",
                    )
                    yield NyxSep()
                    yield Input(
                        placeholder="Master password…",
                        password=True,
                        id="unlock-password",
                    )
                    yield Static("", id="unlock-error")
                    with Horizontal(id="unlock-btns"):
                        yield Button(
                            "⬡  UNLOCK VAULT",
                            id="btn-unlock",
                            classes="primary",
                        )
                        yield Button("QUIT", id="btn-quit-unlock")
                    yield Static(
                        "[#0E1820]OFFLINE  ·  ZERO-KNOWLEDGE  ·  ENCRYPTED[/#0E1820]",
                        id="unlock-hint",
                    )

            # Corner info bottom
            with Horizontal(classes="nyx-corners-bot"):
                yield NyxCornerInfo(
                    "VAULT PATH",
                    ["~/.nyxora/vault.nyx", "32-BYTE SALT", "SCHEMA v2"],
                )
                yield Static("", classes="corner-spacer")
                yield NyxCornerInfo(
                    "BUILD INFO",
                    [f"NYXORA v{__version__}", "NEXUS RELEASE", "SCORPIOCODEX"],
                )

            yield NyxBottomBar()

    def on_mount(self) -> None:
        self.query_one("#unlock-password", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "unlock-password":
            self._attempt_unlock()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-unlock":
            self._attempt_unlock()
        elif event.button.id == "btn-quit-unlock":
            self.app.exit()

    def _attempt_unlock(self) -> None:
        pw_input    = self.query_one("#unlock-password", Input)
        error_label = self.query_one("#unlock-error",   Static)
        password    = pw_input.value.strip()

        if not password:
            error_label.update("  [red]Password cannot be empty.[/red]")
            pw_input.focus()
            return

        error_label.update("  [#C89A30]Deriving key…[/#C89A30]")

        try:
            vault_path = _get_default_vault_path()
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.vault_store   import (
                VaultStore,
                recover_interrupted_password_change,
            )
            from nyxora.core.memory_guard  import wipe_memory
            from nyxora.cli.helpers        import save_session

            engine = CryptoEngine()
            # Heal any interrupted change-password swap before the salt
            # is read, so the pair on disk is always consistent.
            recover_interrupted_password_change(vault_path)
            salt   = _read_kdf_salt(vault_path)
            if salt is None:
                error_label.update(
                    "  [red]Salt not found. Re-initialise with 'nyx vault init'.[/red]"
                )
                return

            root_key = engine.derive_key(password, salt)
            store    = VaultStore(engine)
            store.open(vault_path, root_key)
            store.close()

            session_id = str(uuid.uuid4())
            save_session(session_id, str(vault_path), root_key.hex())
            wipe_memory(root_key)

            error_label.update("")
            self.dismiss(True)

        except Exception as exc:
            err = str(exc).lower()
            if any(k in err for k in (
                "wrong password", "mac", "decrypt", "hmac",
                "integrity", "mismatch", "fingerprint",
            )):
                msg = "  [red]Wrong password — please try again.[/red]"
            else:
                msg = f"  [red]Error: {str(exc)[:70]}[/red]"
            error_label.update(msg)
            pw_input.value = ""
            pw_input.focus()


# ── Create vault screen ───────────────────────────────────────────

class CreateVaultScreen(Screen):
    """Full-screen vault creation overlay."""

    BINDINGS = [Binding("escape", "app.quit", "Quit", show=True)]

    DEFAULT_CSS = """
    CreateVaultScreen {
        background: #060810;
    }
    #create-center {
        width: 100%;
        height: 1fr;
        align: center middle;
    }
    #create-box {
        width: 52;
        height: auto;
        background: #08111A;
        border: tall #1C2A3A;
        padding: 2 3;
        align: center middle;
    }
    .nyx-corners-top { width: 100%; height: auto; }
    .nyx-corners-bot { width: 100%; height: auto; }
    .corner-spacer   { width: 1fr; height: 1; }
    """

    def compose(self) -> ComposeResult:
        from nyxora import __version__

        with Vertical(id="create-ui"):
            yield NyxTopBar([
                ("CREATE VAULT", True),
                ("FIRST RUN", False),
                ("OFFLINE", True),
            ])

            with Horizontal(classes="nyx-corners-top"):
                yield NyxCornerInfo(
                    "CIPHER SUITE",
                    ["XCHACHA20-POLY1305", "ARGON2ID · 64MB"],
                )
                yield Static("", classes="corner-spacer")
                yield NyxCornerInfo(
                    "REQUIREMENTS",
                    ["MIN 8 CHARACTERS", "STORE SECURELY"],
                )

            with Vertical(id="create-center"):
                with Vertical(id="create-box"):
                    yield Static(
                        "[bold #C89A30]◆  NYXORA[/bold #C89A30]",
                        id="unlock-icon",
                    )
                    yield Static(
                        "[bold]Create Your Vault[/bold]",
                        id="unlock-title",
                    )
                    yield Static(
                        "Choose a master password — store it somewhere safe",
                        id="unlock-subtitle",
                    )
                    yield NyxSep()
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
                        "[#141E28]Min 8 characters · Stored locally · Never uploaded[/#141E28]",
                        id="create-hint",
                    )
                    with Horizontal(id="unlock-btns"):
                        yield Button(
                            "⬡  CREATE VAULT",
                            id="btn-create",
                            classes="primary",
                        )
                        yield Button("QUIT", id="btn-quit-create")

            with Horizontal(classes="nyx-corners-bot"):
                yield NyxCornerInfo(
                    "VAULT PATH",
                    ["~/.nyxora/vault.nyx"],
                )
                yield Static("", classes="corner-spacer")
                yield NyxCornerInfo(
                    "BUILD",
                    [f"v{__version__}", "NEXUS"],
                )

            yield NyxBottomBar()

    def on_mount(self) -> None:
        self.query_one("#create-password", Input).focus()

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

    def _attempt_create(self) -> None:
        pw_input      = self.query_one("#create-password", Input)
        confirm_input = self.query_one("#create-confirm",  Input)
        error_label   = self.query_one("#create-error",    Static)
        password = pw_input.value
        confirm  = confirm_input.value

        if len(password) < 8:
            error_label.update("  [red]Password must be at least 8 characters.[/red]")
            pw_input.focus()
            return
        if password != confirm:
            error_label.update("  [red]Passwords do not match.[/red]")
            confirm_input.value = ""
            confirm_input.focus()
            return

        error_label.update("  [#C89A30]Creating vault…[/#C89A30]")

        try:
            vault_path = _get_default_vault_path()
            vault_path.parent.mkdir(parents=True, exist_ok=True)

            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.vault_store   import VaultStore
            from nyxora.core.memory_guard  import wipe_memory
            from nyxora.cli.helpers        import save_session

            engine   = CryptoEngine()
            salt     = engine.generate_salt()
            root_key = engine.derive_key(password, salt)
            store    = VaultStore(engine)
            store.initialize(vault_path, root_key)
            store.close()

            salt_path = vault_path.parent / (vault_path.stem + ".salt")
            salt_path.write_bytes(salt)

            session_id = str(uuid.uuid4())
            save_session(session_id, str(vault_path), root_key.hex())
            wipe_memory(root_key)

            error_label.update("")
            self.dismiss(True)

        except Exception as exc:
            error_label.update(f"  [red]Failed: {str(exc)[:70]}[/red]")
            pw_input.value      = ""
            confirm_input.value = ""
            pw_input.focus()
