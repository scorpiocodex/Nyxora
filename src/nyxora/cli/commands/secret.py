"""Secret entry management: add, list, get, update, delete, search, clone."""
from __future__ import annotations

from typing import Optional

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import complete_entry_ids, open_vault
from nyxora.cli.ui import clipboard_countdown, is_json_mode, json_out, update_diff_panel
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import EntryRecord, VaultStore

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)

_engine = CryptoEngine()

def _open_vault() -> tuple[VaultStore, bytearray]:
    store, _, root_key, _ = open_vault(_engine)
    return store, root_key


def _resolve_entry(store: VaultStore, entry_id: str) -> EntryRecord:
    """Resolve entry by UUID first, then by title search fallback."""
    from nyxora.utils.exceptions import EntryNotFoundError
    try:
        return store.get_entry(entry_id)
    except EntryNotFoundError:
        results = store.search_entries(entry_id)
        if not results:
            raise EntryNotFoundError(
                f"Entry '{entry_id}' not found by ID or title."
            )
        return results[0]


@app.command()
def add(
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    username: Optional[str] = typer.Option(None, "--username", "-u"),
    url: Optional[str] = typer.Option(None, "--url"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Auto-generate password"),
    custom: Optional[str] = typer.Option(
        None, "--custom", "-x",
        help="Custom fields as key=value pairs, comma-separated. "
             "Example: --custom 'pin=1234,recovery=abc'"
    ),
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

    custom_dict: dict[str, str] = {}
    if custom:
        for pair in custom.split(","):
            if "=" in pair:
                k, _, v = pair.partition("=")
                custom_dict[k.strip()] = v.strip()

    store, root_key = _open_vault()
    try:
        eid = store.add_entry(
            t, password, username=u, url=url_val, notes=notes,
            tags=tags_list, custom=custom_dict,
        )
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
            if is_json_mode():
                json_out([{
                    "id": e.id, "title": e.title,
                    "username": e.username, "url": e.url,
                    "tags": e.tags, "updated_at": e.updated_at,
                } for e in entries])
                return
            ui.table_entries(entries, show_passwords=show_passwords)
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def get(
    entry_id: str = typer.Argument(..., help="Entry ID (or prefix)", autocompletion=complete_entry_ids),
    copy: bool = typer.Option(False, "--copy", "-c", help="Copy password to clipboard"),
) -> None:
    """Get and display a vault entry."""
    store, root_key = _open_vault()
    try:
        record = _resolve_entry(store, entry_id)
        if is_json_mode():
            json_out({
                "id": record.id,
                "title": record.title,
                "username": record.username,
                "password": record.password,
                "url": record.url,
                "notes": record.notes,
                "tags": record.tags,
                "custom": record.custom,
                "created_at": record.created_at,
                "updated_at": record.updated_at,
            })
            return
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
    entry_id: str = typer.Argument(..., help="Entry ID", autocompletion=complete_entry_ids),
    title: Optional[str] = typer.Option(None, "--title", "-t"),
    username: Optional[str] = typer.Option(None, "--username", "-u"),
    url: Optional[str] = typer.Option(None, "--url"),
    notes: Optional[str] = typer.Option(None, "--notes"),
    tags: Optional[str] = typer.Option(
        None, "--tags", help="Comma-separated tags (replaces existing)"
    ),
    totp_secret: Optional[str] = typer.Option(
        None, "--totp-secret",
        help="TOTP base32 secret to store with this entry ('' to clear)"
    ),
) -> None:
    """Update fields on an existing entry."""
    import questionary
    new_password = None
    if typer.confirm("Update password?", default=False):
        new_password = questionary.password("New password:").ask()  # pragma: no cover
        if not new_password:  # pragma: no cover
            ui.error_panel("Password cannot be empty.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover

    tags_list: list[str] | None = None
    if tags is not None:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
        changed_tags = True
    else:
        changed_tags = False

    changed = []
    if title:
        changed.append("title")
    if username:
        changed.append("username")
    if new_password:
        changed.append("password")
    if url:
        changed.append("url")
    if notes:
        changed.append("notes")
    if changed_tags:
        changed.append("tags")
    if totp_secret is not None:
        changed.append("totp-secret")

    store, root_key = _open_vault()
    try:
        record = _resolve_entry(store, entry_id)
        store.update_entry(
            record.id,
            title=title,
            username=username,
            password=new_password,
            url=url,
            notes=notes,
            tags=tags_list,
            totp_secret=totp_secret,
        )
        update_diff_panel(changed)
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def delete(
    entry_id: str = typer.Argument(..., help="Entry ID", autocompletion=complete_entry_ids),
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
        record = _resolve_entry(store, entry_id)
        store.delete_entry(record.id)
        ui.success_panel(f"Entry {record.id[:8]}… deleted.")
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
            if is_json_mode():
                json_out([{
                    "id": e.id, "title": e.title,
                    "username": e.username, "url": e.url,
                    "tags": e.tags,
                } for e in results])
                return
            ui.table_entries(results)
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def totp(
    entry_id: str = typer.Argument(..., help="Entry ID"),
    copy: bool = typer.Option(False, "--copy", "-c",
                              help="Copy code to clipboard"),
    watch: bool = typer.Option(False, "--watch", "-w",
                               help="Refresh every 30s automatically"),
) -> None:
    """Show the live TOTP code for an entry."""
    import time

    import pyotp

    store, root_key = _open_vault()
    try:
        record = _resolve_entry(store, entry_id)
        if not getattr(record, "totp_secret", None):
            ui.error_panel(
                f"Entry '{record.title}' has no TOTP secret stored.\n"
                f"Add one with: nyx secret update {entry_id} --totp-secret <BASE32>"
            )
            raise typer.Exit(1)

        def _show_code() -> None:
            secret = record.totp_secret
            assert secret is not None  # guaranteed by the guard above
            totp_obj = pyotp.TOTP(secret)
            code = totp_obj.now()
            remaining = 30 - (int(time.time()) % 30)
            filled = int((remaining / 30) * 20)
            bar = f"[#C89A30]{'█' * filled}[/#C89A30][#444441]{'░' * (20 - filled)}[/#444441]"
            ui.print_line(
                f"  [bold #00FF41]{code[:3]} {code[3:]}[/bold #00FF41]"
                f"  {bar}  [#888780]{remaining}s[/#888780]"
            )
            if copy:
                try:
                    import pyperclip
                    pyperclip.copy(code)
                    from nyxora.cli.ui import clipboard_countdown
                    clipboard_countdown(30)
                except Exception:
                    pass

        ui.print_line(
            f"  [bold #888780]TOTP for[/bold #888780] "
            f"[bold #00FFFF]{record.title}[/bold #00FFFF]"
        )
        _show_code()

        if watch:
            import time as _time
            ui.print_line("  [#888780]Watching… press Ctrl+C to exit[/#888780]")
            try:
                while True:
                    _time.sleep(1)
                    remaining = 30 - (int(_time.time()) % 30)
                    if remaining == 30:   # new period
                        _show_code()
            except KeyboardInterrupt:
                pass
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
        record = _resolve_entry(store, entry_id)  # pragma: no cover
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
