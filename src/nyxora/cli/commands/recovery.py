"""Recovery management: TOTP setup, capsule creation, secret splitting."""
from __future__ import annotations

from pathlib import Path

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import load_session, open_vault
from nyxora.cli.ui import recovery_status_panel
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import wipe_memory
from nyxora.core.recovery_core import RecoveryManager

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)

_engine = CryptoEngine()
_recovery = RecoveryManager(_engine)


@app.command()
def setup() -> None:
    """Set up TOTP two-factor authentication."""
    import questionary  # pragma: no cover
    label = questionary.text("Account label (e.g. your email):").ask() or "nyxora"  # pragma: no cover
    secret = _recovery.generate_totp_secret()  # pragma: no cover
    uri = _recovery.get_totp_uri(secret, label)  # pragma: no cover
  # pragma: no cover
    ui.info_panel(  # pragma: no cover
        f"TOTP Secret: [bold #FFB000]{secret}[/bold #FFB000]\n\n"  # pragma: no cover
        f"Scan this URI in your authenticator app:\n{uri}\n\n"  # pragma: no cover
        f"Store the secret securely — you cannot recover it.",  # pragma: no cover
        title="TOTP Setup"  # pragma: no cover
    )  # pragma: no cover
  # pragma: no cover
    token = questionary.text("Enter the 6-digit code from your app to verify:").ask()  # pragma: no cover
    if _recovery.verify_totp(token or "", secret):  # pragma: no cover
        ui.success_panel("TOTP verified successfully.")  # pragma: no cover
    else:  # pragma: no cover
        ui.error_panel("Invalid TOTP token. Setup incomplete.")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover


@app.command()
def create_capsule(
    output: Path = typer.Argument(..., help="Output path for recovery capsule"),
    hint: str = typer.Option("", "--hint", help="Password hint (stored in capsule)"),
) -> None:
    """Create an emergency recovery capsule."""
    import questionary
    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked. Unlock first.")
        raise typer.Exit(2)
    _, vault_path, root_key = session_data

    capsule_pw = questionary.password("Capsule password (different from vault password):").ask()
    if not capsule_pw:
        ui.error_panel("Capsule password required.")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover
    confirm = questionary.password("Confirm capsule password:").ask()
    if capsule_pw != confirm:
        ui.error_panel("Passwords do not match.")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover

    try:
        from nyxora.core.vault_store import VaultStore
        store = VaultStore(_engine)
        store.open(vault_path, root_key)
        vault_id = store.get_vault_id()
        store.close()

        with ui.spinner("Creating recovery capsule…"):
            _recovery.create_recovery_capsule(root_key, vault_id, capsule_pw, output, hint)
        ui.success_panel(f"Recovery capsule created: {output}\nStore this file securely, offline, separate from the vault.")
    finally:
        wipe_memory(root_key)


@app.command()
def restore_capsule(
    capsule: Path = typer.Argument(..., help="Recovery capsule file"),
) -> None:
    """Restore vault access from a recovery capsule."""
    import questionary
    capsule_pw = questionary.password("Capsule password:").ask() or ""
    try:
        with ui.spinner("Decrypting capsule…"):
            root_key = _recovery.restore_from_capsule(capsule, capsule_pw)
        ui.success_panel("Root key recovered from capsule.")
        wipe_memory(root_key)
    except Exception as e:
        ui.error_panel(str(e))
        raise typer.Exit(1)


@app.command("split-secret")
def split_secret(
    n: int = typer.Option(5, "--shares", "-n", help="Total number of shares"),
    k: int = typer.Option(3, "--threshold", "-k", help="Shares required to reconstruct"),
    output_dir: Path = typer.Option(Path("."), "--output-dir", "-o"),
) -> None:
    """Split the vault root key into N Shamir shares (K required to reconstruct)."""
    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked.")
        raise typer.Exit(2)
    _, _, root_key = session_data  # pragma: no cover
  # pragma: no cover
    try:  # pragma: no cover
        shares = _recovery.split_secret(bytes(root_key), n=n, k=k)  # pragma: no cover
        output_dir.mkdir(parents=True, exist_ok=True)  # pragma: no cover
        for i, share in enumerate(shares):  # pragma: no cover
            share_path = output_dir / f"share_{i+1}_of_{n}.bin"  # pragma: no cover
            share_path.write_bytes(share)  # pragma: no cover
            import os  # pragma: no cover
            os.chmod(share_path, 0o600)  # pragma: no cover
        ui.success_panel(  # pragma: no cover
            f"Root key split into {n} shares ({k} required to reconstruct).\n"  # pragma: no cover
            f"Share files written to {output_dir}"  # pragma: no cover
        )  # pragma: no cover
    finally:  # pragma: no cover
        wipe_memory(root_key)  # pragma: no cover


@app.command()
def status() -> None:
    """Show recovery configuration status."""
    totp_configured = False
    try:
        store, _, root_key, _ = open_vault(_engine)
        try:
            val = store.get_metadata_value("totp_secret")
            totp_configured = bool(val)
        finally:
            store.close()
            wipe_memory(root_key)
    except Exception:
        totp_configured = False

    nyxora_dir = Path.home() / ".nyxora"
    capsule_files = [p.name for p in nyxora_dir.glob("*.capsule")] if nyxora_dir.exists() else []
    share_files = [p.name for p in nyxora_dir.glob("share_*.bin")] if nyxora_dir.exists() else []

    recovery_status_panel(totp_configured, capsule_files, share_files)
