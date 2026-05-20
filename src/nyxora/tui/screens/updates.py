"""
Nyxora TUI v3.0.0 — UpdatesScreen.

Section 5: check for updates and install.
No rollback in TUI — users who need rollback use the CLI.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static

from nyxora import __version__


class UpdatesScreen(Static):
    """
    Update management screen — Section 5.

    Shows current version vs latest, and provides:
      - Check for updates  (c key or button)
      - Install update     (i key or button — only shown when available)
    """

    BINDINGS = [
        Binding("c", "check",   "Check",   show=True),
        Binding("i", "install", "Install", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._latest_version: str | None = None
        self._update_available: bool     = False

    def compose(self) -> ComposeResult:
        yield Static(" ◆  UPDATES", classes="screen-title")

        # Version compare boxes
        with Horizontal(id="version-compare"):
            with Vertical(classes="version-box"):
                yield Static("  INSTALLED", classes="version-lbl")
                yield Static(
                    f"  v{__version__}",
                    id="ver-current",
                    classes="version-num",
                )
            with Vertical(classes="version-box"):
                yield Static("  LATEST", classes="version-lbl")
                yield Static(
                    "  —",
                    id="ver-latest",
                    classes="version-num",
                )

        with Horizontal():
            yield Button("  CHECK FOR UPDATES", id="btn-check",
                         classes="primary")
            yield Button("  INSTALL",           id="btn-install",
                         classes="success")

        yield Static("", id="update-result")
        yield Static(
            "\n  [dim]Channel: stable · "
            "Updates are downloaded from PyPI and GitHub Releases.[/dim]\n"
            "  [dim]For rollback use: nyx update rollback[/dim]\n",
            id="update-footer",
        )

    def on_mount(self) -> None:
        # Hide install button until an update is confirmed available
        try:
            self.query_one("#btn-install", Button).styles.display = "none"
        except Exception:
            pass

    def on_show(self) -> None:
        # Refresh installed version label (may have changed)
        try:
            self.query_one("#ver-current", Static).update(
                f"  v{__version__}"
            )
        except Exception:
            pass

    # ── Events ───────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-check":
            self.action_check()
        elif event.button.id == "btn-install":
            self.action_install()

    # ── Actions ──────────────────────────────────────────────────

    def action_check(self) -> None:
        result = self.query_one("#update-result", Static)
        result.update("  Checking for updates…")
        try:
            from nyxora.core.update_engine import UpdateEngine
            engine = UpdateEngine()
            info   = engine.check_for_updates()

            latest = info.get("latest_version", "?")
            self._latest_version = latest

            try:
                self.query_one("#ver-latest", Static).update(f"  v{latest}")
            except Exception:
                pass

            if info.get("update_available", False):
                self._update_available = True
                result.update(
                    f"\n  [bold #C89A30]Update available: v{latest}[/bold #C89A30]\n\n"
                    f"  Press [bold]i[/bold] or click INSTALL to upgrade.\n"
                    f"  [dim]Nyxora will be reinstalled from PyPI.[/dim]\n"
                    f"  [dim]⚠  The TUI will close during installation.[/dim]\n"
                )
                try:
                    btn = self.query_one("#btn-install", Button)
                    btn.styles.display = "block"
                except Exception:
                    pass
            else:
                self._update_available = False
                result.update(
                    f"\n  [bold green]✓[/bold green]  "
                    f"Nyxora v{__version__} is up to date.\n"
                )
                try:
                    self.query_one("#btn-install", Button).styles.display = "none"
                except Exception:
                    pass

        except Exception as exc:
            result.update(f"\n  [red]Check failed: {exc}[/red]\n")

    def action_install(self) -> None:
        if not self._update_available or not self._latest_version:
            self.app.notify(
                "Run Check first to confirm an update is available.",
                timeout=3,
            )
            return

        result = self.query_one("#update-result", Static)
        result.update(
            f"  Installing v{self._latest_version}…\n"
            "  [dim]This may take a minute. The app will close.[/dim]"
        )
        try:
            from nyxora.core.update_engine import UpdateEngine
            engine = UpdateEngine()
            engine.install_update(self._latest_version)
            self.app.notify(
                f"Update to v{self._latest_version} complete. "
                "Restart Nyxora to use the new version.",
                title="◆ Updated",
                timeout=8,
            )
            # Exit TUI so the new version can be used
            self.app.exit()

        except Exception as exc:
            result.update(f"\n  [red]Install failed: {exc}[/red]\n")
