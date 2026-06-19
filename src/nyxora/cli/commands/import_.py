"""Vault import: batch-add entries from CSV, JSON, Bitwarden, or 1Password."""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

import orjson
import typer

from nyxora.cli import ui
from nyxora.cli.helpers import open_vault
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)
_engine = CryptoEngine()

SUPPORTED_FORMATS = ["auto", "csv", "json", "bitwarden", "1password"]


@app.command("import")
def import_entries(
    file: Path = typer.Argument(..., help="File to import"),
    format: str = typer.Option(
        "auto", "--format", "-f",
        help="Format: auto, csv, json, bitwarden, 1password"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview import without writing to vault"
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Import entries from CSV, JSON, Bitwarden, or 1Password export."""
    if not file.exists():
        ui.error_panel(f"File not found: {file}")
        raise typer.Exit(1)

    fmt = format.lower()
    if fmt not in SUPPORTED_FORMATS:
        ui.error_panel(
            f"Unknown format '{format}'. "
            f"Supported: {', '.join(SUPPORTED_FORMATS)}"
        )
        raise typer.Exit(1)

    # Auto-detect format from file extension and content
    if fmt == "auto":
        fmt = _detect_format(file)

    try:
        entries = _parse_file(file, fmt)
    except Exception as e:
        ui.error_panel(f"Failed to parse {file.name}: {e}")
        raise typer.Exit(1)

    if not entries:
        ui.info_panel("No entries found in file.")
        raise typer.Exit(0)

    ui.info_panel(
        f"Found [bold]{len(entries)}[/bold] entries to import "
        f"from [bold]{file.name}[/bold] ({fmt} format).",
        title="Import Preview"
    )

    if dry_run:
        for entry in entries[:10]:
            ui.print_kv("  Title", entry.get("title", "(no title)"))
        if len(entries) > 10:
            ui.print_line(
                f"  [#888780]... and {len(entries) - 10} more[/#888780]"
            )
        raise typer.Exit(0)

    if not yes:
        import questionary
        ok = questionary.confirm(
            f"Import {len(entries)} entries into vault?"
        ).ask()
        if not ok:
            ui.info_panel("Import cancelled.")
            raise typer.Exit(0)

    store, _, root_key, _ = open_vault(_engine)
    imported = 0
    skipped = 0
    try:
        for entry in entries:
            try:
                store.add_entry(
                    title=entry.get("title") or "(imported)",
                    password=entry.get("password") or "",
                    username=entry.get("username"),
                    url=entry.get("url"),
                    notes=entry.get("notes"),
                    tags=entry.get("tags", []),
                )
                imported += 1
            except Exception:
                skipped += 1

        status = f"[#00FF41]✓ {imported} imported[/#00FF41]"
        if skipped:
            status += f"   [#FFB000]⚑ {skipped} skipped[/#FFB000]"
        ui.success_panel(status, title="Import Complete")

    finally:
        store.close()
        wipe_memory(root_key)


def _detect_format(file: Path) -> str:
    """Detect format from extension and first-byte content sniffing."""
    suffix = file.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in (".json", ".jsonl"):
        try:
            data = orjson.loads(file.read_bytes())
            if isinstance(data, dict):
                if "items" in data and "folders" in data:
                    return "bitwarden"
                if "accounts" in data or "vaults" in data:
                    return "1password"
            return "json"
        except Exception:
            return "json"
    return "csv"  # default fallback


def _parse_file(file: Path, fmt: str) -> list[dict[str, Any]]:
    """Parse a file into a list of entry dicts."""
    if fmt == "csv":
        return _parse_csv(file)
    if fmt == "json":
        return _parse_nyxora_json(file)
    if fmt == "bitwarden":
        return _parse_bitwarden(file)
    if fmt == "1password":
        return _parse_1password(file)
    return []


def _parse_csv(file: Path) -> list[dict[str, Any]]:
    """Parse a CSV with columns: title, username, password, url, notes."""
    text = file.read_text(encoding="utf-8-sig")  # handle BOM
    reader = csv.DictReader(io.StringIO(text))
    entries = []
    for row in reader:
        # Normalize common column name variants
        entry = {
            "title":    row.get("title") or row.get("name") or row.get("Title") or "",
            "username": row.get("username") or row.get("login") or row.get("Username") or "",
            "password": row.get("password") or row.get("Password") or "",
            "url":      row.get("url") or row.get("URL") or row.get("website") or "",
            "notes":    row.get("notes") or row.get("Notes") or row.get("comment") or "",
        }
        if entry["title"] or entry["password"]:
            entries.append(entry)
    return entries


def _parse_nyxora_json(file: Path) -> list[dict[str, Any]]:
    """Parse Nyxora's own JSON export format."""
    data = orjson.loads(file.read_bytes())
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "entries" in data:
        entries: list[dict[str, Any]] = data["entries"]
        return entries
    return []


def _parse_bitwarden(file: Path) -> list[dict[str, Any]]:
    """Parse a Bitwarden JSON export."""
    data = orjson.loads(file.read_bytes())
    items = data.get("items", [])
    entries = []
    for item in items:
        if item.get("type") != 1:  # type 1 = login
            continue
        login = item.get("login") or {}
        entries.append({
            "title":    item.get("name", ""),
            "username": login.get("username", ""),
            "password": login.get("password", ""),
            "url":      (login.get("uris") or [{}])[0].get("uri", ""),
            "notes":    item.get("notes", ""),
            "tags":     [item["folderId"]] if item.get("folderId") else [],
        })
    return entries


def _parse_1password(file: Path) -> list[dict[str, Any]]:
    """Parse a 1Password CSV export."""
    # 1Password CSV: Title, Username, Password, URL, Notes, Type
    return _parse_csv(file)  # column names overlap enough
