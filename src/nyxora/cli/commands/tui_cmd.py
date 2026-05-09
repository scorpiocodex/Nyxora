"""TUI launcher command."""
from __future__ import annotations

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import load_session, open_vault
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory

app = typer.Typer(
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
    invoke_without_command=True,
)
_engine = CryptoEngine()


@app.callback(invoke_without_command=True)
def tui(ctx: typer.Context) -> None:
    """Launch the NYXORA Obsidian Tactical interactive vault browser.

    Requires an unlocked vault session.
    Run 'nyx vault unlock' first.
    """
    if ctx.invoked_subcommand is not None:
        return

    # Check Textual is available
    try:
        import textual  # noqa: F401
    except ImportError:
        ui.error_panel(
            "Textual is not installed.\n"
            "Install it with: pip install 'nyxora[tui]'\n"
            "Or: pip install textual>=0.47.0"
        )
        raise typer.Exit(1)

    # Load session
    session_data = load_session()
    if session_data is None:
        ui.error_panel(
            "Vault is locked.\n"
            "Run 'nyx vault unlock' first, then 'nyx tui'."
        )
        raise typer.Exit(2)

    session_id, vault_path, root_key = session_data

    # Open vault and load all entries
    from nyxora.core.vault_store import VaultStore

    store = VaultStore(_engine)
    entries = []
    try:
        store.open(vault_path, root_key)
        entries = store.list_entries()
        store.close()
    except Exception as e:
        ui.error_panel(f"Failed to open vault: {e}")
        wipe_memory(root_key)
        raise typer.Exit(1)
    finally:
        wipe_memory(root_key)

    if not entries:
        ui.info_panel(
            "Your vault is empty.\n"
            "Add entries with 'nyx secret add' first.",
            title="Nothing to Display"
        )
        raise typer.Exit(0)

    # Launch the TUI
    from nyxora.tui.app import NyxoraApp

    app_instance = NyxoraApp(
        entries=entries,
        vault_path=str(vault_path),
        session_id=session_id,
    )
    app_instance.run()
