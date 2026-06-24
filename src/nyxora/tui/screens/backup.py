"""
Nyxora TUI v3.0.0 — BackupScreen.

Section 3: create, list, and verify vault backups.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import List, Tuple

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Button, Static

from nyxora.tui._markup import escape
from nyxora.tui.screens._shared_bg import (
    NyxBottomBar,
    NyxCornerInfo,
    NyxTopBar,
)
from nyxora.utils.paths import nyxora_home


class BackupScreen(Static):
    """
    Backup management screen — Section 3.

    Displays a table of existing backups and provides:
      - Create Backup  (b key or button)
      - Verify latest  (v key or row button)
      - Refresh list   (r key)
    """

    BINDINGS = [
        Binding("b", "create_backup",  "Create", show=True),
        Binding("v", "verify_latest",  "Verify", show=True),
        Binding("r", "refresh",        "Refresh", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield NyxTopBar([("BACKUP MANAGER", True), ("SECTION 3", False), ("OFFLINE", False)])
        with Horizontal(classes="nyx-corners-top"):
            yield NyxCornerInfo("LAST BACKUP", ["SEE LIST BELOW", "SHUTIL.COPY2"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("STORAGE", ["~/.nyxora/backups", "ENCRYPTED"])
        yield Static(" ◆  BACKUP MANAGEMENT", classes="screen-title")
        with Horizontal(id="action-bar"):
            yield Button("  CREATE BACKUP", id="btn-create", classes="primary")
            yield Button("  VERIFY LATEST", id="btn-verify")
            yield Button("  REFRESH",       id="btn-refresh")
        yield Static("", id="backup-status")
        yield Static(
            "\n  [dim]Loading backups…[/dim]",
            id="backup-table-wrap",
        )
        with Horizontal(classes="nyx-corners-bot"):
            yield NyxCornerInfo("FORMAT", ["AES SNAPSHOT", ".NYX.BAK"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("VERIFY", ["VAULTSTORE.OPEN", "HMAC CHECK"])
        yield NyxBottomBar()

    def on_mount(self) -> None:
        self._load_backups()

    def on_show(self) -> None:
        self._load_backups()

    # ── Data loading ─────────────────────────────────────────────

    def _backup_dir(self) -> Path:
        return nyxora_home() / "backups"

    def _list_backups(self) -> List[Tuple[str, str, str]]:
        """
        Return list of (filename, date_str, size_str) tuples,
        sorted newest-first.
        """
        bd = self._backup_dir()
        if not bd.exists():
            return []
        files = sorted(
            bd.glob("*.nyx.bak"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        result = []
        for f in files:
            mtime = datetime.datetime.fromtimestamp(
                f.stat().st_mtime
            ).strftime("%Y-%m-%d  %H:%M")
            size_kb = round(f.stat().st_size / 1024, 1)
            result.append((f.name, mtime, f"{size_kb} KB"))
        return result

    def _load_backups(self) -> None:
        """Rebuild the backup table display."""
        try:
            backups = self._list_backups()
            wrap = self.query_one("#backup-table-wrap", Static)

            if not backups:
                wrap.update(
                    "\n  [dim]No backups found.[/dim]\n"
                    "  Press [bold]b[/bold] or click CREATE BACKUP to create one."
                )
                return

            # Build a plain-text table since DataTable needs app loop
            lines = ["\n"]
            lines.append(
                f"  [dim]{'Filename':<42}  {'Date':<18}  {'Size':>8}[/dim]\n"
            )
            lines.append(f"  {'─' * 72}\n")
            for i, (name, date, size) in enumerate(backups):
                marker = "[bold #C89A30]▸[/bold #C89A30]" if i == 0 else " "
                lines.append(
                    f"  {marker} {escape(name):<40}  {date:<18}  {size:>8}\n"
                )
            lines.append(f"\n  [dim]{len(backups)} backup(s) found.[/dim]\n")
            wrap.update("".join(lines))

        except Exception as exc:
            try:
                self.query_one("#backup-table-wrap", Static).update(
                    f"\n  [red]Error loading backups: {escape(str(exc))}[/red]"
                )
            except Exception:
                pass

    # ── Button events ────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            self.action_create_backup()
        elif event.button.id == "btn-verify":
            self.action_verify_latest()
        elif event.button.id == "btn-refresh":
            self.action_refresh()

    # ── Actions ──────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self._load_backups()

    def action_create_backup(self) -> None:
        status = self.query_one("#backup-status", Static)
        status.update("  Creating backup…")
        try:
            import shutil
            import time

            from nyxora.cli.helpers import open_vault
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory

            engine = CryptoEngine()
            store, _, root_key, vault_path = open_vault(engine)
            store.close()
            wipe_memory(root_key)

            bd = self._backup_dir()
            bd.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            dest = bd / f"vault_backup_{ts}.nyx.bak"
            shutil.copy2(str(vault_path), str(dest))

            status.update(
                f"  [bold green]✓[/bold green]  Backup created: {dest.name}"
            )
            self.app.notify(
                f"Backup created: {dest.name}",
                title="◆ Backup",
                timeout=4,
            )
            self._load_backups()

        except Exception as exc:
            status.update(f"  [red]Backup failed: {escape(str(exc))}[/red]")
            self.app.notify(
                f"Backup failed: {escape(str(exc))}",
                severity="error",
                timeout=4,
            )

    def action_verify_latest(self) -> None:
        status = self.query_one("#backup-status", Static)
        status.update("  Verifying latest backup…")
        try:
            from nyxora.cli.helpers import load_session
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory
            from nyxora.core.vault_store import VaultStore

            session = load_session()
            if session is None:
                status.update(
                    "  [red]Vault is locked — unlock first to verify.[/red]"
                )
                return

            _, _vault_path, root_key = session
            backups = self._list_backups()
            if not backups:
                status.update("  [#C89A30]No backups to verify.[/#C89A30]")
                wipe_memory(root_key)
                return

            latest_name = backups[0][0]
            backup_path = self._backup_dir() / latest_name

            # Open the backup using the vault's root_key directly
            engine = CryptoEngine()
            store  = VaultStore(engine)
            store.open(backup_path, root_key)
            count = len(store.list_entries())
            store.close()
            wipe_memory(root_key)

            status.update(
                f"  [bold green]✓[/bold green]  "
                f"{escape(latest_name)} is valid  ({count} entries)."
            )
            self.app.notify(
                f"Verified: {escape(latest_name)}",
                title="◆ Backup OK",
                timeout=3,
            )

        except Exception as exc:
            status.update(f"  [red]✗  Verify failed: {escape(str(exc))}[/red]")
            self.app.notify(
                f"Verify failed: {escape(str(exc))}",
                severity="error",
                timeout=4,
            )
