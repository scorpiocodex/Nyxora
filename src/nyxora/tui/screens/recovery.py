"""
Nyxora TUI v3.0.0 — RecoveryScreen.

Section 4: emergency recovery configuration.
Three pathways: TOTP 2FA, Recovery Capsule, Shamir Secret Sharing.
"""
from __future__ import annotations

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static

from nyxora.tui.screens._shared_bg import (
    NyxTopBar, NyxBottomBar, NyxCornerInfo,
)


class RecoveryScreen(Static):
    """
    Emergency recovery screen — Section 4.

    Three protocol panels selectable with keys 1/2/3:
      1  TOTP two-factor — shows QR code + seed
      2  Recovery Capsule — create/verify encrypted capsule
      3  Shamir Shares — split root key into N shares
    """

    BINDINGS = [
        Binding("1", "show_totp",    "TOTP",    show=True),
        Binding("2", "show_capsule", "Capsule", show=True),
        Binding("3", "show_shamir",  "Shamir",  show=True),
        Binding("r", "refresh",      "Refresh", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._active_protocol = "totp"

    def compose(self) -> ComposeResult:
        yield NyxTopBar([
            ("EMERGENCY RECOVERY", True),
            ("SECTION 4", False),
            ("OFFLINE", False),
        ], id="recovery-topbar")
        with Horizontal(classes="nyx-corners-top"):
            yield NyxCornerInfo("PROTOCOLS", ["TOTP: RFC 6238", "PYOTP", "BASE32"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("CAPSULE", ["ARGON2ID KDF", "XCHACHA20"])
        yield Static(" ◆  EMERGENCY RECOVERY", classes="screen-title")
        yield Static("", id="recovery-status-line")

        # Protocol selector tabs
        with Horizontal(id="protocol-selector"):
            yield Button("1  TOTP 2FA",     id="btn-p-totp",    classes="primary")
            yield Button("2  Capsule",       id="btn-p-capsule")
            yield Button("3  Shamir Shares", id="btn-p-shamir")

        yield Static("", id="recovery-status")

        # Main content area: left panel + right QR panel
        with Horizontal(id="recovery-main"):

            # Left: all three protocol panels
            with Vertical(id="recovery-left"):

                # TOTP panel
                with Vertical(id="panel-totp"):
                    yield Static(
                        "\n  [dim]TOTP Two-Factor Authentication[/dim]\n",
                        classes="info-card-title",
                    )
                    yield Label(
                        "Account label  (e.g. your email)",
                        classes="form-label",
                    )
                    yield Input(placeholder="nyxora@example.com", id="totp-label")
                    yield Button(
                        "  SETUP TOTP", id="btn-totp-setup", classes="primary",
                    )
                    yield Static("", id="totp-status-msg")

                # Capsule panel  (hidden initially)
                with Vertical(id="panel-capsule"):
                    yield Static(
                        "\n  [dim]Recovery Capsule[/dim]\n",
                        classes="info-card-title",
                    )
                    yield Label(
                        "Capsule password  (different from vault password)",
                        classes="form-label",
                    )
                    yield Input(placeholder="Capsule password…",
                                password=True, id="capsule-pw")
                    yield Label("Confirm password", classes="form-label")
                    yield Input(placeholder="Confirm…",
                                password=True, id="capsule-pw-confirm")
                    yield Label(
                        "Hint  (optional, stored in capsule)",
                        classes="form-label",
                    )
                    yield Input(placeholder="Password hint…", id="capsule-hint")
                    yield Button(
                        "  CREATE CAPSULE", id="btn-capsule-create",
                        classes="primary",
                    )
                    yield Static("", id="capsule-output")

                # Shamir panel  (hidden initially)
                with Vertical(id="panel-shamir"):
                    yield Static(
                        "\n  [dim]Shamir Secret Sharing[/dim]\n",
                        classes="info-card-title",
                    )
                    yield Label("Total shares  (N)", classes="form-label")
                    yield Input(value="5", id="shamir-n")
                    yield Label(
                        "Threshold  (K required to reconstruct)",
                        classes="form-label",
                    )
                    yield Input(value="3", id="shamir-k")
                    yield Label("Output directory", classes="form-label")
                    yield Input(
                        value=str(Path.home() / ".nyxora" / "shares"),
                        id="shamir-dir",
                    )
                    yield Button(
                        "  SPLIT SECRET", id="btn-shamir-split",
                        classes="primary",
                    )
                    yield Static("", id="shamir-output")

            # Right: QR code panel (only visible when TOTP active)
            with Vertical(id="qr-panel"):
                yield Static(
                    "QR code will\nappear here\nafter SETUP TOTP",
                    id="qr-placeholder",
                )
                yield Static("", id="totp-output")

        with Horizontal(classes="nyx-corners-bot"):
            yield NyxCornerInfo("SHAMIR", ["GF(2^8) FIELD", "N-OF-K SCHEME"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("RECOVERY", ["OFFLINE ONLY", "ZERO-KNOWLEDGE"])
        yield NyxBottomBar()

    def on_mount(self) -> None:
        self._show_panel("totp")
        self._refresh_status()

    def on_show(self) -> None:
        self._refresh_status()

    # ── Status line ──────────────────────────────────────────────

    def _refresh_status(self) -> None:
        """Show current recovery configuration status."""
        try:
            from nyxora.cli.helpers import open_vault
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.core.memory_guard import wipe_memory

            engine = CryptoEngine()
            store, _, root_key, _ = open_vault(engine)
            totp_val = store.get_metadata_value("totp_secret")
            store.close()
            wipe_memory(root_key)
            totp_ok = bool(totp_val)
        except Exception:
            totp_ok = False

        nyxora_dir = Path.home() / ".nyxora"
        capsule_ok = bool(list(nyxora_dir.rglob("*.capsule"))) \
            if nyxora_dir.exists() else False
        shamir_ok  = bool(list(nyxora_dir.rglob("share_*.bin"))) \
            if nyxora_dir.exists() else False

        def tick(ok: bool) -> str:
            return "[bold green]✓[/bold green]" if ok else "[red]✗[/red]"

        try:
            self.query_one("#recovery-status-line", Static).update(
                f"  {tick(totp_ok)} TOTP    "
                f"  {tick(capsule_ok)} Capsule    "
                f"  {tick(shamir_ok)} Shamir shares"
            )
        except Exception:
            pass

        try:
            tb = self.query_one("#recovery-topbar", NyxTopBar)
            def _t(ok: bool, label: str) -> str:
                c = "#C89A30" if ok else "#CC3333"
                s = "✓" if ok else "✗"
                return f"[{c}]{label}:{s}[/{c}]"
            sep = "  [#0E1820]·[/#0E1820]  "
            tb.update(
                _t(totp_ok, "TOTP") + sep +
                _t(capsule_ok, "CAPSULE") + sep +
                _t(shamir_ok, "SHAMIR") + sep +
                "[#1E2D3D]SECTION 4[/#1E2D3D]"
            )
        except Exception:
            pass

    # ── Panel switching ──────────────────────────────────────────

    def _show_panel(self, protocol: str) -> None:
        self._active_protocol = protocol
        panels = {
            "totp":    "#panel-totp",
            "capsule": "#panel-capsule",
            "shamir":  "#panel-shamir",
        }
        btns = {
            "totp":    "#btn-p-totp",
            "capsule": "#btn-p-capsule",
            "shamir":  "#btn-p-shamir",
        }
        for key, sel in panels.items():
            try:
                panel = self.query_one(sel)
                if key == protocol:
                    panel.styles.display = "block"
                else:
                    panel.styles.display = "none"
            except Exception:
                pass
        for key, sel in btns.items():
            try:
                btn = self.query_one(sel, Button)
                if key == protocol:
                    btn.add_class("primary")
                else:
                    btn.remove_class("primary")
            except Exception:
                pass
        # The TOTP confirmation text has no meaning in the other
        # sub-modes — clear the side panel so it doesn't linger there.
        if protocol != "totp":
            try:
                self.query_one("#totp-output", Static).update("")
            except Exception:
                pass

    def action_show_totp(self)    -> None: self._show_panel("totp")
    def action_show_capsule(self) -> None: self._show_panel("capsule")
    def action_show_shamir(self)  -> None: self._show_panel("shamir")
    def action_refresh(self)      -> None: self._refresh_status()

    # ── Button events ────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        dispatch = {
            "btn-p-totp":        lambda: self._show_panel("totp"),
            "btn-p-capsule":     lambda: self._show_panel("capsule"),
            "btn-p-shamir":      lambda: self._show_panel("shamir"),
            "btn-totp-setup":    self._do_totp_setup,
            "btn-capsule-create":self._do_capsule_create,
            "btn-shamir-split":  self._do_shamir_split,
        }
        handler = dispatch.get(event.button.id)
        if handler:
            handler()

    # ── TOTP setup ───────────────────────────────────────────────

    def _do_totp_setup(self) -> None:
        status_msg = self.query_one("#totp-status-msg", Static)
        out        = self.query_one("#totp-output",     Static)

        from nyxora.cli.helpers import load_session as _ls
        if _ls() is None:
            status_msg.update(
                "  [red]Vault is locked — unlock first.[/red]"
            )
            return

        label_val = (
            self.query_one("#totp-label", Input).value.strip()
            or "nyxora"
        )
        status_msg.update("  [#C89A30]Generating TOTP secret…[/#C89A30]")

        try:
            from nyxora.core.recovery_core import RecoveryManager
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.cli.helpers        import open_vault
            from nyxora.core.memory_guard  import wipe_memory

            engine   = CryptoEngine()
            recovery = RecoveryManager(engine)
            secret   = recovery.generate_totp_secret()

            store, _, root_key, _ = open_vault(engine)
            store.set_metadata_value("totp_secret", secret)
            store.close()
            wipe_memory(root_key)

            # Hide placeholder; side panel shows a brief confirmation
            try:
                ph = self.query_one("#qr-placeholder", Static)
                ph.update("")
            except Exception:
                pass

            # Status message in left panel
            status_msg.update(
                f"  [bold #C89A30]Secret:[/bold #C89A30] "
                f"[dim]{secret}[/dim]\n"
                f"  [bold green]✓[/bold green]  Saved to vault.\n"
                f"  [dim]Scan QR with your authenticator app.[/dim]"
            )

            out.update(
                "\n✓ TOTP saved.\nQR shown in overlay —\npress Esc to close."
            )

            # QR goes to a full-screen overlay: the side panel is too
            # short to show all 21+ rows unclipped (HANDOFF §7 / 3-4)
            from nyxora.tui.screens.totp_qr_overlay import TotpQrOverlay
            self.app.push_screen(
                TotpQrOverlay(secret=secret, account_label=label_val)
            )
            self._refresh_status()

        except Exception as exc:
            status_msg.update(
                f"  [red]TOTP setup failed: {exc}[/red]"
            )

    # ── Capsule create ───────────────────────────────────────────

    def _do_capsule_create(self) -> None:
        out  = self.query_one("#capsule-output", Static)

        from nyxora.cli.helpers import load_session as _ls
        if _ls() is None:
            out.update("  [red]Vault is locked — unlock first (press 1).[/red]")
            return

        pw   = self.query_one("#capsule-pw",         Input).value
        conf = self.query_one("#capsule-pw-confirm",  Input).value
        hint = self.query_one("#capsule-hint",        Input).value.strip()

        if not pw:
            out.update("  [red]Capsule password is required.[/red]")
            return
        if pw != conf:
            out.update("  [red]Passwords do not match.[/red]")
            self.query_one("#capsule-pw-confirm", Input).value = ""
            return

        out.update("  Creating capsule…")
        try:
            from nyxora.core.recovery_core import RecoveryManager
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.cli.helpers import open_vault
            from nyxora.core.memory_guard import wipe_memory
            import time

            engine   = CryptoEngine()
            recovery = RecoveryManager(engine)
            store, _, root_key, vault_path = open_vault(engine)
            vault_id = store.get_vault_id() \
                if hasattr(store, "get_vault_id") else "nyxora"
            store.close()

            capsule_path = (
                Path.home() / ".nyxora" /
                f"recovery_{int(time.time())}.capsule"
            )
            recovery.create_recovery_capsule(
                root_key, vault_id, pw, capsule_path, hint
            )
            wipe_memory(root_key)

            out.update(
                f"  [bold green]✓[/bold green]  Capsule created:\n"
                f"  {capsule_path}\n"
                f"  [dim]Store this file securely, offline.[/dim]\n"
            )
            self.app.notify(
                f"Capsule: {capsule_path.name}",
                title="◆ Recovery Capsule",
                timeout=4,
            )
            self._refresh_status()

        except Exception as exc:
            out.update(f"  [red]Capsule failed: {exc}[/red]")

    # ── Shamir split ─────────────────────────────────────────────

    def _do_shamir_split(self) -> None:
        out = self.query_one("#shamir-output", Static)

        from nyxora.cli.helpers import load_session as _ls
        if _ls() is None:
            out.update("  [red]Vault is locked — unlock first (press 1).[/red]")
            return

        try:
            n = int(self.query_one("#shamir-n", Input).value.strip())
            k = int(self.query_one("#shamir-k", Input).value.strip())
        except ValueError:
            out.update("  [red]N and K must be integers.[/red]")
            return

        if k > n:
            out.update("  [red]Threshold K cannot exceed total shares N.[/red]")
            return
        if k < 2:
            out.update("  [red]Threshold K must be at least 2.[/red]")
            return

        out_dir_str = self.query_one("#shamir-dir", Input).value.strip()
        out_dir = Path(out_dir_str)
        out.update("  Splitting secret…")

        try:
            from nyxora.core.recovery_core import RecoveryManager
            from nyxora.core.crypto_engine import CryptoEngine
            from nyxora.cli.helpers import open_vault
            from nyxora.core.memory_guard import wipe_memory
            import os

            engine   = CryptoEngine()
            recovery = RecoveryManager(engine)
            _, _, root_key, _ = open_vault(engine)

            shares = recovery.split_secret(bytes(root_key), n=n, k=k)
            wipe_memory(root_key)

            out_dir.mkdir(parents=True, exist_ok=True)
            paths = []
            for i, share in enumerate(shares):
                sp = out_dir / f"share_{i+1}_of_{n}.bin"
                sp.write_bytes(share)
                os.chmod(sp, 0o600)
                paths.append(sp.name)

            lines = [
                f"  [bold green]✓[/bold green]  "
                f"Root key split into {n} shares "
                f"({k} required to reconstruct).\n\n"
            ]
            for p in paths:
                lines.append(f"  [dim]  {p}[/dim]\n")
            lines.append(f"\n  [dim]Written to: {out_dir}[/dim]\n")
            out.update("".join(lines))

            self.app.notify(
                f"{n} shares written to {out_dir.name}/",
                title="◆ Shamir",
                timeout=4,
            )
            self._refresh_status()

        except Exception as exc:
            out.update(f"  [red]Split failed: {exc}[/red]")


# ── QR code renderer ─────────────────────────────────────────────

def _render_qr(uri: str) -> list[str]:
    """
    Render a QR code using Unicode half-block chars.
    Returns plain strings (no Rich markup) — white CSS bg handles contrast.
    """
    try:
        import qrcode
        from qrcode.constants import ERROR_CORRECT_L
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_L,
            box_size=1,
            border=2,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        matrix = qr.get_matrix()
        rows   = len(matrix)
        cols   = len(matrix[0]) if rows > 0 else 0
        lines  = []

        for y in range(0, rows - (rows % 2), 2):
            line = ""
            for x in range(cols):
                top = matrix[y][x]
                bot = matrix[y + 1][x] if (y + 1) < rows else False
                if top and bot:
                    line += "█"
                elif top and not bot:
                    line += "▀"
                elif not top and bot:
                    line += "▄"
                else:
                    line += " "
            lines.append(line + "\n")

        # Handle odd last row
        if rows % 2 == 1:
            line = ""
            for x in range(cols):
                line += "▀" if matrix[rows - 1][x] else " "
            lines.append(line + "\n")

        return lines

    except ImportError:
        return [
            "\n  qrcode package not installed.\n",
            "  pip install qrcode\n",
        ]
    except Exception as exc:
        return [f"\n  QR error: {exc}\n"]
