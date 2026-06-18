"""Unit tests for the exe launcher's Windows console maximize helper.

ctypes.windll does not exist off Windows, so the win32 path is exercised by
patching the platform seam and creating ctypes.windll with create=True
(otherwise the patch target would not resolve on Linux/mac CI). The real
maximize is verified manually in the release pre-flight exe-launch check.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import nyxora.tui.launcher as launcher


def test_maximize_console_window_invokes_showmaximize_on_win32(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    fake_windll = MagicMock()
    fake_windll.kernel32.GetConsoleWindow.return_value = 4242  # non-zero hwnd

    with patch("ctypes.windll", create=True, new=fake_windll):
        launcher._maximize_console_window()

    fake_windll.kernel32.GetConsoleWindow.assert_called_once_with()
    # SW_MAXIMIZE == 3, applied to the real console hwnd
    fake_windll.user32.ShowWindow.assert_called_once_with(4242, 3)


def test_maximize_console_window_noop_when_no_console(monkeypatch):
    """A zero hwnd (no attached console) must not call ShowWindow."""
    monkeypatch.setattr(sys, "platform", "win32")
    fake_windll = MagicMock()
    fake_windll.kernel32.GetConsoleWindow.return_value = 0

    with patch("ctypes.windll", create=True, new=fake_windll):
        launcher._maximize_console_window()

    fake_windll.user32.ShowWindow.assert_not_called()


def test_maximize_console_window_noop_off_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    fake_windll = MagicMock()

    with patch("ctypes.windll", create=True, new=fake_windll):
        launcher._maximize_console_window()

    # Returned at the platform guard — windll never touched.
    fake_windll.kernel32.GetConsoleWindow.assert_not_called()
    fake_windll.user32.ShowWindow.assert_not_called()


def test_maximize_console_window_swallows_errors(monkeypatch):
    """A failure in the win32 calls must never propagate (cosmetic only)."""
    monkeypatch.setattr(sys, "platform", "win32")
    fake_windll = MagicMock()
    fake_windll.kernel32.GetConsoleWindow.side_effect = OSError("boom")

    with patch("ctypes.windll", create=True, new=fake_windll):
        launcher._maximize_console_window()  # must not raise
