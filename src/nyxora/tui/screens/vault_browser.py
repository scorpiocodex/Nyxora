"""Vault browser — main TUI screen showing entry list and detail panel."""
from __future__ import annotations

import time
from typing import Optional

import pyotp
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static

from nyxora.core.vault_store import EntryRecord


class EntryListItem(ListItem):
    """A single entry row in the vault browser list."""

    DEFAULT_CSS = ""

    def __init__(self, record: EntryRecord) -> None:
        super().__init__()
        self.record = record

    def compose(self) -> ComposeResult:
        title = self.record.title
        sub = self.record.username or ""
        yield Label(title, classes="entry-title")
        if sub:
            yield Label(sub, classes="entry-sub")


class VaultBrowserScreen(Screen):
    """Main vault browser: entry list (left) + detail panel (right)."""

    BINDINGS = [
        Binding("j,down", "cursor_down", "Down", show=False),
        Binding("k,up",   "cursor_up",   "Up",   show=False),
        Binding("/",       "search",      "Search"),
        Binding("c",       "copy_pass",   "Copy"),
        Binding("e",       "edit",        "Edit",   show=False),
        Binding("d",       "delete",      "Delete", show=False),
        Binding("t",       "totp",        "TOTP"),
        Binding("A",       "audit",       "Audit"),
        Binding("p",       "profiles",    "Profiles", show=False),
        Binding("escape",  "clear_search","Clear",    show=False),
    ]

    _filter: reactive[str] = reactive("", recompose=False)
    _selected_id: reactive[str | None] = reactive(None, recompose=False)
    _show_password: reactive[bool] = reactive(False, recompose=False)

    def __init__(
        self,
        entries: list[EntryRecord],
        vault_path: str,
        session_id: str,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._all_entries: list[EntryRecord] = entries
        self._vault_path = vault_path
        self._session_id = session_id

    def compose(self) -> ComposeResult:
        yield Static(
            f"◆ NYXORA  ·  OBSIDIAN TACTICAL"
            f"  ·  {self._vault_path.split('/')[-1]}"
            f"  ·  {len(self._all_entries)} entries"
            f"  ·  session {self._session_id[:8]}…",
            id="tui-header",
        )
        with Horizontal(id="app-grid"):
            with Vertical(id="left-panel"):
                yield Static("ENTRIES", id="panel-title")
                yield Static("⟨/⟩ filter…", id="search-bar")
                yield ListView(id="entry-list")
            with Vertical(id="right-panel"):
                with ScrollableContainer(id="detail-scroll"):
                    yield Static("", id="detail-content")
        yield Footer()

    def on_mount(self) -> None:
        self._populate_list(self._all_entries)

    def _filtered_entries(self) -> list[EntryRecord]:
        if not self._filter:
            return self._all_entries
        q = self._filter.lower()
        return [
            e for e in self._all_entries
            if q in e.title.lower()
            or q in (e.username or "").lower()
            or q in (e.url or "").lower()
            or any(q in t.lower() for t in e.tags)
        ]

    def _populate_list(self, entries: list[EntryRecord]) -> None:
        lv = self.query_one("#entry-list", ListView)
        lv.clear()
        for entry in entries:
            lv.append(EntryListItem(entry))
        if entries:
            lv.index = 0
            self._selected_id = entries[0].id
            self._render_detail(entries[0])

    @on(ListView.Highlighted, "#entry-list")
    def entry_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and isinstance(event.item, EntryListItem):
            self._selected_id = event.item.record.id
            self._show_password = False
            self._render_detail(event.item.record)

    def _render_detail(self, record: EntryRecord) -> None:
        from nyxora.core.intel_engine import IntelEngine
        from nyxora.core.crypto_engine import CryptoEngine
        _engine = CryptoEngine(
            argon2_memory=65536, argon2_time=1, argon2_parallelism=1
        )
        _intel = IntelEngine(_engine)
        entropy = _intel.score_entropy(record.password)
        strength = _intel.classify_strength(entropy)

        pw_display = record.password if self._show_password else "●" * min(len(record.password), 16)
        strength_colors = {
            "Excellent": "#2A7A4A", "Strong": "#3A7A9A",
            "Fair": "#C89A30", "Weak": "#CC3333"
        }
        sc = strength_colors.get(strength, "#888780")

        totp_line = ""
        if getattr(record, "totp_secret", None):
            code = pyotp.TOTP(record.totp_secret).now()
            remaining = 30 - (int(time.time()) % 30)
            totp_line = f"\n[#344252]TOTP CODE   [/#344252][#2A7A4A]{code[:3]} {code[3:]}[/#2A7A4A]  [#C89A30]{remaining}s[/#C89A30]"

        tags_str = ""
        if record.tags:
            tags_str = f"\n[#344252]TAGS        [/#344252][#C89A30]{' '.join(record.tags)}[/#C89A30]"

        notes_str = ""
        if record.notes:
            notes_str = f"\n[#344252]NOTES       [/#344252][#556070]{record.notes}[/#556070]"

        import datetime
        modified = datetime.datetime.fromtimestamp(record.updated_at).strftime("%Y-%m-%d")

        detail = (
            f"[#C89A30 bold]{record.title}[/#C89A30 bold]"
            f"  [#2E3C4A]{record.id[:8]}…[/#2E3C4A]\n"
            f"──────────────────────────────────────────\n"
            f"[#344252]USERNAME    [/#344252][#A8B8C8]{record.username or '—'}[/#A8B8C8]\n"
            f"[#344252]PASSWORD    [/#344252][#445462]{pw_display}[/#445462]"
            f"  [#C89A30][press v to reveal][/#C89A30]\n"
            f"[#344252]STRENGTH    [/#344252][{sc}]{strength}  {entropy:.0f} bits[/{sc}]\n"
            f"[#344252]URL         [/#344252][#3A7A9A]{record.url or '—'}[/#3A7A9A]"
            f"{totp_line}{tags_str}{notes_str}\n"
            f"──────────────────────────────────────────\n"
            f"[#344252]MODIFIED    [/#344252][#2E3C4A]{modified}[/#2E3C4A]\n\n"
            f"[c] COPY  [e] EDIT  [t] TOTP  [d] DELETE"
        )
        self.query_one("#detail-content", Static).update(detail)

    def _get_selected(self) -> EntryRecord | None:
        lv = self.query_one("#entry-list", ListView)
        item = lv.highlighted_child
        if item and isinstance(item, EntryListItem):
            return item.record
        return None

    def action_cursor_down(self) -> None:
        self.query_one("#entry-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        self.query_one("#entry-list", ListView).action_cursor_up()

    def action_search(self) -> None:
        self.app.push_screen("search")

    def action_clear_search(self) -> None:
        self._filter = ""
        search_bar = self.query_one("#search-bar", Static)
        search_bar.update("⟨/⟩ filter…")
        self._populate_list(self._all_entries)

    def action_copy_pass(self) -> None:
        record = self._get_selected()
        if record:
            try:
                import pyperclip
                pyperclip.copy(record.password)
                self.notify(
                    f"Password copied for {record.title}",
                    title="Copied",
                    severity="information",
                )
            except Exception:
                self.notify("pyperclip not available", severity="warning")

    def action_totp(self) -> None:
        record = self._get_selected()
        if not record:
            return
        if not getattr(record, "totp_secret", None):
            self.notify("No TOTP secret on this entry.", severity="warning")
            return
        code = pyotp.TOTP(record.totp_secret).now()
        try:
            import pyperclip
            pyperclip.copy(code)
            self.notify(f"TOTP code {code} copied!", title="TOTP", severity="information")
        except Exception:
            self.notify(f"TOTP: {code}", title="TOTP", severity="information")

    def action_audit(self) -> None:
        self.app.push_screen("audit")

    def action_profiles(self) -> None:
        from nyxora.cli.helpers import load_profiles
        data = load_profiles()
        active = data.get("active", "default")
        profiles = list(data.get("profiles", {}).keys())
        self.notify(
            f"Active: {active}  ·  Profiles: {', '.join(profiles) or 'none'}",
            title="Vault Profiles",
        )

    def apply_filter(self, query: str) -> None:
        """Called by the search overlay to apply a filter."""
        self._filter = query
        filtered = self._filtered_entries()
        bar = self.query_one("#search-bar", Static)
        if query:
            bar.update(f"⟨/⟩ {query}  ·  {len(filtered)} results")
        else:
            bar.update("⟨/⟩ filter…")
        self._populate_list(filtered)
