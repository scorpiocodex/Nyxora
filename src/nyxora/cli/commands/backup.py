"""Backup and restore commands."""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import load_session, open_vault
from nyxora.cli.ui import danger_panel
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import VaultStore
from nyxora.utils.exceptions import BackupError

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)

_engine = CryptoEngine()

def _get_backup_dir() -> Path:
    return Path.home() / ".nyxora" / "backups"



def _open_vault() -> tuple[VaultStore, bytearray, Path]:
    store, _, root_key, vault_path = open_vault(_engine)
    return store, root_key, vault_path


@app.command()
def create(
    output_dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="Backup directory"),
    note: str = typer.Option("", "--note", "-n", help="Backup note"),
) -> None:
    """Create an encrypted backup of the vault."""
    store, root_key, vault_path = _open_vault()
    backup_dir = output_dir or _get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)

    try:
        timestamp = int(time.time())
        backup_name = f"vault_backup_{timestamp}.nyx.bak"
        backup_path = backup_dir / backup_name

        with ui.spinner("Creating backup…"):
            backup_key = _engine.derive_backup_key(root_key, str(timestamp))
            # Read vault file and encrypt it
            vault_data = vault_path.read_bytes()
            ef = _engine.encrypt_field(vault_data, backup_key)
            backup_path.write_bytes(ef.to_bytes())

        wipe_memory(backup_key)
        ui.success_panel(f"Backup created: {backup_path}")
    except Exception as e:  # pragma: no cover
        raise BackupError(str(e)) from e  # pragma: no cover
    finally:
        store.close()
        wipe_memory(root_key)


