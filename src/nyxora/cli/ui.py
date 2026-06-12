"""Rich-based terminal UI for NYXORA.

Neon cyber theme. All output goes through these functions — never print() directly.
Color palette: Neon Cyan, Electric Purple, Matrix Green, Warn Amber, Error Red.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.theme import Theme

# ── Color palette ──────────────────────────────────────────────────────────────

NEON_CYAN = "#00FFFF"
ELEC_PURPLE = "#8B00FF"
MATRIX_GREEN = "#00FF41"
WARN_AMBER = "#FFB000"
ERROR_RED = "#FF3131"
DIM_GRAY = "#666666"

NYX_THEME = Theme({
    "nyx.title":   f"bold {NEON_CYAN}",
    "nyx.success": f"bold {MATRIX_GREEN}",
    "nyx.error":   f"bold {ERROR_RED}",
    "nyx.warning": f"bold {WARN_AMBER}",
    "nyx.accent":  f"bold {ELEC_PURPLE}",
    "nyx.dim":     f"{DIM_GRAY}",
    "nyx.label":   f"bold {NEON_CYAN}",
})

console = Console(theme=NYX_THEME, highlight=False)

# ── JSON output mode ──────────────────────────────────────────────────
_json_mode: bool = False

def set_json_mode(enabled: bool) -> None:
    """Enable or disable JSON output mode globally."""
    global _json_mode
    _json_mode = enabled

def is_json_mode() -> bool:
    """Return True if JSON output mode is active."""
    return _json_mode

def json_out(data: Any) -> None:
    """Print data as compact JSON to stdout. Used when --json is active."""
    import json as _json
    import sys
    sys.stdout.write(_json.dumps(data, default=str, ensure_ascii=False) + "\n")
    sys.stdout.flush()

# ── ASCII Banner ───────────────────────────────────────────────────────────────

_BANNER = r"""
███╗   ██╗██╗   ██╗██╗  ██╗ ██████╗ ██████╗  █████╗
████╗  ██║╚██╗ ██╔╝╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
██╔██╗ ██║ ╚████╔╝  ╚███╔╝ ██║   ██║██████╔╝███████║
██║╚██╗██║  ╚██╔╝   ██╔██╗ ██║   ██║██╔══██╗██╔══██║
██║ ╚████║   ██║   ██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝
  Terminal-native · Offline · Zero-Knowledge · Quantum-Resilient
