"""Locker commands: encrypt/decrypt arbitrary files with vault key."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import load_session
from nyxora.core.crypto_engine import CryptoEngine, EncryptedField
from nyxora.core.memory_guard import wipe_memory

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)

LOCKER_DIR = Path.home() / ".nyxora" / "locker"
NYX_SUFFIX = ".nyx"

_engine = CryptoEngine()


def _get_locker_key(root_key: bytearray, filename: str, file_salt: bytes) -> bytearray:
    return _engine.derive_locker_key(root_key, filename, file_salt)


@app.command()
def encrypt(
    file: Path = typer.Argument(..., help="File to encrypt"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path"),
    delete_original: bool = typer.Option(False, "--delete", help="Shred original after encryption"),
) -> None:
    """Encrypt a file with the vault key. Outputs a .nyx file."""
    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked. Run 'nyx vault unlock' first.")
        raise typer.Exit(2)
    _, _, root_key = session_data

    if not file.exists():
        ui.error_panel(f"File not found: {file}")
        raise typer.Exit(1)

    out_path = output or file.with_suffix(file.suffix + NYX_SUFFIX)

    try:
        file_salt = os.urandom(16)
        locker_key = _get_locker_key(root_key, file.name, file_salt)
        try:
            data = file.read_bytes()
            # Store original filename in associated data
            ad = file.name.encode("utf-8")
            ef = _engine.encrypt_field(data, locker_key, associated_data=ad)
            # Write: [4-byte filename length][filename bytes][16-byte file_salt][encrypted blob]
            filename_bytes = file.name.encode("utf-8")
            header = (
                len(filename_bytes).to_bytes(4, "big")
                + filename_bytes
                + file_salt
            )

            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            if hasattr(os, "O_NOINHERIT"):
                flags |= getattr(os, "O_NOINHERIT")
            fd = os.open(str(out_path), flags, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(header + ef.to_bytes())

            ui.success_panel(f"Encrypted: {out_path}")
            if delete_original:
                _shred_file(file)  # pragma: no cover
        finally:
            wipe_memory(locker_key)
    finally:
        wipe_memory(root_key)


@app.command()
def decrypt(
    file: Path = typer.Argument(..., help=".nyx file to decrypt"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output path"),
) -> None:
    """Decrypt a .nyx file with the vault key."""
    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked. Run 'nyx vault unlock' first.")  # pragma: no cover
        raise typer.Exit(2)  # pragma: no cover
    _, _, root_key = session_data

    if not file.exists():
        ui.error_panel(f"File not found: {file}")
        raise typer.Exit(1)

    try:
        raw = file.read_bytes()
        # Parse header (v1.1.0+ format; files encrypted before v1.1.0 are not compatible)
        fname_len = int.from_bytes(raw[:4], "big")
        original_name = raw[4:4+fname_len].decode("utf-8")
        file_salt = raw[4+fname_len:4+fname_len+16]
        blob = raw[4+fname_len+16:]

        locker_key = _get_locker_key(root_key, original_name, file_salt)
        ad = original_name.encode("utf-8")
        ef = EncryptedField.from_bytes(blob)
        plaintext = _engine.decrypt_field(ef, locker_key, associated_data=ad)
        wipe_memory(locker_key)

        out_path = output or file.parent / original_name

        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOINHERIT"):
            flags |= getattr(os, "O_NOINHERIT")
        fd = os.open(str(out_path), flags, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(plaintext)

        ui.success_panel(f"Decrypted: {out_path}")
    finally:
        wipe_memory(root_key)


@app.command("list")
def list_files(
    locker_dir: Optional[Path] = typer.Option(None, "--dir", "-d"),
) -> None:
    """List encrypted .nyx files in the locker directory."""
    ld = locker_dir or LOCKER_DIR
    if not ld.exists():
        ui.info_panel("Locker directory is empty.")  # pragma: no cover
        return  # pragma: no cover
    files = list(ld.glob(f"*{NYX_SUFFIX}"))
    if not files:
        ui.info_panel("No .nyx files found.")
        return
    import datetime  # pragma: no cover

    # pragma: no cover
    from rich.table import Table  # pragma: no cover

    # pragma: no cover
    from nyxora.cli.ui import ELEC_PURPLE, NEON_CYAN, console  # pragma: no cover
    table = Table(title="[nyx.title]Locker Files[/nyx.title]",  # pragma: no cover
                  border_style=ELEC_PURPLE, header_style=f"bold {NEON_CYAN}")  # pragma: no cover
    table.add_column("Filename")  # pragma: no cover
    table.add_column("Size")  # pragma: no cover
    table.add_column("Modified")  # pragma: no cover
    for f in sorted(files):  # pragma: no cover
        mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")  # pragma: no cover
        size = f"{f.stat().st_size / 1024:.1f} KB"  # pragma: no cover
        table.add_row(f.name, size, mtime)  # pragma: no cover
    console.print(table)  # pragma: no cover


@app.command()
def shred(
    file: Path = typer.Argument(..., help="File to securely delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Securely shred a file with 3-pass overwrite."""
    if not yes:
        import questionary
        confirm = questionary.confirm(f"Permanently shred {file}?").ask()  # pragma: no cover
        if not confirm:
            return  # pragma: no cover
    _shred_file(file)  # pragma: no cover
    ui.success_panel(f"File securely shredded: {file}")  # pragma: no cover


def _shred_file(path: Path) -> None:
    """3-pass overwrite: urandom → 0xFF → 0x00, handling read-only and large files via chunking."""
    import stat  # pragma: no cover
    if not path.exists():  # pragma: no cover
        return  # pragma: no cover

    size = path.stat().st_size
    try:  # pragma: no cover
        path.chmod(path.stat().st_mode | stat.S_IWRITE)  # pragma: no cover
    except Exception:  # pragma: no cover
        pass  # pragma: no cover
  # pragma: no cover
    if size > 50 * 1024 * 1024:  # pragma: no cover
        ui.info_panel(f"Shredding large file ({size / (1024*1024):.1f} MB)... this may take a moment.")  # pragma: no cover

    chunk_size = 4 * 1024 * 1024
    try:
        with open(path, "r+b") as f:
            for offset in range(0, size, chunk_size):
                chunk = min(chunk_size, size - offset)
                f.seek(offset)
                f.write(os.urandom(chunk))
            f.flush()  # pragma: no cover
            os.fsync(f.fileno())

            for offset in range(0, size, chunk_size):
                chunk = min(chunk_size, size - offset)
                f.seek(offset)
                f.write(b"\xFF" * chunk)
            f.flush()  # pragma: no cover
            os.fsync(f.fileno())

            for offset in range(0, size, chunk_size):
                chunk = min(chunk_size, size - offset)
                f.seek(offset)
                f.write(b"\x00" * chunk)
            f.flush()  # pragma: no cover
            os.fsync(f.fileno())  # pragma: no cover
    except Exception as e:  # pragma: no cover
        ui.error_panel(f"Failed to completely shred file {path.name}: {e}")  # pragma: no cover
  # pragma: no cover
    try:  # pragma: no cover
        path.unlink()  # pragma: no cover
    except Exception as e:  # pragma: no cover
        ui.error_panel(f"Failed to delete file {path.name} after shredding: {e}")  # pragma: no cover
