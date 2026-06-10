"""nyx tui — launch the interactive Nyxora TUI."""
from __future__ import annotations

import typer

app = typer.Typer(
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)


@app.callback(invoke_without_command=True)
def tui() -> None:
    """Interactive vault browser — Obsidian Tactical TUI."""
    try:
        from nyxora.tui.app import launch_tui
        launch_tui()
    except ImportError:
        from nyxora.cli import ui
        ui.error_panel(
            "Textual is not installed.\n"
            "Install with: pip install nyxora[tui]\n"
            "Or: pip install textual>=0.47.0",
            title="TUI Unavailable",
        )
        raise typer.Exit(1)
