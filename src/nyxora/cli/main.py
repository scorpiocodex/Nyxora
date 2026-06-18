"""NYXORA CLI entry point.

Registers all command groups and wraps the app in a global exception handler
that converts NyxoraError subclasses into styled error panels — no raw
Python tracebacks ever reach the terminal.
"""

from __future__ import annotations

import typer

from nyxora import __version__
from nyxora.cli import ui
from nyxora.cli.commands import (
    backup,
    generate,
    locker,
    recovery,
    scripting,
    secret,
    security,
    tui_cmd,
    update,
    vault,
)
from nyxora.utils.exceptions import NyxoraError

app = typer.Typer(
    name="nyx",
    help="""
[bold #00FFFF]███╗   ██╗██╗   ██╗██╗  ██╗ ██████╗ ██████╗  █████╗[/]
[bold #00FFFF]████╗  ██║╚██╗ ██╔╝╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗[/]
[bold #00FF41]██╔██╗ ██║ ╚████╔╝  ╚███╔╝ ██║   ██║██████╔╝███████║[/]
[bold #00FF41]██║╚██╗██║  ╚██╔╝   ██╔██╗ ██║   ██║██╔══██╗██╔══██║[/]
[bold #8B00FF]██║ ╚████║   ██║   ██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║[/]
[bold #8B00FF]╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝[/]

[bold #00FFFF]NYXORA[/] — Next-Generation Password Intelligence Vault.

[#00FF41]Offline[/] • [#8B00FF]Zero-Knowledge[/] • [#00FFFF]Terminal-Native[/] • [#FFB000]Quantum-Resilient[/]
""",
    epilog="Execute [bold #00FFFF]nyx <command> --help[/] for encrypted module instructions.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode="rich",
    add_completion=True,
)

# ── Register command groups ────────────────────────────────────────────────────

app.add_typer(vault.app, name="vault", help="[bold]Vault lifecycle[/]: unlock, lock, health-check.", rich_help_panel="🔑 Core Operations")
app.add_typer(secret.app, name="secret", help="[bold]Manage vault entries[/]: add, list, get, update, delete.", rich_help_panel="🔒 Secrets Management")
app.add_typer(generate.app, name="generate", help="[bold]Generate credentials[/]: passwords, passphrases, API keys, SSH keys.", rich_help_panel="⚡ Generators & Tools")
app.add_typer(security.app, name="security", help="[bold]Audit and forensics[/]: breach scan, logs, integrity.", rich_help_panel="🛡️ Security & Intelligence")
app.add_typer(backup.app, name="backup", help="[bold]Manage backups[/]: restore, export, verify.", rich_help_panel="💾 Data Portability")
app.add_typer(recovery.app, name="recovery", help="[bold]Emergency recovery[/]: TOTP setup, capsules, secret splitting.", rich_help_panel="🚑 Emergency Access")
app.add_typer(locker.app, name="locker", help="[bold]File encryption[/]: encrypt/decrypt arbitrary files.", rich_help_panel="📁 File Locker")
app.add_typer(
    update.app,
    name="update",
    help="[bold]Manage updates[/]: check, install, rollback.",
    rich_help_panel="🔄 Updates"
)
app.add_typer(
    scripting.app,
    name="script",
    help="[bold]Scripting tools[/]: pipe, run, fzf integration.",
    rich_help_panel="⚙️  Scripting & Integration"
)
app.add_typer(
    tui_cmd.app,
    name="tui",
    help="[bold]Interactive vault browser[/] — Obsidian Tactical TUI.",
    rich_help_panel="🖥️  Interactive"
)


# ── Version callback ──────────────────────────────────────────────────────────

def version_callback(value: bool) -> None:
    if value:
        from nyxora.cli import ui
        ui.print_line(
            f"\n  [bold #C89A30]◆[/bold #C89A30] "
            f"[bold #E8D5A8]NYXORA[/bold #E8D5A8]  "
            f"[#344252]Tactical Secrets Vault[/#344252]\n"
            f"  [#2E3C4A]Version   [/#2E3C4A][bold #C89A30]v{__version__}[/bold #C89A30]\n"
            f"  [#2E3C4A]License   [/#2E3C4A][#344252]MIT[/#344252]\n"
            f"  [#2E3C4A]Author    [/#2E3C4A][#344252]ScorpioCodeX[/#344252]\n"
            f"  [#2E3C4A]Cipher    [/#2E3C4A][#344252]Argon2id · XChaCha20-Poly1305[/#344252]\n"
        )
        raise typer.Exit()


@app.callback()
def main_callback(
    version: bool = typer.Option(
        None, "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Output results as JSON (for scripting).",
        is_eager=False,
    ),
) -> None:
    """NYXORA — Terminal-native password intelligence vault."""
    if json_output:
        from nyxora.cli.ui import set_json_mode
        set_json_mode(True)


# ── Global exception handler ───────────────────────────────────────────────────

def cli_main() -> None:
    """Entry point with global exception handling.

    NyxoraError subclasses → styled error_panel + appropriate exit code.
    All other exceptions → generic error message (NYX_DEBUG=1 for full trace).
    """
    import os
    import sys

    # Legacy Windows consoles default to cp1252, which cannot encode the Rich
    # banner's box-drawing glyphs (the `nyx --help` art) and raises
    # UnicodeEncodeError. Degrade gracefully to UTF-8 with replacement so
    # output never crashes on incapable consoles; unchanged on capable ones.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    try:
        app()
    except SystemExit:
        raise
    except NyxoraError as exc:
        ui.error_panel(exc.user_message)
        sys.exit(exc.exit_code)
    except Exception:
        if os.environ.get("NYX_DEBUG", "").lower() in ("1", "true", "yes"):
            import traceback
            ui.error_panel(traceback.format_exc(), title="Debug Traceback")
        else:
            ui.error_panel(  # pragma: no cover
                "An unexpected error occurred. Set NYX_DEBUG=1 for full details.",
                title="Unexpected Error",
            )
        sys.exit(1)

if __name__ == "__main__":
    cli_main()  # pragma: no cover