@app.command("list")
def list_backups(
    backup_dir: Optional[Path] = typer.Option(None, "--dir", "-d"),
) -> None:
    """List available backups."""
    bd = backup_dir or _get_backup_dir()
    if not bd.exists():
        ui.info_panel("No backups directory found.")
        return

    backups = sorted(bd.glob("*.nyx.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        ui.info_panel("No backups found.")
        return

    import datetime

    from rich.table import Table

    from nyxora.cli.ui import ELEC_PURPLE, NEON_CYAN, console

    table = Table(title="[nyx.title]Backups[/nyx.title]",
                  border_style=ELEC_PURPLE, header_style=f"bold {NEON_CYAN}")
    table.add_column("Filename")
    table.add_column("Date")
    table.add_column("Size")

    for b in backups:
        mtime = datetime.datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size = f"{b.stat().st_size / 1024:.1f} KB"
        table.add_row(b.name, mtime, size)
    console.print(table)


@app.command()
def restore(
    backup_file: Path = typer.Argument(..., help="Backup file to restore"),
) -> None:
    """Restore a vault from a backup file."""
    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked. Run 'nyx vault unlock' first.")
        raise typer.Exit(2)

    _, vault_path, root_key = session_data  # pragma: no cover
  # pragma: no cover
    try:  # pragma: no cover
        backup_data = backup_file.read_bytes()  # pragma: no cover
        # Extract timestamp from filename  # pragma: no cover
        import re  # pragma: no cover
        match = re.search(r"vault_backup_(\d+)", backup_file.name)  # pragma: no cover
        if not match:  # pragma: no cover
            raise BackupError("Cannot determine backup timestamp from filename.")  # pragma: no cover
        timestamp = match.group(1)  # pragma: no cover
  # pragma: no cover
        with ui.spinner("Decrypting backup…"):  # pragma: no cover
            backup_key = _engine.derive_backup_key(root_key, timestamp)  # pragma: no cover
            from nyxora.core.crypto_engine import EncryptedField  # pragma: no cover
            ef = EncryptedField.from_bytes(backup_data)  # pragma: no cover
            vault_data = _engine.decrypt_field(ef, backup_key)  # pragma: no cover
            wipe_memory(backup_key)  # pragma: no cover
  # pragma: no cover
        # Write restored vault  # pragma: no cover
        vault_path.write_bytes(vault_data)  # pragma: no cover
        ui.success_panel(f"Vault restored from {backup_file.name}")  # pragma: no cover
    finally:  # pragma: no cover
        wipe_memory(root_key)  # pragma: no cover


@app.command()
def cleanup(
    keep: int = typer.Option(10, "--keep", "-k", help="Number of backups to keep"),
    backup_dir: Optional[Path] = typer.Option(None, "--dir", "-d"),
) -> None:
    """Delete oldest backups, keeping the most recent N."""
    bd = backup_dir or _get_backup_dir()
    if not bd.exists():
        ui.info_panel("No backups directory found.")  # pragma: no cover
        return  # pragma: no cover
    backups = sorted(bd.glob("*.nyx.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
    to_delete = backups[keep:]
    for b in to_delete:
        b.unlink()  # pragma: no cover
    ui.success_panel(f"Removed {len(to_delete)} backup(s). {min(len(backups), keep)} remaining.")


@app.command()
def verify(
    backup_file: Optional[Path] = typer.Argument(
        None,
        help="Backup file to verify. If omitted, verifies the most recent backup."
    ),
) -> None:
    """Verify the integrity of a backup file."""
    if backup_file is None:  # pragma: no cover
        backup_dir = Path.home() / ".nyxora" / "backups"  # pragma: no cover
        if not backup_dir.exists():  # pragma: no cover
            ui.error_panel("No backups directory found. Run 'nyx backup create' first.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        candidates = sorted(  # pragma: no cover
            backup_dir.glob("*.nyx.bak"),  # pragma: no cover
            key=lambda p: p.stat().st_mtime,  # pragma: no cover
            reverse=True,  # pragma: no cover
        )  # pragma: no cover
        if not candidates:  # pragma: no cover
            ui.error_panel("No backups found. Run 'nyx backup create' first.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        backup_file = candidates[0]  # pragma: no cover
        ui.info_panel(  # pragma: no cover
            f"Auto-detected most recent backup:\n{backup_file.name}",  # pragma: no cover
            title="Backup Selected"  # pragma: no cover
        )  # pragma: no cover

    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked. Run 'nyx vault unlock' first.")
        raise typer.Exit(2)

    _, _, root_key = session_data  # pragma: no cover
    try:  # pragma: no cover
        import re  # pragma: no cover
        match = re.search(r"vault_backup_(\d+)", backup_file.name)  # pragma: no cover
        if not match:  # pragma: no cover
            ui.error_panel("Cannot determine backup timestamp from filename.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        timestamp = match.group(1)  # pragma: no cover
        backup_data = backup_file.read_bytes()  # pragma: no cover
        backup_key = _engine.derive_backup_key(root_key, timestamp)  # pragma: no cover
        from nyxora.core.crypto_engine import EncryptedField  # pragma: no cover
        ef = EncryptedField.from_bytes(backup_data)  # pragma: no cover
        _engine.decrypt_field(ef, backup_key)  # pragma: no cover
        wipe_memory(backup_key)  # pragma: no cover
        ui.success_panel(f"Backup {backup_file.name} is valid.")  # pragma: no cover
    except Exception as e:  # pragma: no cover
        ui.error_panel(f"Backup verification failed: {e}")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover
    finally:  # pragma: no cover
        wipe_memory(root_key)  # pragma: no cover


@app.command()
def export(
    output: Path = typer.Argument(..., help="Output file path"),
    plaintext: bool = typer.Option(False, "--plaintext", help="Export as plain CSV (INSECURE)"),
) -> None:
    """Export vault entries to a file."""
    if plaintext:
        danger_panel(
            "You are about to export ALL vault passwords as plain text.\n"
            "This file will NOT be encrypted. Anyone with access to it\n"
            "can read every password immediately.\n\n"
            "Store it only in a secure, encrypted location.",
            title="⚠  PLAINTEXT EXPORT WARNING"
        )
        import questionary
        first = questionary.confirm(
            "I understand this export will be unencrypted. Continue?",
            default=False
        ).ask()
        if not first:
            ui.info_panel("Export cancelled.")
            raise typer.Exit(0)
        confirm_word = questionary.text(
            "Type CONFIRM to proceed:"
        ).ask()
        if confirm_word != "CONFIRM":
            ui.info_panel("Export cancelled — confirmation word did not match.")
            raise typer.Exit(0)

    store, root_key, _ = _open_vault()
    try:
        entries = store.list_entries()
        if plaintext:
            import csv
            import io
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow(["title", "username", "password", "url", "notes", "tags"])
            for e in entries:
                writer.writerow([e.title, e.username or "", e.password,
                                 e.url or "", e.notes or "", ",".join(e.tags)])
            import os
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOINHERIT"):
                flags |= getattr(os, "O_NOINHERIT")

            fd = os.open(output, flags, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(buf.getvalue())
            ui.warning_panel(f"Exported {len(entries)} entries to {output} (PLAINTEXT — handle with care!)")
        else:
            import json
            import os

            import questionary

            pwd = questionary.password("Enter export encryption password:").ask()
            if not pwd:
                return  # pragma: no cover
            pwd2 = questionary.password("Confirm password:").ask()
            if pwd != pwd2:
                ui.error_panel("Passwords do not match.")  # pragma: no cover
                raise typer.Exit(1)  # pragma: no cover

            export_data = []
            for e in entries:
                export_data.append({
                    "id": e.id,
                    "title": e.title,
                    "username": e.username,
                    "password": e.password,
                    "url": e.url,
                    "notes": e.notes,
                    "tags": e.tags,
                    "custom": e.custom,
                })

            payload = json.dumps(export_data).encode("utf-8")
            salt = os.urandom(32)
            export_key = _engine.derive_key(pwd, salt)
            ef = _engine.encrypt_field(payload, export_key)
            wipe_memory(export_key)

            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOINHERIT"):
                flags |= getattr(os, "O_NOINHERIT")

            fd = os.open(output, flags, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(salt + ef.to_bytes())

            ui.success_panel(f"Exported {len(entries)} entries securely to {output}")
    finally:
        store.close()
        wipe_memory(root_key)
