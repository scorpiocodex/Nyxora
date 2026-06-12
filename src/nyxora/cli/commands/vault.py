"""Vault lifecycle commands: unlock, lock, panic, status, health-check, change-password."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer

from nyxora.cli import ui
from nyxora.cli.helpers import (
    clear_session,
    get_vault_path,
    load_session,
    save_session,
)
from nyxora.cli.ui import checklist_panel, is_json_mode, json_out, session_dashboard
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import SecureString, generate_session_token, wipe_memory
from nyxora.core.session_core import DEFAULT_INACTIVITY_TIMEOUT, SessionManager
from nyxora.core.vault_store import VaultStore, recover_interrupted_password_change
from nyxora.utils.config import Config
from nyxora.utils.exceptions import NyxoraError

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)

_engine = CryptoEngine()
_session = SessionManager()


def _fsync_file(path: Path) -> None:
    """Best-effort fsync for power-loss durability. Never raises."""
    try:
        fd = os.open(str(path), os.O_RDWR)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:  # pragma: no cover
        pass


@app.command()
def unlock(
    vault_path: Optional[Path] = typer.Option(None, "--vault", "-v", help="Path to vault file."),
    create: bool = typer.Option(False, "--create", help="Create a new vault if it doesn't exist."),
) -> None:
    """Unlock the vault with master password."""
    config = Config()
    config.load()
    vp = vault_path or get_vault_path(config)

    # Heal any interrupted change-password swap before the salt is read
    # (see core.vault_store.recover_interrupted_password_change).
    healed = recover_interrupted_password_change(vp)
    if healed == "rolled-forward":
        ui.info_panel(
            "An interrupted password change was completed — "
            "the NEW master password is now active."
        )
    elif healed == "rolled-back":
        ui.info_panel(
            "An interrupted password change was rolled back — "
            "the OLD master password remains active."
        )

    import questionary
    password = questionary.password("Master password:").ask()
    if not password:
        ui.error_panel("No password entered.")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover

    session_token = generate_session_token()

    with SecureString(password) as pw:
        if not vp.exists():
            if not create:  # pragma: no cover
                ui.error_panel(f"Vault not found at {vp}. Use --create to initialize.")  # pragma: no cover
                raise typer.Exit(1)  # pragma: no cover
            # Create new vault  # pragma: no cover
            salt = _engine.generate_salt()  # pragma: no cover
            vp.parent.mkdir(parents=True, exist_ok=True)  # pragma: no cover
            with ui.spinner("Deriving key (Argon2id)…"):  # pragma: no cover
                root_key = _engine.derive_key(pw, salt)  # pragma: no cover
            store = VaultStore(_engine)  # pragma: no cover
            store.initialize(vp, root_key)  # pragma: no cover
            store.close()  # pragma: no cover
            salt_file = vp.with_suffix(".salt")  # pragma: no cover
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC  # pragma: no cover
            if hasattr(os, "O_NOINHERIT"):  # pragma: no cover
                flags |= getattr(os, "O_NOINHERIT")  # pragma: no cover
            fd = os.open(str(salt_file), flags, 0o600)  # pragma: no cover
            with os.fdopen(fd, "wb") as f:  # pragma: no cover
                f.write(salt)  # pragma: no cover
            _session.unlock(root_key, session_token)  # pragma: no cover
            _session.record_successful_unlock()  # pragma: no cover
            save_session(session_token, str(vp), root_key.hex())  # pragma: no cover
            wipe_memory(root_key)  # pragma: no cover
            ui.success_panel(f"New vault created and unlocked at {vp}")  # pragma: no cover
        else:
            salt_file = vp.with_suffix(".salt")
            if not salt_file.exists():
                ui.error_panel("Vault salt file missing. Cannot derive key.")  # pragma: no cover
                raise typer.Exit(1)  # pragma: no cover
            salt = salt_file.read_bytes()
            with ui.spinner("Deriving key (Argon2id)…"):
                root_key = _engine.derive_key(pw, salt)
            store = VaultStore(_engine)
            try:
                store.open(vp, root_key)
            except NyxoraError as e:
                _session.record_failed_attempt()
                wipe_memory(root_key)
                # IntegrityError on open almost always means wrong password,
                # not actual tampering — give the user an accurate message.
                from nyxora.utils.exceptions import IntegrityError as _IE
                if isinstance(e, _IE):
                    ui.error_panel(
                        "Wrong password or corrupted vault.\n"
                        "If you are sure the password is correct, run "
                        "'nyx vault health-check' to inspect vault integrity."
                    )
                else:
                    ui.error_panel(e.user_message)
                raise typer.Exit(1)
            store.close()
            _session.unlock(root_key, session_token)
            _session.record_successful_unlock()
            save_session(session_token, str(vp), root_key.hex())
            wipe_memory(root_key)
            ui.success_panel(f"Vault unlocked: {vp}")

            # Non-blocking update notification
            from nyxora.utils.config import Config as _Cfg
            _cfg = _Cfg()
            _cfg.load()
            if _cfg.get("update.check_on_startup", True):
                import threading

                from nyxora.core.update_engine import background_check
                _channel = _cfg.get("update.channel", "stable")

                def _notify() -> None:
                    msg = background_check(_channel)
                    if msg:
                        from nyxora.cli.ui import console
                        console.print(
                            f"  [#444441]⟳ {msg}[/#444441]"
                        )

                threading.Thread(target=_notify, daemon=True, name="nyxora-update-check").start()


@app.command()
def init(
    vault_path: Optional[Path] = typer.Option(None, "--vault", "-v", help="Path to vault file."),
) -> None:
    """Initialize a new vault."""
    config = Config()
    config.load()
    vp = vault_path or get_vault_path(config)

    import questionary
    password = questionary.password("Master password:").ask()
    if not password:
        ui.error_panel("No password entered.")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover
    confirm = questionary.password("Confirm password:").ask()
    if password != confirm:
        ui.error_panel("Passwords do not match.")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover

    vp.parent.mkdir(parents=True, exist_ok=True)
    salt = _engine.generate_salt()
    session_token = generate_session_token()

    with SecureString(password) as pw:
        with ui.spinner("Deriving key (Argon2id)…"):
            root_key = _engine.derive_key(pw, salt)

    store = VaultStore(_engine)
    store.initialize(vp, root_key)
    store.close()

    # Store salt alongside vault
    salt_file = vp.with_suffix(".salt")

    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOINHERIT"):
        flags |= getattr(os, "O_NOINHERIT")
    fd = os.open(str(salt_file), flags, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(salt)

    save_session(session_token, str(vp), root_key.hex())
    wipe_memory(root_key)
    ui.success_panel(f"Vault initialized at {vp}")


@app.command("change-password")
def change_password() -> None:
    """Change the master password for the current vault."""
    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked. Run 'nyx vault unlock' first.")  # pragma: no cover
        raise typer.Exit(2)  # pragma: no cover

    _, vault_path, root_key = session_data
    session_token = generate_session_token()
    try:
        # Heal/clear any leftovers from a previously interrupted
        # change-password before staging a new one (a stale .nyx.new
        # would collide with initialize below).
        if recover_interrupted_password_change(vault_path) == "rolled-forward":
            ui.info_panel(
                "A previously interrupted password change was completed — "
                "the password from that run is now active. If this session "
                "was unlocked with the older password, unlock again first."
            )

        import questionary
        new_password = questionary.password("New master password:").ask()
        if not new_password:
            ui.error_panel("No password entered.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover

        confirm = questionary.password("Confirm new password:").ask()
        if new_password != confirm:
            ui.error_panel("Passwords do not match.")
            raise typer.Exit(1)

        store = VaultStore(_engine)
        store.open(vault_path, root_key)

        new_salt = _engine.generate_salt()
        with SecureString(new_password) as pw:
            with ui.spinner("Deriving new key (Argon2id)…"):
                new_root_key = _engine.derive_key(pw, new_salt)

        # ── Phase 1: STAGE. Originals untouched — a crash anywhere in
        # this phase leaves the old vault+salt live (old password works)
        # and recovery-on-open clears the stale staged files.
        new_vault = vault_path.with_suffix(".nyx.new")
        staged_salt = vault_path.with_suffix(".salt.new")
        new_store = VaultStore(_engine)
        new_store.initialize(new_vault, new_root_key)

        with ui.spinner("Migrating and re-encrypting vault data…"):
            new_store.migrate_from_store(store)

        new_store.close()
        store.close()

        # Verify the new vault opens correctly before touching the original
        verify_store = VaultStore(_engine)
        try:
            verify_store.open(new_vault, new_root_key)
            verify_store.close()
        except Exception:
            new_vault.unlink(missing_ok=True)
            raise

        # Stage the new salt durably (write + fsync — it must never be
        # truncated: it doubles as the recovery signal for an interrupted
        # commit) and fsync the new vault best-effort.
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        if hasattr(os, "O_NOINHERIT"):
            flags |= getattr(os, "O_NOINHERIT")
        fd = os.open(str(staged_salt), flags, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(new_salt)
            f.flush()
            os.fsync(f.fileno())
        _fsync_file(new_vault)

        # ── Phase 2: COMMIT — two atomic os.replace calls, vault first.
        # Between them the disk briefly holds a new-key vault with the
        # old salt, but vault.salt.new still exists; recovery-on-open
        # (recover_interrupted_password_change) rolls the salt forward,
        # so every crash point leaves the vault openable with exactly
        # one of the two passwords — never neither.
        salt_file = vault_path.with_suffix(".salt")
        try:
            os.replace(new_vault, vault_path)
        except Exception as e:
            # The vault replace failed — originals are still live.
            # Roll back fully so the old password stays authoritative.
            new_vault.unlink(missing_ok=True)
            staged_salt.unlink(missing_ok=True)
            ui.error_panel(
                f"Password change aborted: {e}\n"
                "The vault is unchanged — your OLD password remains active."
            )
            raise typer.Exit(1)

        try:
            os.replace(staged_salt, salt_file)
        except Exception:
            # The vault is already under the NEW key and the staged salt
            # is still on disk — the next unlock completes the swap
            # automatically. The password change has effectively
            # succeeded; do NOT report it as a failure.
            ui.warning_panel(
                "Vault re-encrypted under the new password, but the salt "
                "finalisation was deferred. It completes automatically on "
                "the next unlock — use the NEW password."
            )

        try:
            save_session(session_token, str(vault_path), new_root_key.hex())
        except Exception:
            ui.warning_panel(
                "Password changed, but the session could not be refreshed. "
                "Run 'nyx vault unlock' with your NEW password."
            )
        wipe_memory(new_root_key)
        ui.success_panel("Master password changed successfully.")

    except typer.Exit:
        raise
    except Exception as e:
        ui.error_panel(
            f"Failed to change password: {e}\n"
            "The vault is unchanged — your OLD password remains active."
        )
        raise typer.Exit(1)
    finally:
        wipe_memory(root_key)


@app.command()
def lock() -> None:
    """Lock the vault and wipe the session key."""
    clear_session()
    ui.success_panel("Vault locked. Session wiped.")


@app.command()
def panic() -> None:
    """PANIC — immediately wipe session and exit."""
    clear_session()
    ui.error_panel("PANIC: Session destroyed. All key material wiped.", title="PANIC")
    raise typer.Exit(4)


@app.command()
def status() -> None:
    """Show vault lock state and entry count."""
    session_data = load_session()
    if session_data is None:
        ui.info_panel("Vault is LOCKED", title="Vault Status")  # pragma: no cover
        return  # pragma: no cover
    session_id, vault_path, root_key = session_data
    try:
        store = VaultStore(_engine)
        store.open(vault_path, root_key)
        count = store.entry_count()
        store.close()
        if is_json_mode():
            json_out({
                "locked": False,
                "vault_path": str(vault_path),
                "entry_count": count,
                "session_id": session_id[:8],
            })
            return
        session_dashboard(
            session_id=session_id,
            vault_path=str(vault_path),
            entry_count=count,
            failed_attempts=_session.get_failed_attempts(),
            inactivity_timeout=DEFAULT_INACTIVITY_TIMEOUT,
        )
    finally:
        wipe_memory(root_key)


@app.command("health-check")
def health_check() -> None:
    """Run a full integrity verification of the vault."""
    session_data = load_session()
    if session_data is None:
        ui.error_panel("Vault is locked. Run 'nyx vault unlock' first.")  # pragma: no cover
        raise typer.Exit(2)  # pragma: no cover
    _, vault_path, root_key = session_data
    try:
        store = VaultStore(_engine)
        store.open(vault_path, root_key)
        with ui.spinner("Verifying vault integrity…"):
            report = store.verify_integrity()
        store.close()
        items = [
            (report.schema_ok,       "Schema fingerprint"),
            (report.vault_hmac_ok,   "Vault-wide HMAC chain"),
            (len(report.entries_failed) == 0,
             f"Entry integrity ({report.entries_checked} entries checked)"),
            (report.audit_log_ok,    "Audit log integrity"),
            (report.passed,          "Overall vault health"),
        ]
        subtitle = (
            "" if report.passed
            else f"Failed entries: {', '.join(report.entries_failed[:5])}"
        )
        checklist_panel("Vault Health Check", items, subtitle=subtitle)
    finally:
        wipe_memory(root_key)


@app.command("profiles")
def list_profiles() -> None:
    """List all vault profiles."""
    from rich.table import Table

    from nyxora.cli.helpers import load_profiles
    from nyxora.cli.ui import ELEC_PURPLE, NEON_CYAN, console

    data = load_profiles()
    profiles = data.get("profiles", {})
    active = data.get("active")

    if not profiles:
        ui.info_panel(
            "No profiles configured.\n"
            "Use [bold]nyx vault add-profile <name> --path <vault.nyx>[/bold] "
            "to create one.",
            title="Vault Profiles"
        )
        return

    table = Table(
        title="[nyx.title]Vault Profiles[/nyx.title]",
        border_style=ELEC_PURPLE,
        header_style=f"bold {NEON_CYAN}",
    )
    table.add_column("Active")
    table.add_column("Name")
    table.add_column("Vault Path")
    table.add_column("Description")

    for name, info in sorted(profiles.items()):
        marker = "[bold #00FF41]●[/bold #00FF41]" if name == active else " "
        table.add_row(
            marker,
            f"[bold]{name}[/bold]" if name == active else name,
            info.get("vault_path", ""),
            info.get("description", ""),
        )
    console.print(table)


@app.command("use")
def use_profile(
    name: str = typer.Argument(..., help="Profile name to activate"),
) -> None:
    """Switch to a named vault profile."""
    from nyxora.cli.helpers import set_active_profile
    try:
        set_active_profile(name)
        ui.success_panel(
            f"Active profile set to [bold]{name}[/bold].",
            title="Profile Switched"
        )
    except ValueError as e:
        ui.error_panel(str(e))
        raise typer.Exit(1)


@app.command("add-profile")
def add_profile(
    name: str = typer.Argument(..., help="Profile name"),
    path: Path = typer.Option(..., "--path", "-p",
                              help="Path to vault .nyx file"),
    description: str = typer.Option("", "--description", "-d",
                                    help="Optional description"),
    activate: bool = typer.Option(False, "--activate",
                                  help="Set as active profile immediately"),
) -> None:
    """Register a new vault profile."""
    from nyxora.cli.helpers import load_profiles, save_profiles

    data = load_profiles()
    data.setdefault("profiles", {})[name] = {
        "vault_path": str(path),
        "description": description,
    }
    if data.get("active") is None:
        data["active"] = name  # first profile auto-activates
    save_profiles(data)

    if activate:
        data["active"] = name
        save_profiles(data)

    ui.success_panel(
        f"Profile [bold]{name}[/bold] registered.\n"
        f"Vault path: {path}",
        title="Profile Added"
    )


@app.command("remove-profile")
def remove_profile(
    name: str = typer.Argument(..., help="Profile name to remove"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove a vault profile (does not delete the vault file)."""
    import questionary

    from nyxora.cli.helpers import load_profiles, save_profiles

    data = load_profiles()
    if name not in data.get("profiles", {}):
        ui.error_panel(f"Profile '{name}' not found.")
        raise typer.Exit(1)

    if not yes:
        ok = questionary.confirm(
            f"Remove profile '{name}'? (vault file is NOT deleted)"
        ).ask()
        if not ok:
            ui.info_panel("Cancelled.")
            return

    del data["profiles"][name]
    if data.get("active") == name:
        # Auto-select another profile if one exists
        remaining = list(data["profiles"].keys())
        data["active"] = remaining[0] if remaining else None
    save_profiles(data)

    ui.success_panel(
        f"Profile [bold]{name}[/bold] removed.",
        title="Profile Removed"
    )


from nyxora.cli.commands.import_ import import_entries  # noqa: E402

app.command("import")(import_entries)
