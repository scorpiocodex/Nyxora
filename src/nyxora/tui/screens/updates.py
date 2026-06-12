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
from nyxora.tui._markup import escape
from nyxora.tui.screens._shared_bg import (
    NyxBottomBar,
    NyxCornerInfo,
    NyxTopBar,
)


class UpdatesScreen(Static):
    """Update management screen — Section 5."""

    BINDINGS = [
        Binding("c", "check",   "Check",   show=True),
        Binding("i", "install", "Install", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._latest_version: str | None = None
        self._update_available: bool     = False
        self._release: dict | None       = None

    def compose(self) -> ComposeResult:
        yield NyxTopBar([
            (f"v{__version__}", True),
            ("STABLE CHANNEL", False),
            ("SECTION 5", False),
            ("PYPI + GITHUB", False),
        ])
        with Horizontal(classes="nyx-corners-top"):
            yield NyxCornerInfo("CHANNEL", ["STABLE", "PYPI", "GITHUB RELEASES"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("INSTALLED", [f"v{__version__}", "NEXUS"])
        yield Static(" ◆  UPDATES", classes="screen-title")
        with Horizontal(id="version-compare"):
            with Vertical(classes="version-box"):
                yield Static(
                    "[#1E2D3D]  INSTALLED[/#1E2D3D]",
                    classes="version-lbl",
                )
                yield Static(
                    f"[#C89A30]  v{__version__}[/#C89A30]",
                    id="ver-current",
                    classes="version-num",
                )
            with Vertical(classes="version-box"):
                yield Static(
                    "[#1E2D3D]  LATEST[/#1E2D3D]",
                    classes="version-lbl",
                )
                yield Static(
                    "[#1E2D3D]  —[/#1E2D3D]",
                    id="ver-latest",
                    classes="version-num",
                )
        with Horizontal():
            yield Button("  CHECK FOR UPDATES", id="btn-check",
                         classes="primary")
            yield Button("  INSTALL", id="btn-install", classes="success")
        yield Static("", id="update-result")
        yield Static(
            "\n  [dim]Channel: stable · "
            "Installed from PyPI via pip.[/dim]\n"
            "  [dim]For rollback: nyx update rollback[/dim]\n",
            id="update-footer",
        )
        with Horizontal(classes="nyx-corners-bot"):
            yield NyxCornerInfo("UPDATE", ["WHEEL + SHA256", "PIP INSTALL"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("ROLLBACK", ["nyx update rollback", "PREV VERSION KEPT"])
        yield NyxBottomBar()

    def on_mount(self) -> None:
        try:
            self.query_one("#btn-install", Button).styles.display = "none"
            self.query_one("#ver-current", Static).update(
                f"[#C89A30]  v{__version__}[/#C89A30]"
            )
        except Exception:
            pass

    def on_show(self) -> None:
        try:
            self.query_one("#ver-current", Static).update(
                f"[#C89A30]  v{__version__}[/#C89A30]"
            )
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-check":
            self.action_check()
        elif event.button.id == "btn-install":
            self.action_install()

    def action_check(self) -> None:
        result = self.query_one("#update-result", Static)
        result.update("  Checking for updates…")
        try:
            from nyxora.core.update_engine import fetch_latest_release, is_newer

            release = fetch_latest_release(channel="stable")
            if release is None:
                result.update(
                    "\n  [red]Could not reach GitHub. "
                    "Check your internet connection.[/red]\n"
                )
                return

            self._release = release
            tag = release.get("tag_name", "?").lstrip("v")
            self._latest_version = tag

            try:
                self.query_one("#ver-latest", Static).update(
                    f"[#C89A30]  v{escape(tag)}[/#C89A30]"
                )
            except Exception:
                pass

            if is_newer(release):
                self._update_available = True
                result.update(
                    f"\n  [bold #C89A30]Update available: "
                    f"v{escape(tag)}[/bold #C89A30]\n\n"
                    f"  Press [bold]i[/bold] or click INSTALL to upgrade.\n"
                    f"  [dim]Nyxora will be upgraded via pip.[/dim]\n"
                    f"  [dim]⚠  The TUI will close during installation.[/dim]\n"
                )
                try:
                    self.query_one("#btn-install", Button).styles.display = "block"
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
            result.update(f"\n  [red]Check failed: {escape(str(exc))}[/red]\n")

    def action_install(self) -> None:
        if not self._update_available or not self._latest_version:
            self.app.notify(
                "Run Check first to confirm an update is available.",
                timeout=3,
            )
            return

        result = self.query_one("#update-result", Static)
        result.update(
            f"  Installing v{escape(self._latest_version)}…\n"
            "  [dim]This may take a minute. The app will close.[/dim]"
        )
        try:
            import tempfile
            from pathlib import Path

            from nyxora.core.update_engine import (
                download_asset,
                get_checksums_asset,
                get_wheel_asset,
                install_wheel,
                save_rollback_version,
                verify_checksum,
            )

            release      = self._release
            wheel_asset  = get_wheel_asset(release)
            if not wheel_asset:
                result.update("\n  [red]No wheel asset found in release.[/red]\n")
                return

            save_rollback_version(__version__)

            with tempfile.TemporaryDirectory() as tmp:
                wheel_path = Path(tmp) / wheel_asset["name"]
                download_asset(
                    wheel_asset["browser_download_url"],
                    wheel_path,
                )

                # Optional checksum verification
                chk_asset = get_checksums_asset(release)
                if chk_asset:
                    import requests
                    chk_resp = requests.get(
                        chk_asset["browser_download_url"],
                        timeout=10,
                    )
                    if chk_resp.status_code == 200:
                        if not verify_checksum(wheel_path, chk_resp.text):
                            result.update(
                                "\n  [red]Checksum mismatch — "
                                "aborting install.[/red]\n"
                            )
                            return

                success, msg = install_wheel(wheel_path)

            if success:
                self.app.notify(
                    f"Updated to v{escape(self._latest_version)}. "
                    "Restart Nyxora to use the new version.",
                    title="◆ Updated",
                    timeout=8,
                )
                self.app.exit()
            else:
                result.update(
                    f"\n  [red]Install failed:\n{escape(msg[:200])}[/red]\n"
                )

        except Exception as exc:
            result.update(f"\n  [red]Install failed: {escape(str(exc))}[/red]\n")
