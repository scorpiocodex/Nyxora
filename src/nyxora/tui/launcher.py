"""
Nyxora TUI Launcher — exe/app entry point.

When nyx.exe is opened directly (double-clicked or run from terminal
without subcommands), this module routes to the correct screen:
  - No vault found  → CreateVaultScreen (full TUI wizard)
  - Vault locked    → UnlockScreen
  - Vault unlocked  → MainApp with ManageScreen active

This file is the PyInstaller entry point. The CLI (main.py) is unchanged.
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def _maximize_console_window() -> None:
    """Best-effort maximize the hosting console on Windows. No-op elsewhere.

    Double-clicking the packaged exe opens a default-sized console; a maximized
    window gives the TUI room and avoids short-viewport clipping. Purely
    cosmetic — any failure is swallowed so it can never block launch.
    """
    if sys.platform != "win32":
        return
    try:
        SW_MAXIMIZE = 3
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            return
        hwnd = windll.kernel32.GetConsoleWindow()
        if hwnd:
            windll.user32.ShowWindow(hwnd, SW_MAXIMIZE)
    except Exception:
        pass  # a cosmetic maximize must never block launch


def get_default_vault_path() -> Path:
    """Return the default vault path (~/.nyxora/vault.nyx)."""
    return Path.home() / ".nyxora" / "vault.nyx"


def vault_exists() -> bool:
    """Check whether the default vault file exists."""
    return get_default_vault_path().exists()


def is_vault_unlocked() -> bool:
    """Check whether there is an active session for the default vault."""
    try:
        from nyxora.cli.helpers import load_session
        session = load_session()
        if session is None:
            return False
        _, vault_path, _ = session
        from pathlib import Path as _Path
        return _Path(vault_path).resolve() == get_default_vault_path().resolve()
    except Exception:
        return False


def run_app() -> None:
    """
    Entry point called by the exe.
    Routes to the appropriate TUI screen based on vault state.
    """
    try:
        # Degrade gracefully on legacy cp1252 consoles so the startup-error
        # path (and any glyphs) never raises UnicodeEncodeError.
        for _stream in (sys.stdout, sys.stderr):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        _maximize_console_window()
        from nyxora.tui.app import NyxoraApp
        app = NyxoraApp(
            start_screen=_resolve_start_screen(),
            exe_mode=True,
        )
        app.run()
    except Exception as exc:
        print(f"\n  ◆ NYXORA — startup error: {exc}\n", file=sys.stderr)
        sys.exit(1)


def _resolve_start_screen() -> str:
    """
    Determine which screen to show on startup.
    Returns one of: 'create', 'unlock', 'manage'
    """
    if not vault_exists():
        return "create"
    if is_vault_unlocked():
        return "manage"
    return "unlock"


if __name__ == "__main__":
    run_app()
