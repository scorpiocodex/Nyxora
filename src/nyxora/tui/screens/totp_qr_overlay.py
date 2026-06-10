"""
Nyxora TUI v3.0.0 — TotpQrOverlay.

Pushed as a full-screen overlay from RecoveryScreen after the TOTP
secret has been saved to the vault. Display-only: renders the otpauth
QR with the full screen's vertical room (the side #qr-panel is too
short to show an unclipped, scannable QR). Esc dismisses.
"""
from __future__ import annotations

import pyotp
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from nyxora.tui.screens.recovery import _render_qr


class TotpQrOverlay(Screen[None]):
    """Full-screen TOTP QR display overlay."""

    BINDINGS = [
        Binding("escape", "close", "Close", show=True),
    ]

    def __init__(
        self,
        secret: str,
        account_label: str,
        issuer: str = "NYXORA",
    ) -> None:
        super().__init__()
        self.secret = secret
        self.account_label = account_label
        self.issuer = issuer

    def compose(self) -> ComposeResult:
        with Vertical(id="qr-overlay-box"):
            yield Static(
                "◆  SCAN WITH AUTHENTICATOR APP",
                id="qr-overlay-title",
            )
            yield Static(
                self.account_label,
                id="qr-overlay-account",
                markup=False,
            )
            yield Static(
                self._qr_text(),
                id="qr-overlay-qr",
                markup=False,
            )
            yield Static(
                f"Manual entry:  {self.secret}",
                id="qr-overlay-secret",
                markup=False,
            )
            yield Static("Press Esc to close", id="qr-overlay-hint")

    def _qr_text(self) -> str:
        """Render the otpauth URI as half-block QR text."""
        uri = pyotp.TOTP(self.secret).provisioning_uri(
            name=self.account_label,
            issuer_name=self.issuer,
        )
        lines = _render_qr(uri)
        return "".join(
            line.rstrip("\n") + "\n" for line in lines
        ).rstrip("\n")

    def action_close(self) -> None:
        self.dismiss(None)
