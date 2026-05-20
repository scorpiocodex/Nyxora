"""
Nyxora TUI v3.0.0 — AddEntryScreen.

Pushed as a full-screen overlay from ManageScreen when the user
presses 'a'. On success, dismisses with True so ManageScreen
reloads its entry list.
"""
from __future__ import annotations

import math
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Label, Static


class AddEntryScreen(Screen):
    """Full-screen add-entry form."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+s", "save",   "Save",   show=True),
    ]

    def compose(self) -> ComposeResult:
        with ScrollableContainer():
            with Vertical(id="unlock-box"):
                yield Static(" ◆  ADD NEW ENTRY", classes="screen-title")
                yield Static("", id="add-error", classes="form-error")

                yield Label("Title *", classes="form-label")
                yield Input(placeholder="e.g. GitHub",
                            id="add-title")

                yield Label("Username", classes="form-label")
                yield Input(placeholder="e.g. alice",
                            id="add-username")

                yield Label("Password", classes="form-label")
                with Horizontal():
                    yield Input(placeholder="Leave blank to generate",
                                password=True,
                                id="add-password")
                    yield Button("GENERATE", id="btn-gen-pw")

                yield Static("", id="add-pw-strength", classes="form-hint")

                yield Label("URL", classes="form-label")
                yield Input(placeholder="https://…",
                            id="add-url")

                yield Label("Tags  (space-separated)", classes="form-label")
                yield Input(placeholder="e.g. dev personal",
                            id="add-tags")

                yield Label("Notes", classes="form-label")
                yield Input(placeholder="Optional notes",
                            id="add-notes")

                with Horizontal():
                    yield Button("  SAVE",   id="btn-save",   classes="primary")
                    yield Button("  CANCEL", id="btn-cancel")

    def on_mount(self) -> None:
        self.query_one("#add-title", Input).focus()

    # ── Events ───────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "add-password":
            self._update_strength(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()
        elif event.button.id == "btn-gen-pw":
            self._generate_password()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Tab through fields on Enter; save on last field."""
        order = [
            "add-title", "add-username", "add-password",
            "add-url", "add-tags", "add-notes",
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
        error = self.query_one("#add-error", Static)
        title = self.query_one("#add-title", Input).value.strip()

        if not title:
            error.update("  Title is required.")
            self.query_one("#add-title", Input).focus()
            return

        password = self.query_one("#add-password", Input).value.strip()
        if not password:
            password = self._generate_password(apply=False)

        username = self.query_one("#add-username", Input).value.strip()
        url      = self.query_one("#add-url",      Input).value.strip()
        notes    = self.query_one("#add-notes",    Input).value.strip()
        tags_raw = self.query_one("#add-tags",     Input).value.strip()
        tags     = [t for t in tags_raw.split() if t]

        error.update("  Saving…")

        try:
            from nyxora.cli.helpers import open_vault
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory

            engine = CryptoEngine()
            store, _, root_key, _ = open_vault(engine)
            store.add_entry(
                title=title,
                username=username,
                password=password,
                url=url,
                notes=notes,
                tags=tags,
            )
            store.close()
            wipe_memory(root_key)

            self.dismiss(True)

        except Exception as exc:
            error.update(f"  Save failed: {str(exc)[:60]}")

    # ── Helpers ──────────────────────────────────────────────────

    def _generate_password(self, apply: bool = True) -> str:
        """Generate a strong password; optionally populate the input."""
        try:
            from nyxora.core.crypto_engine import CryptoEngine
            engine = CryptoEngine()
            pw = engine.generate_password(length=24)
        except Exception:
            import secrets, string
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            pw = "".join(secrets.choice(alphabet) for _ in range(24))

        if apply:
            self.query_one("#add-password", Input).value = pw
            self._update_strength(pw)
        return pw

    def _update_strength(self, password: str) -> None:
        """Show live strength label below the password field."""
        try:
            hint = self.query_one("#add-pw-strength", Static)
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
