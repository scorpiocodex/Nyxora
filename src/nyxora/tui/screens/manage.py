"""
Nyxora TUI v3.0.0 — ManageScreen.

Section 2: 2-panel vault browser.
Left panel : search input + filtered entry list
Right panel: full entry detail + copy/edit/delete/TOTP actions
"""
from __future__ import annotations

import math
import time
from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Button, Input, ListItem, ListView, Static

from nyxora.core.vault_store import EntryRecord


# ── Entry list item ───────────────────────────────────────────────

class EntryItem(ListItem):
    """A single row in the left-panel entry list."""

    def __init__(self, record: EntryRecord) -> None:
        self.record = record
        title    = record.title    or "—"
        username = record.username or ""
        super().__init__(
            Static(f" {title}\n [dim]{username}[/dim]"),
            id=f"ei-{record.id[:8]}",
            classes="entry-item",
        )


# ── Manage screen ─────────────────────────────────────────────────

class ManageScreen(Static):
    """
    2-panel vault browser — Section 2.

    Key bindings (active when this screen has focus):
        /  → focus search
        a  → add entry   (wired in Prompt 7)
        e  → edit entry  (wired in Prompt 7)
        c  → copy password to clipboard
        t  → copy TOTP code to clipboard
        d  → delete (two-press confirmation)
        p  → toggle password visibility in detail
        Esc → clear search / deselect
    """

    BINDINGS = [
        Binding("/",      "focus_search",  "Search", show=True),
        Binding("a",      "add_entry",     "Add",    show=True),
        Binding("e",      "edit_entry",    "Edit",   show=True),
        Binding("c",      "copy_pw",       "Copy",   show=True),
        Binding("u",      "copy_user",     "User",   show=True),
        Binding("y",      "copy_url",      "URL",    show=True),
        Binding("t",      "show_totp",     "TOTP",   show=True),
        Binding("d",      "delete_entry",  "Delete", show=True),
        Binding("p",      "toggle_pw",     "Reveal", show=False),
        Binding("escape", "clear_search",  "Clear",  show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._entries:  List[EntryRecord]       = []
        self._filtered: List[EntryRecord]       = []
        self._selected: Optional[EntryRecord]   = None
        self._show_password: bool               = False
        self._delete_pending: bool              = False

    # ── Layout ───────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static(" ◆  MANAGE VAULT", classes="screen-title")
        with Horizontal(id="manage-layout"):
            # Left: entry list
            with Vertical(id="entry-list-panel"):
                yield Input(
                    placeholder="  / to search…",
                    id="entry-search",
                )
                yield ListView(id="entry-items")
            # Right: detail + actions
            with Vertical(id="entry-detail-panel"):
                with ScrollableContainer(id="entry-detail-scroll"):
                    yield Static(
                        "\n  Select an entry from the list.",
                        id="entry-detail",
                    )
                with Horizontal(id="action-bar"):
                    yield Button("COPY",   id="btn-copy",   classes="primary")
                    yield Button("USER",   id="btn-user")
                    yield Button("URL",    id="btn-url")
                    yield Button("EDIT",   id="btn-edit")
                    yield Button("TOTP",   id="btn-totp")
                    yield Button("DELETE", id="btn-delete", classes="danger")

    # ── Lifecycle ────────────────────────────────────────────────

    def on_mount(self) -> None:
        self._load_entries()
        self.set_interval(1.0, self._tick)

    def on_show(self) -> None:
        """Reload entries whenever the user navigates back here."""
        self._load_entries()

    # ── Data loading ─────────────────────────────────────────────

    def _load_entries(self) -> None:
        """Load all entries from the vault."""
        try:
            from nyxora.cli.helpers import open_vault
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory

            engine = CryptoEngine()
            store, _, root_key, _ = open_vault(engine)
            self._entries = store.list_entries()
            store.close()
            wipe_memory(root_key)

            self._apply_filter(
                self.query_one("#entry-search", Input).value
            )

        except Exception:
            self._entries  = []
            self._filtered = []
            try:
                self.query_one("#entry-detail", Static).update(
                    "\n  [dim]Vault is locked or unavailable.\n"
                    "  Press [bold]1[/bold] to go to Vault and unlock.[/dim]"
                )
            except Exception:
                pass
            self._rebuild_list()

    def _apply_filter(self, query: str) -> None:
        """Filter entries by search query and rebuild the ListView."""
        q = query.lower().strip()
        if q:
            self._filtered = [
                e for e in self._entries
                if q in (e.title    or "").lower()
                or q in (e.username or "").lower()
                or q in " ".join(e.tags or []).lower()
                or q in (e.url      or "").lower()
            ]
        else:
            self._filtered = list(self._entries)
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        """Repopulate the ListView with current filtered entries."""
        try:
            lv = self.query_one("#entry-items", ListView)
            lv.clear()
            for entry in self._filtered:
                lv.append(EntryItem(entry))

            # Re-select previously selected entry if still present
            if self._selected:
                for i, entry in enumerate(self._filtered):
                    if entry.id == self._selected.id:
                        lv.index = i
                        self._render_detail()
                        return

            self._selected = None
            count = len(self._filtered)
            try:
                self.query_one("#entry-detail", Static).update(
                    f"\n  Select an entry from the list.\n"
                    f"  [dim]{count} {'entry' if count == 1 else 'entries'}[/dim]"
                )
            except Exception:
                pass
        except Exception:
            pass

    # ── Detail rendering ─────────────────────────────────────────

    def _render_detail(self) -> None:
        """Render the selected entry into the right panel."""
        if self._selected is None:
            return
        e = self._selected

        try:
            detail = self.query_one("#entry-detail", Static)

            # Password display
            pw = e.password or ""
            if self._show_password:
                pw_display = pw
                pw_hint    = "[dim]p to hide[/dim]"
            else:
                pw_display = "●" * min(len(pw), 20)
                pw_hint    = "[dim]p to reveal[/dim]"

            # Strength
            strength = _strength_label(pw)

            # TOTP line (only if secret is configured)
            totp_line = ""
            totp_secret = getattr(e, "totp_secret", None)
            if totp_secret:
                try:
                    import pyotp
                    totp_obj   = pyotp.TOTP(totp_secret)
                    code       = totp_obj.now()
                    remaining  = 30 - (int(time.time()) % 30)
                    filled     = remaining // 3
                    bar        = "█" * filled + "░" * (10 - filled)
                    fmt_code   = f"{code[:3]} {code[3:]}" if len(code) == 6 else code
                    totp_line  = (
                        f"  [dim]TOTP[/dim]           "
                        f"[bold green]{fmt_code}[/bold green]  "
                        f"[dim]{bar}  {remaining}s[/dim]\n"
                    )
                except Exception:
                    totp_line = "  [dim]TOTP[/dim]           [dim]—[/dim]\n"

            tags_str  = "  ".join(e.tags)  if e.tags  else "[dim]—[/dim]"
            notes_str = (e.notes or "—").replace("\n", " ")[:80]

            # Delete confirmation overlay
            confirm = (
                "\n  [bold red]Press D again to confirm deletion.[/bold red]\n"
                if self._delete_pending else ""
            )

            text = (
                f"\n"
                f"  [bold #C89A30]{e.title}[/bold #C89A30]"
                f"  [dim]{e.id[:8]}…[/dim]\n"
                f"  {'─' * 44}\n"
                f"  [dim]USERNAME[/dim]       {e.username or '[dim]—[/dim]'}\n"
                f"  [dim]PASSWORD[/dim]       {pw_display}  {pw_hint}\n"
                f"  [dim]STRENGTH[/dim]       {strength}\n"
                f"  [dim]URL[/dim]            [#3A7A9A]{e.url or '—'}[/#3A7A9A]\n"
                f"{totp_line}"
                f"  [dim]TAGS[/dim]           [#C89A30]{tags_str}[/#C89A30]\n"
                f"  [dim]NOTES[/dim]          [dim]{notes_str}[/dim]\n"
                f"  [dim]MODIFIED[/dim]       {_fmt_ts(e.updated_at)}\n"
                f"  {'─' * 44}\n"
                f"{confirm}"
            )
            detail.update(text)
        except Exception:
            pass

    # ── TOTP tick ────────────────────────────────────────────────

    def _tick(self) -> None:
        """Called every second — refreshes TOTP countdown display."""
        if self._selected and getattr(self._selected, "totp_secret", None):
            self._render_detail()

    # ── Events ───────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if isinstance(event.item, EntryItem):
            self._selected       = event.item.record
            self._show_password  = False
            self._delete_pending = False
            self._render_detail()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "entry-search":
            self._apply_filter(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        dispatch = {
            "btn-copy":   self.action_copy_pw,
            "btn-user":   self.action_copy_user,
            "btn-url":    self.action_copy_url,
            "btn-edit":   self.action_edit_entry,
            "btn-totp":   self.action_show_totp,
            "btn-delete": self.action_delete_entry,
        }
        handler = dispatch.get(event.button.id)
        if handler:
            handler()

    # ── Keyboard actions ─────────────────────────────────────────

    def action_focus_search(self) -> None:
        self.query_one("#entry-search", Input).focus()

    def action_clear_search(self) -> None:
        inp = self.query_one("#entry-search", Input)
        if inp.value:
            inp.value = ""
        else:
            self._selected       = None
            self._delete_pending = False
            self._rebuild_list()

    def action_toggle_pw(self) -> None:
        if self._selected:
            self._show_password = not self._show_password
            self._render_detail()

    def action_add_entry(self) -> None:
        from nyxora.tui.screens.add_entry import AddEntryScreen
        self.app.push_screen(AddEntryScreen(), self._on_entry_saved)

    def action_edit_entry(self) -> None:
        if not self._selected:
            self.app.notify("Select an entry first.", timeout=2)
            return
        from nyxora.tui.screens.edit_entry import EditEntryScreen
        self.app.push_screen(
            EditEntryScreen(self._selected),
            self._on_entry_saved,
        )

    def _on_entry_saved(self, success: bool) -> None:
        """Called when AddEntryScreen or EditEntryScreen dismisses."""
        if success:
            self._load_entries()
            self.app.notify("Entry saved.", title="◆ Saved", timeout=2)

    def action_copy_pw(self) -> None:
        if not self._selected:
            self.app.notify("Select an entry first.", timeout=2)
            return
        try:
            import pyperclip
            pyperclip.copy(self._selected.password or "")
            self.app.notify(
                "Password copied. Clears in 30 s.",
                title="◆ Copied",
                timeout=3,
            )
            self.set_timer(30.0, self._clear_clipboard)
        except Exception as exc:
            self.app.notify(
                f"Copy failed: {exc}",
                severity="error",
                timeout=3,
            )

    def action_copy_user(self) -> None:
        if not self._selected:
            self.app.notify("Select an entry first.", timeout=2)
            return
        username = self._selected.username or ""
        if not username:
            self.app.notify("No username for this entry.", timeout=2)
            return
        try:
            import pyperclip
            pyperclip.copy(username)
            self.app.notify(
                f"Username '{username}' copied.",
                title="◆ Copied",
                timeout=3,
            )
        except Exception as exc:
            self.app.notify(
                f"Copy failed: {exc}",
                severity="error",
                timeout=3,
            )

    def action_copy_url(self) -> None:
        if not self._selected:
            self.app.notify("Select an entry first.", timeout=2)
            return
        url = self._selected.url or ""
        if not url:
            self.app.notify("No URL for this entry.", timeout=2)
            return
        try:
            import pyperclip
            pyperclip.copy(url)
            self.app.notify(
                f"URL '{url}' copied.",
                title="◆ Copied",
                timeout=3,
            )
        except Exception as exc:
            self.app.notify(
                f"Copy failed: {exc}",
                severity="error",
                timeout=3,
            )

    def _clear_clipboard(self) -> None:
        try:
            import pyperclip
            pyperclip.copy("")
        except Exception:
            pass

    def action_show_totp(self) -> None:
        if not self._selected:
            self.app.notify("Select an entry first.", timeout=2)
            return
        secret = getattr(self._selected, "totp_secret", None)
        if not secret:
            self.app.notify("No TOTP configured for this entry.", timeout=2)
            return
        try:
            import pyotp
            import pyperclip
            code = pyotp.TOTP(secret).now()
            pyperclip.copy(code)
            self.app.notify(
                f"TOTP {code[:3]} {code[3:]} copied.",
                title="◆ TOTP",
                timeout=3,
            )
        except Exception as exc:
            self.app.notify(f"TOTP error: {exc}", severity="error", timeout=3)

    def action_delete_entry(self) -> None:
        if not self._selected:
            self.app.notify("Select an entry first.", timeout=2)
            return

        if not self._delete_pending:
            self._delete_pending = True
            self._render_detail()
            self.set_timer(3.0, self._cancel_delete)
            return

        # Second press confirmed
        self._delete_pending = False
        self._execute_delete()

    def _cancel_delete(self) -> None:
        self._delete_pending = False
        if self._selected:
            self._render_detail()

    def _execute_delete(self) -> None:
        if not self._selected:
            return
        entry_id = self._selected.id
        title    = self._selected.title or "entry"
        try:
            from nyxora.cli.helpers import open_vault
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory

            engine = CryptoEngine()
            store, _, root_key, _ = open_vault(engine)
            store.delete_entry(entry_id)
            store.close()
            wipe_memory(root_key)

            self._selected       = None
            self._show_password  = False
            self.app.notify(
                f"Deleted: {title}",
                title="◆ Deleted",
                timeout=3,
            )
            self._load_entries()

        except Exception as exc:
            self.app.notify(
                f"Delete failed: {exc}",
                severity="error",
                timeout=4,
            )


# ── Utility functions ────────────────────────────────────────────

def _strength_label(password: str) -> str:
    """Return a Rich-markup strength label for a password string."""
    if not password:
        return "[dim]—[/dim]"
    charset = 0
    if any(c.islower()  for c in password): charset += 26
    if any(c.isupper()  for c in password): charset += 26
    if any(c.isdigit()  for c in password): charset += 10
    if any(not c.isalnum() for c in password): charset += 32
    bits = int(len(password) * math.log2(max(charset, 1)))
    if bits < 28:  return f"[bold red]Very Weak[/bold red]   {bits} bits"
    if bits < 40:  return f"[red]Weak[/red]          {bits} bits"
    if bits < 60:  return f"[#C89A30]Fair[/#C89A30]          {bits} bits"
    if bits < 128: return f"[#3A7A9A]Strong[/#3A7A9A]        {bits} bits"
    return             f"[bold green]Excellent[/bold green]     {bits} bits"


def _fmt_ts(ts: int) -> str:
    """Format a Unix timestamp as YYYY-MM-DD HH:MM."""
    try:
        import datetime
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "—"
