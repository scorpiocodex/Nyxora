"""Update management: check, install, rollback, channel."""
from __future__ import annotations

import typer

from nyxora.cli import ui
from nyxora.utils.config import Config

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)


def _get_channel() -> str:
    config = Config()
    config.load()
    return config.get("update.channel", "stable")


@app.command()
def check() -> None:
    """Check for available Nyxora updates."""
    from nyxora import __version__
    from nyxora.core.update_engine import fetch_latest_release, is_newer

    channel = _get_channel()
    ui.info_panel(
        f"Current version: [bold #00FFFF]v{__version__}[/bold #00FFFF]\n"
        f"Channel: [#888780]{channel}[/#888780]",
        title="Update Check"
    )

    with ui.spinner("Checking GitHub Releases…"):
        release = fetch_latest_release(channel)

    if release is None:
        ui.warning_panel(
            "Could not reach GitHub. Check your connection.\n"
            "Releases: https://github.com/scorpiocodex/Nyxora/releases",
            title="Network Unavailable"
        )
        raise typer.Exit(1)

    tag = release.get("tag_name", "")
    name = release.get("name", tag)
    body = release.get("body", "")

    if not is_newer(release):
        ui.success_panel(
            f"Nyxora [bold #00FFFF]v{__version__}[/bold #00FFFF] is the latest version.",
            title="Up to Date"
        )
        return

    # Summarise release notes — first 8 non-empty lines
    notes_lines = [l for l in body.splitlines() if l.strip()][:8]
    notes = "\n".join(f"  {l}" for l in notes_lines)
    if not notes:
        notes = "  See release notes on GitHub."

    ui.info_panel(
        f"[bold #00FF41]{tag}[/bold #00FF41] is available  (you have v{__version__})\n\n"
        f"[#888780]{name}[/#888780]\n\n"
        f"{notes}\n\n"
        f"Run [bold #00FFFF]nyx update install[/bold #00FFFF] to upgrade.",
        title="Update Available"
    )


@app.command()
def install(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Download and install the latest Nyxora release."""
    from nyxora import __version__
    from nyxora.core.update_engine import (
        download_asset,
        fetch_latest_release,
        get_checksums_asset,
        get_wheel_asset,
        install_wheel,
        is_newer,
        save_rollback_version,
        verify_checksum,
    )

    channel = _get_channel()

    with ui.spinner("Fetching release information…"):
        release = fetch_latest_release(channel)

    if release is None:
        ui.error_panel("Could not reach GitHub. Check your connection.")
        raise typer.Exit(1)

    if not is_newer(release):
        ui.success_panel(
            f"Already on the latest version: v{__version__}",
            title="Up to Date"
        )
        return

    tag = release.get("tag_name", "")
    wheel_asset = get_wheel_asset(release)

    if wheel_asset is None:
        ui.error_panel(
            f"No wheel (.whl) found in release {tag}.\n"
            f"Install manually: https://github.com/scorpiocodex/Nyxora/releases/tag/{tag}"
        )
        raise typer.Exit(1)

    if not yes:
        import questionary
        ok = questionary.confirm(
            f"Install Nyxora {tag}? (current: v{__version__})"
        ).ask()
        if not ok:
            ui.info_panel("Update cancelled.")
            raise typer.Exit(0)

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        wheel_path = tmp_path / wheel_asset["name"]

        with ui.spinner(f"Downloading {wheel_asset['name']}…"):
            try:
                download_asset(wheel_asset["browser_download_url"], wheel_path)
            except Exception as e:
                ui.error_panel(f"Download failed: {e}")
                raise typer.Exit(1)

        # Verify checksum if sha256sums.txt is available
        checksums_asset = get_checksums_asset(release)
        if checksums_asset:
            with ui.spinner("Verifying checksum…"):
                try:
                    checksums_path = tmp_path / checksums_asset["name"]
                    download_asset(
                        checksums_asset["browser_download_url"], checksums_path
                    )
                    checksums_text = checksums_path.read_text(encoding="utf-8")
                    if not verify_checksum(wheel_path, checksums_text):
                        ui.error_panel(
                            "SHA-256 checksum mismatch. "
                            "The downloaded file may be corrupted or tampered with.\n"
                            "Aborting installation."
                        )
                        raise typer.Exit(1)
                    ui.success_panel("Checksum verified.", title="Integrity OK")
                except typer.Exit:
                    raise
                except Exception as e:
                    ui.warning_panel(
                        f"Could not verify checksum: {e}\n"
                        "Proceeding without verification."
                    )
        else:
            ui.warning_panel(
                "No sha256sums.txt found in release assets.\n"
                "Installing without checksum verification.",
                title="No Checksum"
            )

        # Save rollback point
        save_rollback_version(__version__)

        with ui.spinner(f"Installing {tag}…"):
            success, msg = install_wheel(wheel_path)

        if success:
            ui.success_panel(
                f"Nyxora updated to [bold #00FFFF]{tag}[/bold #00FFFF]\n"
                f"Restart your terminal for changes to take effect.",
                title="Update Complete"
            )
        else:
            ui.error_panel(
                f"Installation failed:\n{msg}\n\n"
                f"Try manually:\n  pip install {wheel_path}",
                title="Install Failed"
            )
            raise typer.Exit(1)


@app.command()
def rollback() -> None:
    """Roll back to the previous Nyxora version."""
    from nyxora.core.update_engine import get_rollback_version, rollback_to_previous

    prev = get_rollback_version()
    if not prev:
        ui.error_panel(
            "No rollback version stored.\n"
            "Reinstall manually: https://github.com/scorpiocodex/Nyxora/releases"
        )
        raise typer.Exit(1)

    import questionary
    ok = questionary.confirm(f"Roll back to v{prev}?").ask()
    if not ok:
        ui.info_panel("Rollback cancelled.")
        raise typer.Exit(0)

    with ui.spinner(f"Rolling back to v{prev}…"):
        success, msg = rollback_to_previous()

    if success:
        ui.success_panel(msg, title="Rollback Complete")
    else:
        ui.error_panel(msg, title="Rollback Failed")
        raise typer.Exit(1)


@app.command()
def channel(
    name: str = typer.Argument(..., help="Channel: stable or pre-release"),
) -> None:
    """Set the update channel (stable or pre-release)."""
    if name not in ("stable", "pre-release"):
        ui.error_panel(
            "Invalid channel. Use 'stable' or 'pre-release'."
        )
        raise typer.Exit(1)

    config = Config()
    config.load()
    config.set("update.channel", name)
    config.save()
    ui.success_panel(
        f"Update channel set to [bold #00FFFF]{name}[/bold #00FFFF].",
        title="Channel Updated"
    )
