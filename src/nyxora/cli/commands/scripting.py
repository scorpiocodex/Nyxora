"""Scripting integration: pipe, run, fzf — vault credentials into subprocesses."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import open_vault
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory

app = typer.Typer(
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)
_engine = CryptoEngine()


def _resolve_entry(store, entry_id: str):  # pragma: no cover
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


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def pipe(
    ctx: typer.Context,
    entry_id: str = typer.Argument(..., help="Entry ID or title prefix"),
    field: str = typer.Option(
        "password", "--field", "-f",
        help="Field to pipe: password, username, url, or a custom field key"
    ),
) -> None:
    """Pipe a vault field into a command's stdin.

    Usage:  nyx pipe <entry-id> -- <command> [args...]
    Example: nyx pipe db-prod -- psql -U postgres
    """
    cmd_args = ctx.args
    if not cmd_args:
        ui.error_panel(
            "No command specified.\n"
            "Usage: nyx pipe <entry-id> -- <command> [args...]"
        )
        raise typer.Exit(1)

    store, _, root_key, _ = open_vault(_engine)
    secret = None
    try:
        record = _resolve_entry(store, entry_id)
        if field == "password":
            secret = record.password
        elif field == "username":
            secret = record.username or ""
        elif field == "url":
            secret = record.url or ""
        else:
            secret = record.custom.get(field, "")
            if not secret:
                ui.error_panel(f"Custom field '{field}' not found on this entry.")
                raise typer.Exit(1)
    finally:
        store.close()
        wipe_memory(root_key)

    # Run command with field value piped to stdin
    # stdout/stderr pass through directly to the terminal
    try:
        proc = subprocess.Popen(
            cmd_args,
            stdin=subprocess.PIPE,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
        proc.communicate(input=(secret + "\n").encode("utf-8"))
        sys.exit(proc.returncode)
    except FileNotFoundError:
        ui.error_panel(f"Command not found: {cmd_args[0]}")
        raise typer.Exit(1)
    except Exception as e:
        ui.error_panel(f"Failed to run command: {e}")
        raise typer.Exit(1)
    finally:
        # Wipe secret from memory
        if secret:
            secret = "\x00" * len(secret)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def run(
    ctx: typer.Context,
    entry_id: str = typer.Argument(..., help="Entry ID or title prefix"),
    prefix: str = typer.Option(
        "NYX", "--prefix", "-p",
        help="Env var prefix (default: NYX → NYX_PASSWORD, NYX_USERNAME…)"
    ),
    no_custom: bool = typer.Option(
        False, "--no-custom",
        help="Skip injecting custom fields as env vars"
    ),
) -> None:
    """Run a command with vault credentials injected as environment variables.

    Usage:  nyx run <entry-id> -- <command> [args...]
    Example: nyx run aws-prod -- aws s3 ls

    Injects:  {PREFIX}_PASSWORD, {PREFIX}_USERNAME, {PREFIX}_URL
    Custom fields: {PREFIX}_{KEY} for each custom field key.
    """
    cmd_args = ctx.args
    if not cmd_args:
        ui.error_panel(
            "No command specified.\n"
            "Usage: nyx run <entry-id> -- <command> [args...]"
        )
        raise typer.Exit(1)

    store, _, root_key, _ = open_vault(_engine)
    env_extras: dict[str, str] = {}
    try:
        record = _resolve_entry(store, entry_id)
        pfx = prefix.upper().rstrip("_")
        env_extras[f"{pfx}_PASSWORD"] = record.password
        if record.username:
            env_extras[f"{pfx}_USERNAME"] = record.username
        if record.url:
            env_extras[f"{pfx}_URL"] = record.url
        if not no_custom and record.custom:
            for k, v in record.custom.items():
                env_extras[f"{pfx}_{k.upper()}"] = str(v)
    finally:
        store.close()
        wipe_memory(root_key)

    env = os.environ.copy()
    env.update(env_extras)

    try:
        result = subprocess.run(cmd_args, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        ui.error_panel(f"Command not found: {cmd_args[0]}")
        raise typer.Exit(1)
    except Exception as e:
        ui.error_panel(f"Failed to run command: {e}")
        raise typer.Exit(1)
    finally:
        for k in env_extras:
            env_extras[k] = "\x00" * len(env_extras[k])


@app.command()
def fzf(
    copy: bool = typer.Option(
        False, "--copy", "-c", help="Copy password to clipboard after selection"
    ),
    show: bool = typer.Option(
        False, "--show", "-s", help="Show full entry detail after selection"
    ),
    field: str = typer.Option(
        "password", "--field", "-f",
        help="Field to output: password, username, url, totp"
    ),
    json_out: bool = typer.Option(
        False, "--json", help="Print selected entry as JSON to stdout"
    ),
) -> None:
    """Open an fzf fuzzy-finder over vault entries.

    Requires fzf to be installed: https://github.com/junegunn/fzf
    """
    import pyotp

    # Check fzf is available
    fzf_check = subprocess.run(
        ["fzf", "--version"], capture_output=True, text=True
    )
    if fzf_check.returncode != 0:
        ui.error_panel(
            "fzf not found. Install it first:\n"
            "  Windows (winget): winget install fzf\n"
            "  Linux:            sudo apt install fzf\n"
            "  macOS:            brew install fzf"
        )
        raise typer.Exit(1)

    store, _, root_key, _ = open_vault(_engine)
    try:
        entries = store.list_entries()
        if not entries:
            ui.info_panel("No entries in vault.")
            raise typer.Exit(0)

        # Format: "TITLE\tUSERNAME\tID" — fzf shows columns 1+2, we use col 3
        lines = "\n".join(
            f"{e.title}\t{e.username or ''}\t{e.id}"
            for e in entries
        )

        result = subprocess.run(
            ["fzf",
             "--with-nth=1,2",
             "--delimiter=\t",
             "--prompt=vault > ",
             "--border",
             "--height=40%",
             "--ansi"],
            input=lines,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            # User cancelled
            raise typer.Exit(0)

        selected_line = result.stdout.strip()
        if not selected_line:
            raise typer.Exit(0)

        parts = selected_line.split("\t")
        if len(parts) < 3:
            raise typer.Exit(0)
        entry_id = parts[2]

        record = _resolve_entry(store, entry_id)

        if json_out:
            from nyxora.cli.ui import json_out as _json_out
            _json_out({
                "id": record.id, "title": record.title,
                "username": record.username, "password": record.password,
                "url": record.url, "tags": record.tags,
            })
            return

        if field == "password":
            output = record.password
        elif field == "username":
            output = record.username or ""
        elif field == "url":
            output = record.url or ""
        elif field == "totp":
            if not getattr(record, "totp_secret", None):
                ui.error_panel("This entry has no TOTP secret stored.")
                raise typer.Exit(1)
            output = pyotp.TOTP(record.totp_secret).now()
        else:
            output = record.custom.get(field, "")

        if copy:
            try:
                import pyperclip
                pyperclip.copy(output)
                from nyxora.cli.ui import clipboard_countdown
                ui.success_panel(
                    f"[bold]{record.title}[/bold] {field} copied to clipboard.",
                    title="Copied"
                )
                clipboard_countdown(30)
            except Exception:
                sys.stdout.write(output + "\n")
        elif show:
            ui.print_kv("Title", record.title)
            ui.print_kv("Username", record.username or "")
            ui.print_kv("Password", record.password)
            if record.url:
                ui.print_kv("URL", record.url)
        else:
            # Default: print to stdout (for scripting — no trailing newline strip)
            sys.stdout.write(output + "\n")
            sys.stdout.flush()

    finally:
        store.close()
        wipe_memory(root_key)
