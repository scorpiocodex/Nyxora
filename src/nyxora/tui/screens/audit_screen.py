"""Audit dashboard screen."""
from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

from nyxora.core.vault_store import EntryRecord


class AuditScreen(Screen[None]):
    """Vault health score and entry audit overview."""

    BINDINGS = [
        Binding("escape,q", "back", "Back"),
    ]

    def __init__(self, entries: list[EntryRecord], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._entries = entries

    def compose(self) -> ComposeResult:
        yield Static(
            "◆ NYXORA  ·  SECURITY AUDIT  ·  [dim]Esc to go back[/dim]",
            id="tui-header",
        )
        yield Static("", id="audit-content")
        yield Footer()

    def on_mount(self) -> None:
        self._render_audit()

    def _render_audit(self) -> None:
        from nyxora.core.crypto_engine import CryptoEngine
        from nyxora.core.intel_engine import IntelEngine

        _engine = CryptoEngine(
            argon2_memory=65536, argon2_time=1, argon2_parallelism=1
        )
        _intel = IntelEngine(_engine)
        score = _intel.compute_health_score(self._entries)

        grade_colors = {
            "A": "#2A7A4A", "B": "#3A7A9A",
            "C": "#C89A30", "D": "#CC8800", "F": "#CC3333",
        }
        gc = grade_colors.get(score.grade, "#888780")

        bar_w = 30

        def pbar(val: int, max_val: int, color: str = "#C89A30") -> str:
            filled = int((val / max_val) * bar_w) if max_val else 0
            return f"[{color}]{'█' * filled}[/{color}][#1A2430]{'░' * (bar_w - filled)}[/#1A2430]"

        content = (
            f"[{gc} bold]  GRADE {score.grade}[/{gc} bold]"
            f"  [{gc}]{score.total}/100[/{gc}]\n\n"
            f"  [#344252]Strength  [/#344252] {pbar(score.strength_score, 40)}  [#A8B8C8]{score.strength_score}/40[/#A8B8C8]\n"
            f"  [#344252]Breach-free[/#344252] {pbar(score.breach_score, 25, '#2A7A4A')}  [#A8B8C8]{score.breach_score}/25[/#A8B8C8]\n"
            f"  [#344252]No reuse  [/#344252] {pbar(score.duplicate_score, 15, '#3A7A9A')}  [#A8B8C8]{score.duplicate_score}/15[/#A8B8C8]\n"
            f"  [#344252]Age       [/#344252] {pbar(score.age_score, 10, '#C89A30')}  [#A8B8C8]{score.age_score}/10[/#A8B8C8]\n"
            f"  [#344252]TOTP      [/#344252] {pbar(score.totp_score, 10, '#2A7A4A')}  [#A8B8C8]{score.totp_score}/10[/#A8B8C8]\n\n"
            f"  ─────────────────────────────────────────────────────\n"
            f"  [#344252]Total entries   [/#344252][#A8B8C8]{score.total_entries}[/#A8B8C8]\n"
            f"  [#344252]Duplicates      [/#344252]"
            f"[#CC3333]{score.duplicate_count}[/#CC3333]\n"
            f"  [#344252]Overdue >90d    [/#344252]"
            f"[#C89A30]{score.old_entries_count}[/#C89A30]\n"
            f"  [#344252]TOTP enabled    [/#344252]"
            f"[#2A7A4A]{score.totp_enabled_count}[/#2A7A4A]\n\n"
            f"  [#2E3C4A]Run 'nyx security audit' for full HIBP breach analysis.[/#2E3C4A]"
        )

        self.query_one("#audit-content", Static).update(content)

    def action_back(self) -> None:
        self.app.pop_screen()
