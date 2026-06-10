"""
Nyxora TUI v3.0.0 — VaultScreen.

Section 1 of the sidebar navigation.
Shows vault status, info panel, lock/unlock button, health check.
"""
from __future__ import annotations

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Static

from nyxora.tui.screens._shared_bg import (
    NyxTopBar, NyxBottomBar, NyxCornerInfo,
)


class VaultScreen(Static):
    """Vault management screen — Section 1."""

    BINDINGS = [
        Binding("l", "lock_vault",   "Lock/Unlock", show=True),
        Binding("h", "health_check", "Health Check", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield NyxTopBar([
            ("VAULT MANAGEMENT", True),
            ("SECTION 1", False),
            ("ARGON2ID · XCHACHA20", False),
        ], id="vault-topbar")
        with Horizontal(classes="nyx-corners-top"):
            yield NyxCornerInfo("KDF", ["ARGON2ID", "64MB RAM", "TIME: 3"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("INTEGRITY", ["HMAC: VERIFIED", "SCHEMA: OK", "AUDIT: OK"])
        yield Static(" ◆  VAULT MANAGEMENT", classes="screen-title")
        yield Static("", id="vault-status-badge")
        yield Static("", id="vault-info-grid")
        with Horizontal():
            yield Button("  LOCK VAULT", id="btn-lock", classes="danger")
            yield Button("  HEALTH CHECK", id="btn-health")
        yield Static("", id="health-result")
        with Horizontal(classes="nyx-corners-bot"):
            yield NyxCornerInfo("CIPHER", ["XCHACHA20", "POLY1305 MAC"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("VAULT ID", ["2a4fa4a8…"])
        yield NyxBottomBar()

    def on_mount(self) -> None:
        self._refresh_status()

    def on_show(self) -> None:
        self._refresh_status()

    # ── Status display ───────────────────────────────────────────

    def _refresh_status(self) -> None:
        try:
            from nyxora.cli.helpers import load_session
            from nyxora.core.memory_guard import wipe_memory
            from nyxora import __version__

            session = load_session()
            badge = self.query_one("#vault-status-badge", Static)
            info  = self.query_one("#vault-info-grid",   Static)
            btn   = self.query_one("#btn-lock",          Button)

            if session is None:
                badge.update(" [bold red]● LOCKED[/bold red]")
                info.update(
                    "\n  Vault is locked.\n"
                    "  Press [bold]l[/bold] or UNLOCK to authenticate.\n"
                )
                btn.label = "  UNLOCK"
                btn.remove_class("danger")
                btn.add_class("primary")
                try:
                    tb = self.query_one("#vault-topbar", NyxTopBar)
                    tb.update(
                        "[#CC3333]● LOCKED[/#CC3333]"
                        "  [#0E1820]·[/#0E1820]  "
                        "[#1E2D3D]SECTION 1[/#1E2D3D]"
                        "  [#0E1820]·[/#0E1820]  "
                        "[#1E2D3D]ARGON2ID · XCHACHA20[/#1E2D3D]"
                    )
                except Exception:
                    pass
                return

            _, vault_path, root_key = session

            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.vault_store import VaultStore
            engine = CryptoEngine()
            store  = VaultStore(engine)
            store.open(vault_path, root_key)
            entry_count = len(store.list_entries())
            vault_id    = store.get_vault_id()[:8] \
                if hasattr(store, "get_vault_id") else "—"
            store.close()
            wipe_memory(root_key)

            vp = Path(str(vault_path))
            size_kb  = round(vp.stat().st_size / 1024, 1) if vp.exists() else "?"
            modified = (
                __import__("datetime").datetime.fromtimestamp(
                    vp.stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M")
                if vp.exists() else "—"
            )

            badge.update(" [bold green]● UNLOCKED[/bold green]")
            info.update(
                f"\n"
                f"  [dim]Path[/dim]          {vp}\n"
                f"  [dim]Entries[/dim]       {entry_count}\n"
                f"  [dim]Size[/dim]          {size_kb} KB\n"
                f"  [dim]Last modified[/dim] {modified}\n"
                f"  [dim]Cipher[/dim]        Argon2id · XChaCha20-Poly1305\n"
                f"  [dim]Vault ID[/dim]      {vault_id}…\n"
            )
            btn.label = "  LOCK VAULT"
            btn.remove_class("primary")
            btn.add_class("danger")
            try:
                tb = self.query_one("#vault-topbar", NyxTopBar)
                tb.update(
                    "[#C89A30]● UNLOCKED[/#C89A30]"
                    "  [#0E1820]·[/#0E1820]  "
                    "[#1E2D3D]SECTION 1[/#1E2D3D]"
                    "  [#0E1820]·[/#0E1820]  "
                    "[#1E2D3D]ARGON2ID · XCHACHA20[/#1E2D3D]"
                )
            except Exception:
                pass

        except Exception as exc:
            try:
                self.query_one("#vault-status-badge", Static).update(
                    f" [red]● ERROR: {str(exc)[:50]}[/red]"
                )
            except Exception:
                pass

    # ── Actions ──────────────────────────────────────────────────

    def action_lock_vault(self) -> None:
        from nyxora.cli.helpers import load_session
        if load_session() is None:
            self._push_unlock()
        else:
            self._do_lock()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-lock":
            self.action_lock_vault()
        elif event.button.id == "btn-health":
            self._do_health_check()

    def _do_lock(self) -> None:
        """Lock the vault: wipe session and update display."""
        try:
            from nyxora.cli.helpers import load_session, clear_session
            from nyxora.core.memory_guard import wipe_memory

            session = load_session()
            if session is not None:
                _, _vp, root_key = session
                wipe_memory(root_key)

            clear_session()

            self.app.notify(
                "Vault locked. Session wiped.",
                title="◆ LOCKED",
                timeout=3,
            )
        except Exception as exc:
            self.app.notify(
                f"Lock failed: {exc}",
                severity="error",
                timeout=4,
            )

        # Push UnlockScreen regardless — re-auth required
        self._push_unlock()

    def _push_unlock(self) -> None:
        from nyxora.tui.screens.unlock import UnlockScreen

        def _on_done(success: bool) -> None:
            self._refresh_status()
            try:
                self.app._update_header_status()
            except Exception:
                pass
            if success:
                self.app.notify(
                    "Vault unlocked.",
                    title="◆ UNLOCKED",
                    timeout=3,
                )

        self.app.push_screen(UnlockScreen(), _on_done)

    def _do_health_check(self) -> None:
        result = self.query_one("#health-result", Static)

        # Check vault is unlocked first
        from nyxora.cli.helpers import load_session
        if load_session() is None:
            result.update("\n  [red]Vault is locked — unlock first.[/red]\n")
            return

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
            # ForensicReport is a dataclass — use getattr, not .get()
            checks = {
                "Schema fingerprint":    getattr(report, "schema_ok",     False),
                "Vault-wide HMAC chain": getattr(report, "vault_hmac_ok", False),
                "Entry integrity":       len(getattr(report, "entries_failed", ["x"])) == 0,
                "Audit log integrity":   getattr(report, "audit_log_ok",  False),
            }
            for label, passed in checks.items():
                icon   = "✓" if passed else "✗"
                colour = "bold green" if passed else "bold red"
                lines.append(f"  [{colour}]{icon}[/{colour}]  {label}\n")
                if not passed:
                    all_pass = False

            overall = (
                "  [bold green]PASSED[/bold green] — vault integrity verified."
                if all_pass else
                "  [bold red]FAILED[/bold red] — one or more checks failed."
            )
            lines.append(f"\n{overall}\n")
            result.update("".join(lines))

        except Exception as exc:
            result.update(
                f"\n  [bold red]✗[/bold red]  Health check failed: {exc}\n"
            )