"""


def vault_header() -> None:
    """Render the NYXORA ASCII banner."""
    console.print(_BANNER, style="nyx.accent")


# ── Panel helpers ──────────────────────────────────────────────────────────────

def success_panel(message: str, title: str = "Success") -> None:
    """Display a green success panel."""
    console.print(
        Panel(f"[nyx.success]{message}[/nyx.success]", title=f"[nyx.success]{title}[/nyx.success]",
              border_style=MATRIX_GREEN)
    )


def error_panel(message: str, title: str = "Error") -> None:
    """Display a red error panel."""
    console.print(
        Panel(f"[nyx.error]{message}[/nyx.error]", title=f"[nyx.error]{title}[/nyx.error]",
              border_style=ERROR_RED)
    )


def warning_panel(message: str, title: str = "Warning") -> None:
    """Display an amber warning panel."""
    console.print(
        Panel(f"[nyx.warning]{message}[/nyx.warning]", title=f"[nyx.warning]{title}[/nyx.warning]",
              border_style=WARN_AMBER)
    )


def info_panel(message: str, title: str = "Info") -> None:
    """Display a cyan info panel."""
    console.print(
        Panel(f"[nyx.title]{message}[/nyx.title]", title=f"[nyx.title]{title}[/nyx.title]",
              border_style=NEON_CYAN)
    )


# ── Progress helpers ───────────────────────────────────────────────────────────

@contextmanager
def spinner(message: str) -> Generator[None, None, None]:
    """Display an electric purple dots spinner during an operation."""
    with Progress(
        SpinnerColumn(style=f"bold {ELEC_PURPLE}"),
        TextColumn(f"[bold {ELEC_PURPLE}]{{task.description}}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(message, total=None)
        yield


@contextmanager
def progress_bar(total: int, description: str) -> Generator[Progress, None, None]:
    """Display a neon progress bar. Yields the Progress object for manual advance()."""
    with Progress(  # pragma: no cover
        SpinnerColumn(style=f"bold {ELEC_PURPLE}"),  # pragma: no cover
        TextColumn(f"[bold {NEON_CYAN}]{{task.description}}"),  # pragma: no cover
        BarColumn(bar_width=40, style=ELEC_PURPLE, complete_style=MATRIX_GREEN),  # pragma: no cover
        MofNCompleteColumn(),  # pragma: no cover
        console=console,  # pragma: no cover
    ) as progress:  # pragma: no cover
        progress.add_task(description, total=total)  # pragma: no cover
        yield progress  # pragma: no cover


# ── Table rendering ────────────────────────────────────────────────────────────

def table_entries(entries: list[Any], show_passwords: bool = False) -> None:
    """Render a neon-bordered table of vault entries."""
    from nyxora.core.vault_store import EntryRecord

    table = Table(
        title="[nyx.title]Vault Entries[/nyx.title]",
        border_style=ELEC_PURPLE,
        header_style=f"bold {NEON_CYAN}",
        show_lines=True,
    )
    table.add_column("ID", style=DIM_GRAY, max_width=8)
    table.add_column("Title", style=f"bold {NEON_CYAN}")
    table.add_column("Username", style=NEON_CYAN)
    if show_passwords:
        table.add_column("Password", style=WARN_AMBER)
    table.add_column("URL", style=DIM_GRAY, max_width=30)
    table.add_column("Tags", style=ELEC_PURPLE)
    table.add_column("Updated", style=DIM_GRAY)

    import datetime
    for entry in entries:
        if not isinstance(entry, EntryRecord):
            continue  # pragma: no cover
        updated = datetime.datetime.fromtimestamp(entry.updated_at).strftime("%Y-%m-%d")
        tags_str = ", ".join(entry.tags) if entry.tags else ""
        row = [
            entry.id[:8],
            entry.title,
            entry.username or "",
        ]
        if show_passwords:
            row.append(entry.password)
        row += [
            entry.url or "",
            tags_str,
            updated,
        ]
        table.add_row(*row)

    console.print(table)


def forensic_panel(report: Any) -> None:
    """Render a detailed forensic report panel."""
    from nyxora.core.vault_store import ForensicReport
    if not isinstance(report, ForensicReport):
        return  # pragma: no cover

    status = "[nyx.success]PASSED[/nyx.success]" if report.passed else "[nyx.error]FAILED[/nyx.error]"
    lines = [f"Overall: {status}", ""]

    lines.append(f"  Schema fingerprint: {'OK' if report.schema_ok else 'FAILED'}")
    lines.append(f"  Vault HMAC:         {'OK' if report.vault_hmac_ok else 'FAILED'}")
    lines.append(f"  Entries checked:    {report.entries_checked}")
    lines.append(f"  Entries failed:     {len(report.entries_failed)}")
    lines.append(f"  Audit log:          {'OK' if report.audit_log_ok else 'FAILED'}")

    if report.entries_failed:
        lines.append("\n  Compromised entry IDs:")  # pragma: no cover
        for eid in report.entries_failed:  # pragma: no cover
            lines.append(f"    [nyx.error]✗ {eid}[/nyx.error]")  # pragma: no cover

    if report.details:
        lines.append("\n  Details:")
        for d in report.details:
            lines.append(f"    {d}")

    border = MATRIX_GREEN if report.passed else ERROR_RED
    console.print(
        Panel("\n".join(lines), title="[nyx.title]Forensic Report[/nyx.title]",
              border_style=border)
    )


def audit_table(report: Any) -> None:
    """Render a vault audit report with strength histogram and breach counts."""
    from nyxora.core.intel_engine import VaultAuditReport
    if not isinstance(report, VaultAuditReport):
        return  # pragma: no cover

    # Summary panel
    lines = [
        f"  Total entries:  {report.total_entries}",
        f"  Breached:       [nyx.error]{report.breached_count}[/nyx.error]",
        f"  Duplicates:     [nyx.warning]{report.duplicate_count}[/nyx.warning]",
        "",
        "  Strength Distribution:",
    ]
    for strength, count in report.strength_histogram.items():
        bar = "█" * count
        color = {
            "Weak": ERROR_RED, "Fair": WARN_AMBER,
            "Strong": NEON_CYAN, "Excellent": MATRIX_GREEN,
        }.get(strength, NEON_CYAN)
        lines.append(f"    {strength:10s} [{color}]{bar} {count}[/{color}]")

    console.print(Panel("\n".join(lines), title="[nyx.title]Vault Audit Summary[/nyx.title]",
                        border_style=NEON_CYAN))

    # Per-entry table
    table = Table(
        title="[nyx.title]Entry Audit Results[/nyx.title]",
        border_style=ELEC_PURPLE,
        header_style=f"bold {NEON_CYAN}",
        show_lines=True,
    )
    table.add_column("Title", style=f"bold {NEON_CYAN}")
    table.add_column("Strength")
    table.add_column("Entropy")
    table.add_column("Breached?")
    table.add_column("Duplicate?")
    table.add_column("Patterns")

    for entry in report.entries:
        strength_colors = {  # pragma: no cover
            "Weak": ERROR_RED, "Fair": WARN_AMBER,  # pragma: no cover
            "Strong": NEON_CYAN, "Excellent": MATRIX_GREEN,  # pragma: no cover
        }  # pragma: no cover
        sc = strength_colors.get(entry.strength, NEON_CYAN)  # pragma: no cover
        breached_str = f"[{ERROR_RED}]YES ({entry.breach_count})[/{ERROR_RED}]" if entry.is_breached else "No"  # pragma: no cover
        dup_str = f"[{WARN_AMBER}]YES[/{WARN_AMBER}]" if entry.is_duplicate else "No"  # pragma: no cover
        table.add_row(  # pragma: no cover
            entry.title,
            f"[{sc}]{entry.strength}[/{sc}]",
            f"{entry.entropy:.1f} bits",
            breached_str,
            dup_str,
            ", ".join(entry.patterns[:3]) or "none",
        )

    console.print(table)


def print_line(text: str = "") -> None:
    """Print a plain line through the themed console."""
    console.print(text)


def print_kv(key: str, value: str) -> None:
    """Print a key-value pair in neon style."""
    console.print(f"  [nyx.label]{key}:[/nyx.label] {value}")


# ── New display helpers ────────────────────────────────────────────────────────

def entropy_bar(score: float, width: int = 20) -> str:
    """Return a Rich markup block bar representing entropy level."""
    filled = int((min(score, 128) / 128) * width)
    if score < 30:
        color = "#FF3131"
    elif score < 50:
        color = "#FFB000"
    elif score < 70:
        color = "#00FFFF"
    else:
        color = "#00FF41"
    return f"[{color}]{'█' * filled}[/{color}][#444441]{'░' * (width - filled)}[/#444441]"


def strength_badge(strength: str) -> str:
    """Return a colored Rich markup label for a strength category."""
    mapping = {
        "Weak":      "[bold #FF3131]WEAK[/bold #FF3131]",
        "Fair":      "[bold #FFB000]FAIR[/bold #FFB000]",
        "Strong":    "[bold #00FFFF]STRONG[/bold #00FFFF]",
        "Excellent": "[bold #00FF41]EXCELLENT[/bold #00FF41]",
    }
    return mapping.get(strength, "[bold #888780]UNKNOWN[/bold #888780]")


def checklist_panel(title: str, items: list[tuple[bool, str]], subtitle: str = "") -> None:
    """Print a Rich panel containing a vertical checklist of (passed, label) items."""
    from rich.text import Text
    text = Text()
    for i, (passed, label) in enumerate(items):
        if i:
            text.append("\n")
        if passed:
            text.append("  ✓", style="bold #00FF41")
        else:
            text.append("  ✗", style="bold #FF3131")
        text.append(f" {label}")
    if subtitle:
        text.append(f"\n\n{subtitle}", style="dim")
    console.print(Panel(text, title=f"[nyx.title]{title}[/nyx.title]", border_style=ELEC_PURPLE))


def danger_panel(message: str, title: str = "⚠  DANGER") -> None:
    """Print a bold red danger warning panel."""
    console.print(Panel(
        f"[#FF3131]{message}[/#FF3131]",
        title=f"[bold #FF3131]{title}[/bold #FF3131]",
        border_style="#FF3131",
        title_align="left",
    ))


def session_dashboard(
    session_id: str,
    vault_path: str,
    entry_count: int,
    failed_attempts: int,
    inactivity_timeout: int,
) -> None:
    """Print a rich vault status panel as a borderless two-column table."""
    table = Table(box=None, padding=(0, 2, 0, 0), show_header=False)
    table.add_column("label", style="bold #888780", justify="right")
    table.add_column("value", justify="left")

    attempts_val = (
        "[#00FF41]0 failed[/#00FF41]"
        if failed_attempts == 0
        else f"[#FFB000]{failed_attempts} failed[/#FFB000]"
    )

    table.add_row("STATUS",   "[bold #00FF41]  UNLOCKED[/bold #00FF41]")
    table.add_row("PATH",     f"[{NEON_CYAN}]{vault_path}[/{NEON_CYAN}]")
    table.add_row("ENTRIES",  f"[{NEON_CYAN}]{entry_count}[/{NEON_CYAN}]")
    table.add_row("SESSION",  f"[#888780]{session_id[:8]}…[/#888780]")
    table.add_row("TIMEOUT",  f"[#888780]{inactivity_timeout // 60}m inactivity limit[/#888780]")
    table.add_row("ATTEMPTS", attempts_val)
    table.add_row("CIPHER",   "[#888780]Argon2id · XChaCha20-Poly1305[/#888780]")

    console.print(Panel(table, title="[nyx.title]Vault Status[/nyx.title]", border_style=ELEC_PURPLE))


def audit_summary_panel(total: int, breached: int, weak: int, fair: int, reused: int) -> None:
    """Print a one-line audit summary panel."""
    line = f"[#888780]{total} entries scanned[/#888780]   "
    line += (
        f"[bold #FF3131]✗ {breached} BREACHED[/bold #FF3131]   "
        if breached
        else "[#00FF41]✓ 0 BREACHED[/#00FF41]   "
    )
    line += (
        f"[#FF3131]{weak} WEAK[/#FF3131]   "
        if weak
        else "[#00FF41]0 WEAK[/#00FF41]   "
    )
    line += f"[#FFB000]{fair} FAIR[/#FFB000]   " if fair else ""
    line += (
        f"[#FFB000]⚑ {reused} REUSED[/#FFB000]"
        if reused
        else "[#00FF41]✓ 0 REUSED[/#00FF41]"
    )
    console.print(Panel(line, title="[nyx.title]Audit Summary[/nyx.title]", border_style=ELEC_PURPLE))


def clipboard_countdown(seconds: int = 30) -> None:
    """Launch a daemon thread that clears the clipboard after `seconds` seconds."""
    import threading
    import time

    import pyperclip

    def _clear() -> None:
        time.sleep(seconds)
        pyperclip.copy("")
        console.print(f"[#888780]  Clipboard cleared after {seconds}s.[/#888780]")

    threading.Thread(target=_clear, daemon=True).start()


def update_diff_panel(changed_fields: list[str]) -> None:
    """Print a panel listing updated fields, or an info panel if nothing changed."""
    if not changed_fields:
        info_panel("No fields were updated.")
        return
    content = "\n".join(f"  [#00FF41]✓[/#00FF41] {f}" for f in changed_fields)
    console.print(Panel(content, title="[nyx.title]Entry Updated[/nyx.title]", border_style=MATRIX_GREEN))


def recovery_status_panel(
    totp_configured: bool,
    capsule_files: list[str],
    share_files: list[str],
) -> None:
    """Print a checklist panel summarising configured recovery pathways."""
    capsule_label = (
        f"Recovery capsule ({len(capsule_files)} file(s) found)"
        if capsule_files
        else "Recovery capsule (none found)"
    )
    shares_label = (
        f"Shamir shares ({len(share_files)} file(s) found)"
        if share_files
        else "Shamir shares (none found)"
    )
    items: list[tuple[bool, str]] = [
        (totp_configured, "TOTP two-factor authentication"),
        (len(capsule_files) > 0, capsule_label),
        (len(share_files) > 0, shares_label),
    ]
    checklist_panel(
        "Recovery Status",
        items,
        subtitle="Run 'nyx recovery --help' to configure missing pathways.",
    )
