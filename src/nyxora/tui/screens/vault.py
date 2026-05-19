"""
Nyxora TUI v3.0.0 — VaultScreen.

Section 1 of the sidebar navigation.
Shows vault status, info panel, lock button, and optional health check.
"""
from __future__ import annotations

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Button, Label, Static


class VaultScreen(Static):
    """
    Vault management screen — Section 1.

    Displays:
      - UNLOCKED / LOCKED status with colour badge
      - Vault info grid (path, entries, cipher, KDF, last modified)
      - Lock button
      - Health Check button with inline results
    """

    BINDINGS = [
        Binding("l", "lock_vault",   "Lock",         show=True),
        Binding("h", "health_check", "Health Check", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Static(
            " ◆  VAULT MANAGEMENT",
            classes="screen-title",
        )
        yield Static(id="vault-status-badge")
        yield Static("", id="vault-info-grid")
        with Horizontal():
            yield Button(
                "  LOCK VAULT",
                id="btn-lock",
                classes="danger",
            )
            yield Button(
                "  HEALTH CHECK",
                id="btn-health",
            )
        yield Static("", id="health-result")

    def on_mount(self) -> None:
        self._refresh_status()

    def on_show(self) -> None:
        """Refresh when user navigates to this screen."""
        self._refresh_status()

    # ── Refresh display ──────────────────────────────────────────

    def _refresh_status(self) -> None:
        """Update the status badge and info grid from current session."""
        try:
            from nyxora.cli.helpers import load_session, open_vault
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory
            from nyxora import __version__

            session = load_session()
            badge = self.query_one("#vault-status-badge", Static)
            info = self.query_one("#vault-info-grid", Static)

            if session is None:
                badge.update(" ● LOCKED")
                badge.remove_class("status-unlocked")
                badge.add_class("status-locked")
                info.update(
                    "\n  Vault is locked.\n"
                    "  Use [bold]nyx vault unlock[/bold] or restart the app."
                )
                return

            _, vault_path, root_key = session

            # Open vault briefly to read metadata
            engine = CryptoEngine()
            from nyxora.core.vault_store import VaultStore
            store = VaultStore(engine)
            store.open(vault_path, root_key)
            entry_count = store.count_entries()
            vault_id = store.get_vault_id()[:8] if hasattr(store, "get_vault_id") else "—"
            store.close()
            wipe_memory(root_key)

            vp = Path(str(vault_path))
            size_kb = round(vp.stat().st_size / 1024, 1) if vp.exists() else "?"
            modified = (
                __import__("datetime").datetime.fromtimestamp(
                    vp.stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M")
                if vp.exists() else "—"
            )

            badge.update(" ● UNLOCKED")
            badge.remove_class("status-locked")
            badge.add_class("status-unlocked")

            info.update(
                f"\n"
                f"  [dim]Path[/dim]          {vp}\n"
                f"  [dim]Entries[/dim]       {entry_count}\n"
                f"  [dim]Size[/dim]          {size_kb} KB\n"
                f"  [dim]Last modified[/dim] {modified}\n"
                f"  [dim]Cipher[/dim]        Argon2id · XChaCha20-Poly1305\n"
                f"  [dim]Vault ID[/dim]      {vault_id}…\n"
            )

        except Exception as exc:
            try:
                badge = self.query_one("#vault-status-badge", Static)
                badge.update(f" ● ERROR: {str(exc)[:40]}")
            except Exception:
                pass

    # ── Actions ──────────────────────────────────────────────────

    def action_lock_vault(self) -> None:
        self._do_lock()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-lock":
            self._do_lock()
        elif event.button.id == "btn-health":
            self._do_health_check()

    def _do_lock(self) -> None:
        """Lock the vault: wipe session and update display."""
        try:
            from nyxora.cli.helpers import load_session
            from nyxora.core.memory_guard import wipe_memory
            import keyring as _kr

            session = load_session()
            if session is not None:
                _, _vp, _rk = session
                wipe_memory(_rk)

            try:
                _kr.delete_password("nyxora", "session")
            except Exception:
                pass

            session_file = Path.home() / ".nyxora" / "session.key"
            if session_file.exists():
                session_file.unlink(missing_ok=True)

            self._refresh_status()
            # Refresh the header status badge in the parent app
            try:
                self.app._update_header_status()
            except Exception:
                pass
            self.app.notify(
                "Vault locked. Session wiped.",
                title="◆ LOCKED",
                timeout=3,
            )
        except Exception as exc:
            self.app.notify(
                f"Lock failed: {exc}",
                title="Error",
                severity="error",
                timeout=4,
            )

    def _do_health_check(self) -> None:
        """Run vault integrity check and display results."""
        result = self.query_one("#health-result", Static)
        result.update("  Running health check…")

        try:
            from nyxora.cli.helpers import open_vault
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory

            engine = CryptoEngine()
            store, _, root_key, _ = open_vault(engine)
            report = store.verify_integrity()
            store.close()
            wipe_memory(root_key)

            lines = ["\n"]
            all_pass = True
            checks = {
                "Schema fingerprint":    report.get("schema_ok", False),
                "Vault-wide HMAC chain": report.get("hmac_ok", False),
                "Entry integrity":       report.get("entries_ok", False),
                "Audit log integrity":   report.get("audit_ok", False),
            }
            for label, passed in checks.items():
                icon = "✓" if passed else "✗"
                colour = "bold green" if passed else "bold red"
                lines.append(
                    f"  [{colour}]{icon}[/{colour}]  {label}\n"
                )
                if not passed:
                    all_pass = False

            overall = (
                "  [bold green]PASSED[/bold green] — vault integrity verified."
                if all_pass
                else "  [bold red]FAILED[/bold red] — one or more checks failed."
            )
            lines.append(f"\n{overall}\n")
            result.update("".join(lines))

        except Exception as exc:
            result.update(
                f"\n  [bold red]✗[/bold red]  Health check failed: {exc}\n"
            )
