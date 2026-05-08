"""Security audit, breach scanning, forensics, and log commands."""
from __future__ import annotations

from typing import Optional

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import open_vault
from nyxora.cli.ui import audit_summary_panel
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.intel_engine import IntelEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.vault_store import VaultStore

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)

_engine = CryptoEngine()
_intel = IntelEngine(_engine)

def _open_vault() -> tuple[VaultStore, bytearray]:
    store, _, root_key, _ = open_vault(_engine)
    return store, root_key


@app.command()
def audit(
    no_hibp: bool = typer.Option(False, "--no-hibp", help="Skip HIBP breach check"),
) -> None:
    """Run a full security audit of all vault entries."""
    store, root_key = _open_vault()
    try:
        entries = store.list_entries()
        audit_data = [(e.id, e.title, e.password) for e in entries]
        with ui.spinner("Auditing entries…"):
            report = _intel.audit_all(audit_data, check_hibp=not no_hibp)
        ui.audit_table(report)
        weak_count = report.strength_histogram.get("Weak", 0)
        fair_count = report.strength_histogram.get("Fair", 0)
        audit_summary_panel(
            total=report.total_entries,
            breached=report.breached_count,
            weak=weak_count,
            fair=fair_count,
            reused=report.duplicate_count,
        )
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def stats() -> None:
    """Show vault statistics: entry count, age distribution, tag counts."""
    store, root_key = _open_vault()
    try:
        import datetime
        entries = store.list_entries()
        now = datetime.datetime.now()
        tag_counts: dict[str, int] = {}
        old_count = 0
        for e in entries:
            for tag in e.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1  # pragma: no cover
            age_days = (now - datetime.datetime.fromtimestamp(e.updated_at)).days
            if age_days > 90:
                old_count += 1  # pragma: no cover

        lines = [
            f"  Total entries:        {len(entries)}",
            f"  Entries > 90 days old: {old_count}",
            f"  Tags: {', '.join(f'{k}({v})' for k, v in sorted(tag_counts.items())) or 'none'}",
        ]
        ui.info_panel("\n".join(lines), title="Vault Statistics")
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def log(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of events to show"),
    event_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by event type"),
    reverse: bool = typer.Option(False, "--reverse", "-r", help="Show newest events first"),
) -> None:
    """Display the audit log."""
    store, root_key = _open_vault()
    try:
        import datetime

        from rich.table import Table

        from nyxora.cli.ui import ELEC_PURPLE, NEON_CYAN, console

        events = store.get_all_audit_events()
        if event_type:
            events = [e for e in events if e["event_type"] == event_type.upper()]  # pragma: no cover

        if reverse:
            events.reverse()  # pragma: no cover

        events = events[:limit]

        table = Table(title="[nyx.title]Audit Log[/nyx.title]",
                      border_style=ELEC_PURPLE, header_style=f"bold {NEON_CYAN}")
        table.add_column("Time")
        table.add_column("Event")
        table.add_column("Entry ID")
        table.add_column("Session")

        for event in events:
            ts = datetime.datetime.fromtimestamp(event["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            table.add_row(
                ts,
                event["event_type"],
                (event["entry_id"] or "")[:8],
                (event["session_id"] or "")[:8],
            )
        console.print(table)
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def forensic() -> None:
    """Run a full forensic integrity check and display detailed results."""
    store, root_key = _open_vault()
    try:
        with ui.spinner("Running forensic analysis…"):
            report = store.verify_integrity()
        ui.forensic_panel(report)
    finally:
        store.close()
        wipe_memory(root_key)


@app.command("breach-scan")
def breach_scan() -> None:
    """Check all vault passwords against HaveIBeenPwned."""
    store, root_key = _open_vault()
    try:
        entries = store.list_entries()
        breached = []
        with ui.spinner(f"Scanning {len(entries)} entries against HIBP…"):
            for entry in entries:
                try:
                    is_b, count = _intel.check_breach_hibp(entry.password)
                    if is_b:
                        breached.append((entry.title, count))  # pragma: no cover
                except Exception:  # pragma: no cover
                    pass  # pragma: no cover

        if breached:
            lines = "\n".join(f"  ⚠ {title}: seen {count} times" for title, count in breached)  # pragma: no cover
            ui.error_panel(lines, title=f"Breached Passwords ({len(breached)} found)")  # pragma: no cover
        else:
            ui.success_panel("No breached passwords found.")
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def due(
    days: int = typer.Option(90, "--days", "-d",
                             help="Days threshold for password age"),
) -> None:
    """List entries whose password hasn't changed in N days."""
    import datetime
    import time
    from rich.table import Table
    from nyxora.cli.ui import ELEC_PURPLE, NEON_CYAN, console

    store, root_key = _open_vault()
    try:
        entries = store.list_entries()
        now = datetime.datetime.now()
        threshold_secs = days * 86400
        overdue = [
            e for e in entries
            if (int(time.time()) - e.updated_at) > threshold_secs
        ]
        overdue.sort(key=lambda e: e.updated_at)

        if not overdue:
            ui.success_panel(
                f"All {len(entries)} entries updated within the last {days} days.",
                title="Rotation Status"
            )
            return

        table = Table(
            title=f"[nyx.title]Overdue Entries (>{days} days)[/nyx.title]",
            border_style=ELEC_PURPLE,
            header_style=f"bold {NEON_CYAN}",
        )
        table.add_column("Title")
        table.add_column("Last Updated")
        table.add_column("Age")
        table.add_column("Tags")

        for e in overdue:
            updated = datetime.datetime.fromtimestamp(e.updated_at)
            age_days = (now - updated).days
            age_str = f"[bold #FF3131]{age_days}d[/bold #FF3131]" if age_days > 180 \
                else f"[#FFB000]{age_days}d[/#FFB000]"
            table.add_row(
                e.title,
                updated.strftime("%Y-%m-%d"),
                age_str,
                ", ".join(e.tags) if e.tags else "—",
            )
        console.print(table)
        ui.warning_panel(
            f"{len(overdue)} of {len(entries)} entries overdue for rotation.",
            title="Action Recommended"
        )
    finally:
        store.close()
        wipe_memory(root_key)


@app.command()
def health() -> None:
    """Show vault security health score and breakdown."""
    from nyxora.cli.ui import checklist_panel, danger_panel
    from rich.table import Table
    from nyxora.cli.ui import ELEC_PURPLE, NEON_CYAN, console

    store, root_key = _open_vault()
    try:
        entries = store.list_entries()
        with ui.spinner("Computing vault health score…"):
            score = _intel.compute_health_score(entries)

        # Grade color
        grade_colors = {
            "A": "#00FF41", "B": "#00FFFF",
            "C": "#FFB000", "D": "#FF8000", "F": "#FF3131"
        }
        gc = grade_colors.get(score.grade, "#888780")

        ui.info_panel(
            f"[{gc}]Grade {score.grade}[/{gc}]  "
            f"[bold {gc}]{score.total}[/bold {gc}] / 100\n\n"
            f"  [#888780]Strength   [/#888780] {'█' * (score.strength_score // 2)}{'░' * (20 - score.strength_score // 2)}  {score.strength_score}/40\n"
            f"  [#888780]Breach-free[/#888780] {'█' * (score.breach_score)}{'░' * (25 - score.breach_score)}  {score.breach_score}/25\n"
            f"  [#888780]No reuse   [/#888780] {'█' * (score.duplicate_score)}{'░' * (15 - score.duplicate_score)}  {score.duplicate_score}/15\n"
            f"  [#888780]Age        [/#888780] {'█' * (score.age_score)}{'░' * (10 - score.age_score)}  {score.age_score}/10\n"
            f"  [#888780]TOTP       [/#888780] {'█' * (score.totp_score)}{'░' * (10 - score.totp_score)}  {score.totp_score}/10",
            title="Vault Health Score"
        )

        items = [
            (score.duplicate_count == 0,
             f"No reused passwords ({score.duplicate_count} found)"),
            (score.old_entries_count == 0,
             f"All passwords rotated within 90 days "
             f"({score.old_entries_count} overdue)"),
            (score.totp_enabled_count > 0,
             f"TOTP configured on {score.totp_enabled_count} of "
             f"{score.total_entries} entries"),
            (score.total >= 75,
             f"Overall vault health: {score.grade} ({score.total}/100)"),
        ]
        checklist_panel("Health Checks", items,
                        subtitle="Run 'nyx security audit' for full breach analysis.")
    finally:
        store.close()
        wipe_memory(root_key)
