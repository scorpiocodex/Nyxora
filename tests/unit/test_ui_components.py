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
