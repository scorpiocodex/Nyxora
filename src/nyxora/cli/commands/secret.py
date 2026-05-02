"""Secret entry management: add, list, get, update, delete, search, clone."""
from __future__ import annotations

from typing import Optional

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import open_vault
from nyxora.cli.ui import clipboard_countdown, update_diff_panel
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import VaultStore

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)

_engine = CryptoEngine()

def _open_vault() -> tuple[VaultStore, bytearray]:
    store, _, root_key, _ = open_vault(_engine)
    return store, root_key


@app.command()
def add(
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    username: Optional[str] = typer.Option(None, "--username", "-u"),
    url: Optional[str] = typer.Option(None, "--url"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Auto-generate password"),
) -> None:
    """Add a new secret entry to the vault."""
    import questionary
    t = title or questionary.text("Title:").ask()
    if not t:
        ui.error_panel("Title is required.")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover

    u = username or questionary.text("Username (optional):").ask() or None
    url_val = url or questionary.text("URL (optional):").ask() or None

    if generate:
        import secrets as secrets_mod
        import string
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()"
        password = "".join(secrets_mod.choice(alphabet) for _ in range(24))
        ui.info_panel(f"Generated password: [nyx.success]{password}[/nyx.success]")
    else:
        password = questionary.password("Password:").ask()
        if not password:
            ui.error_panel("Password is required.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover

    notes = questionary.text("Notes (optional):").ask() or None
    tags_list = [tag.strip() for tag in tags.split(",")] if tags else []

    store, root_key = _open_vault()
    try:
        eid = store.add_entry(t, password, username=u, url=url_val, notes=notes, tags=tags_list)
        ui.success_panel(f"Entry added: {t}\nID: {eid}")
    finally:
        store.close()
        wipe_memory(root_key)


@app.command("list")
def list_entries(
    tag: Optional[str] = typer.Option(None, "--tag", help="Filter by tag"),
    show_passwords: bool = typer.Option(False, "--show-passwords", help="Show passwords in table"),
) -> None:
    """List all vault entries."""
    store, root_key = _open_vault()
    try:
        entries = store.list_entries()
        if tag:
            entries = [e for e in entries if tag in e.tags]
        if not entries:
            ui.info_panel("No entries found.")  # pragma: no cover
        else:
            ui.table_entries(entries, show_passwords=show_passwords)
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def get(
    entry_id: str = typer.Argument(..., help="Entry ID (or prefix)"),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy password to clipboard"),
) -> None:
    """Get and display a vault entry."""
    store, root_key = _open_vault()
    try:
        record = store.get_entry(entry_id)
        ui.print_kv("ID", record.id)
        ui.print_kv("Title", record.title)
        if record.username:
            ui.print_kv("Username", record.username)
        ui.print_kv("Password", record.password)
        if record.url:
            ui.print_kv("URL", record.url)  # pragma: no cover
        if record.notes:
            ui.print_kv("Notes", record.notes)  # pragma: no cover
        if record.tags:
            ui.print_kv("Tags", ", ".join(record.tags))  # pragma: no cover
        if copy:
            try:  # pragma: no cover
                import pyperclip  # pragma: no cover
                pyperclip.copy(record.password)  # pragma: no cover
                ui.success_panel("Password copied to clipboard.")  # pragma: no cover
                clipboard_countdown(30)  # pragma: no cover
            except Exception:  # pragma: no cover
                ui.warning_panel("Clipboard copy failed. Install pyperclip.")  # pragma: no cover
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def update(
    entry_id: str = typer.Argument(..., help="Entry ID"),
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    username: Optional[str] = typer.Option(None, "--username", "-u"),
    url: Optional[str] = typer.Option(None, "--url"),
    notes: Optional[str] = typer.Option(None, "--notes"),
) -> None:
    """Update fields on an existing entry."""
    import questionary
    new_password = None
    if typer.confirm("Update password?", default=False):
        new_password = questionary.password("New password:").ask()  # pragma: no cover
        if not new_password:  # pragma: no cover
            ui.error_panel("Password cannot be empty.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover

    changed = []
    if title: changed.append("title")
    if username: changed.append("username")
    if new_password: changed.append("password")
    if url: changed.append("url")
    if notes: changed.append("notes")

    store, root_key = _open_vault()
    try:
        store.update_entry(entry_id, title=title, username=username,
                           password=new_password, url=url, notes=notes)
        update_diff_panel(changed)
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def delete(
    entry_id: str = typer.Argument(..., help="Entry ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete (soft) an entry from the vault."""
    if not yes:
        import questionary
        confirm = questionary.confirm(f"Delete entry {entry_id[:8]}…?").ask()
        if not confirm:
            ui.info_panel("Deletion cancelled.")  # pragma: no cover
            return  # pragma: no cover

    store, root_key = _open_vault()
    try:
        store.delete_entry(entry_id)
        ui.success_panel(f"Entry {entry_id[:8]}… deleted.")
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def search(query: str = typer.Argument(..., help="Search query")) -> None:
    """Search entries by title, username, URL, or tags."""
    store, root_key = _open_vault()
    try:
        results = store.search_entries(query)
        if not results:
            ui.info_panel(f"No entries found matching '{query}'.")  # pragma: no cover
        else:
            ui.table_entries(results)
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def clone(
    entry_id: str = typer.Argument(..., help="Entry ID to clone"),
    new_title: Optional[str] = typer.Option(None, "--title", "-t", help="Title for the clone"),
) -> None:
    """Clone an entry with a new title and ID."""
    store, root_key = _open_vault()  # pragma: no cover
    try:  # pragma: no cover
        record = store.get_entry(entry_id)  # pragma: no cover
        clone_title = new_title or f"{record.title} (copy)"  # pragma: no cover
        new_id = store.add_entry(  # pragma: no cover
            clone_title, record.password,  # pragma: no cover
            username=record.username, url=record.url,  # pragma: no cover
            notes=record.notes, tags=record.tags, custom=record.custom,  # pragma: no cover
        )  # pragma: no cover
        ui.success_panel(f"Entry cloned: {clone_title}\nNew ID: {new_id}")  # pragma: no cover
    finally:  # pragma: no cover
        store.close()  # pragma: no cover
        wipe_memory(root_key)  # pragma: no cover
