import threading
from unittest.mock import patch

from nyxora.cli.ui import (
    audit_summary_panel,
    checklist_panel,
    clipboard_countdown,
    danger_panel,
    entropy_bar,
    recovery_status_panel,
    session_dashboard,
    strength_badge,
    update_diff_panel,
)


def test_new_ui_components():
    # entropy_bar
    assert "█" in entropy_bar(80)
    assert "░" in entropy_bar(10)
    assert entropy_bar(0) == entropy_bar(0)  # doesn't crash

    # strength_badge
    assert "WEAK" in strength_badge("Weak")
    assert "EXCELLENT" in strength_badge("Excellent")
    assert "UNKNOWN" in strength_badge("Garbage")

    # checklist_panel — just verify it doesn't raise
    checklist_panel("Test", [(True, "item one"), (False, "item two")],
                    subtitle="test subtitle")

    # danger_panel
    danger_panel("danger message", title="TEST")

    # session_dashboard
    session_dashboard("abc123token", "/vault/test.nyx", 42, 0, 300)
    session_dashboard("abc123token", "/vault/test.nyx", 42, 3, 300)

    # audit_summary_panel — all combinations
    audit_summary_panel(10, 0, 0, 0, 0)
    audit_summary_panel(10, 2, 1, 3, 1)

    # update_diff_panel
    update_diff_panel([])
    update_diff_panel(["title", "password"])

    # recovery_status_panel
    recovery_status_panel(True, ["cap.capsule"], ["share_1.bin"])
    recovery_status_panel(False, [], [])

    # clipboard_countdown — the daemon thread must clear the clipboard.
    # Stub pyperclip (headless CI has no clipboard backend, and the real
    # clipboard should not be touched locally) and wait for the thread.
    cleared = threading.Event()

    def fake_copy(value: str) -> None:
        assert value == ""
        cleared.set()

    with patch("pyperclip.copy", fake_copy):
        clipboard_countdown(seconds=0)
        assert cleared.wait(timeout=5)


def test_table_entries_password_visibility(monkeypatch):
    """The real contract for table_entries: the password column is rendered only
    when show_passwords=True; the title always shows. Replaces the hollow
    table_entries calls from the removed test_massive_coverage.py."""
    import io

    from rich.console import Console

    import nyxora.cli.ui as ui
    from nyxora.core.vault_store import EntryRecord

    er = EntryRecord(
        id="abcdef12", title="GitHubAcct", username="alice",
        password="PWVISIBLE9", url="https://x.example", updated_at=0,
    )

    def render(show: bool) -> str:
        buf = io.StringIO()
        # Wide console so 7 columns never wrap and split the values we assert on.
        wide = Console(file=buf, width=200, theme=ui.NYX_THEME, highlight=False)
        monkeypatch.setattr(ui, "console", wide)
        ui.table_entries([er], show_passwords=show)
        return buf.getvalue()

    shown = render(True)
    assert "PWVISIBLE9" in shown   # password column present when requested
    assert "GitHubAcct" in shown

    hidden = render(False)
    assert "PWVISIBLE9" not in hidden  # password withheld by default
    assert "GitHubAcct" in hidden      # title always shown


def test_table_entries_empty_renders_header(monkeypatch):
    """An empty entry list still renders the table header, not a crash."""
    import io

    from rich.console import Console

    import nyxora.cli.ui as ui

    buf = io.StringIO()
    monkeypatch.setattr(
        ui, "console",
        Console(file=buf, width=200, theme=ui.NYX_THEME, highlight=False),
    )
    ui.table_entries([])
    assert "Vault Entries" in buf.getvalue()
