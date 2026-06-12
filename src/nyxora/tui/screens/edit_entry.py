"""
Nyxora TUI v3.0.0 — EditEntryScreen.

Pushed as a full-screen overlay from ManageScreen when the user
presses 'e' on a selected entry. Pre-populates all fields.
On success, dismisses with True so ManageScreen reloads.
"""
from __future__ import annotations

import math

from nyxora.tui._markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Static

from nyxora.core.vault_store import EntryRecord


class EditEntryScreen(Screen):
    """Full-screen edit-entry form, pre-populated from an EntryRecord."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+s", "save",   "Save",   show=True),
    ]

    def __init__(self, record: EntryRecord, **kwargs) -> None:
        super().__init__(**kwargs)
        self._record = record

    def compose(self) -> ComposeResult:
        e = self._record
        with ScrollableContainer():
            with Vertical(id="unlock-box"):
                yield Static(
                    f" ◆  EDIT ENTRY — {escape(e.title)}",
                    classes="screen-title",
                )
                yield Static("", id="edit-error", classes="form-error")

                yield Label("Title *", classes="form-label")
                yield Input(value=e.title or "",
                            id="edit-title")

                yield Label("Username", classes="form-label")
                yield Input(value=e.username or "",
                            id="edit-username")

                yield Label("Password", classes="form-label")
                with Horizontal():
                    yield Input(value=e.password or "",
                                password=True,
                                id="edit-password")
                    yield Button("GENERATE", id="btn-gen-pw")

                yield Static("", id="edit-pw-strength", classes="form-hint")

                yield Label("URL", classes="form-label")
                yield Input(value=e.url or "",
                            id="edit-url")

                yield Label("Tags  (space-separated)", classes="form-label")
                yield Input(value=" ".join(e.tags) if e.tags else "",
                            id="edit-tags")

                yield Label("Notes", classes="form-label")
                yield Input(value=e.notes or "",
                            id="edit-notes")

                yield Label("TOTP Secret  (leave blank to keep existing)",
                            classes="form-label")
                yield Input(placeholder="Base32 secret or leave blank",
                            id="edit-totp")

                with Horizontal():
                    yield Button("  SAVE CHANGES", id="btn-save",
                                 classes="primary")
                    yield Button("  CANCEL",       id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#edit-title", Input).focus()
        # Show current password strength on open
        pw = self._record.password or ""
        if pw:
            self._update_strength(pw)

    # ── Events ───────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "edit-password":
            self._update_strength(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-gen-pw":
            self._generate_password()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        order = [
            "edit-title", "edit-username", "edit-password",
            "edit-url", "edit-tags", "edit-notes", "edit-totp",
        ]
        idx = order.index(event.input.id) if event.input.id in order else -1
        if idx >= 0 and idx < len(order) - 1:
            self.query_one(f"#{order[idx + 1]}", Input).focus()
        else:
            self.action_save()

    # ── Actions ──────────────────────────────────────────────────

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_save(self) -> None:
        error = self.query_one("#edit-error", Static)
        title = self.query_one("#edit-title", Input).value.strip()

        if not title:
            error.update("  Title is required.")
            self.query_one("#edit-title", Input).focus()
            return

        password = self.query_one("#edit-password", Input).value.strip()
        username = self.query_one("#edit-username", Input).value.strip()
        url      = self.query_one("#edit-url",      Input).value.strip()
        notes    = self.query_one("#edit-notes",    Input).value.strip()
        tags_raw = self.query_one("#edit-tags",     Input).value.strip()
        tags     = [t for t in tags_raw.split() if t]
        totp_new = self.query_one("#edit-totp",     Input).value.strip()

        error.update("  Saving…")

        try:
            from nyxora.cli.helpers import open_vault
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory

            engine = CryptoEngine()
            store, _, root_key, _ = open_vault(engine)

            kwargs: dict = dict(
                entry_id = self._record.id,
                title    = title,
                username = username,
                url      = url,
                notes    = notes,
                tags     = tags,
            )
            if password:
                kwargs["password"] = password
            if totp_new:
                kwargs["totp_secret"] = totp_new

            store.update_entry(**kwargs)
            store.close()
            wipe_memory(root_key)

            self.dismiss(True)

        except Exception as exc:
            error.update(f"  Save failed: {escape(str(exc)[:60])}")

    # ── Helpers ──────────────────────────────────────────────────

    def _generate_password(self) -> None:
        try:
            from nyxora.core.crypto_engine import CryptoEngine
            engine = CryptoEngine()
            pw = engine.generate_password(length=24)
        except Exception:
            import secrets, string
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            pw = "".join(secrets.choice(alphabet) for _ in range(24))
        self.query_one("#edit-password", Input).value = pw
        self._update_strength(pw)

    def _update_strength(self, password: str) -> None:
        try:
            hint = self.query_one("#edit-pw-strength", Static)
            if not password:
                hint.update("")
                return
            charset = 0
            if any(c.islower()     for c in password): charset += 26
            if any(c.isupper()     for c in password): charset += 26
            if any(c.isdigit()     for c in password): charset += 10
            if any(not c.isalnum() for c in password): charset += 32
            bits = int(len(password) * math.log2(max(charset, 1)))
            if bits < 28:   label = f"[bold red]Very Weak[/bold red]  {bits} bits"
            elif bits < 40: label = f"[red]Weak[/red]  {bits} bits"
            elif bits < 60: label = f"[#C89A30]Fair[/#C89A30]  {bits} bits"
            elif bits < 128: label = f"[#3A7A9A]Strong[/#3A7A9A]  {bits} bits"
            else:            label = f"[bold green]Excellent[/bold green]  {bits} bits"
            hint.update(f"  {label}")
        except Exception:
            pass
