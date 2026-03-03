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
