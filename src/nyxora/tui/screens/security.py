"""
Nyxora TUI v3.0.0 — SecurityScreen.

Section 7: paste-and-check password strength analyser.
"""
from __future__ import annotations

import math

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Static

from nyxora.tui.screens._shared_bg import (
    NyxTopBar, NyxBottomBar, NyxCornerInfo,
)


class SecurityScreen(Static):
    """
    Password strength checker — Section 7.

    Paste any password into the input field.
    Live score updates as you type: entropy, charset, grade, advice.
    Session history (masked) shown below — cleared when TUI exits.
    """

    BINDINGS = [
        Binding("escape", "clear", "Clear", show=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._history: list[tuple[str, str]] = []  # (masked, grade)

    def compose(self) -> ComposeResult:
        yield NyxTopBar([
            ("STRENGTH CHECKER", True),
            ("SECTION 7", False),
            ("LOCAL ONLY", False),
        ])
        with Horizontal(classes="nyx-corners-top"):
            yield NyxCornerInfo("ANALYSIS", ["LOCAL ONLY", "NO NETWORK", "NO STORAGE"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("ALGORITHM", ["SHANNON ENTROPY", "CHARSET SCORING"])
        yield Static(" ◆  SECURITY — STRENGTH CHECKER", classes="screen-title")
        yield Static(
            "\n  [dim]Paste a password to analyse its strength.[/dim]\n"
            "  [dim]Nothing is stored — analysis runs locally.[/dim]\n",
        )
        yield Label("Password", classes="form-label")
        yield Input(
            placeholder="Paste or type a password…",
            password=True,
            id="sec-input",
        )
        yield Button("  SHOW / HIDE", id="btn-toggle-pw")
        yield Static("", id="sec-result")
        yield Static("", id="sec-history-title")
        yield Static("", id="sec-history")
        with Horizontal(classes="nyx-corners-bot"):
            yield NyxCornerInfo("PRIVACY", ["NOTHING STORED", "SESSION ONLY"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("GRADES", ["A+/A/B/C/D/F", "ENTROPY BITS"])
        yield NyxBottomBar()

    def on_mount(self) -> None:
        self.query_one("#sec-input", Input).focus()
        self._pw_visible = False

    # ── Events ───────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "sec-input":
            self._analyse(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "sec-input":
            self._record_to_history(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-toggle-pw":
            self._toggle_visibility()

    def action_clear(self) -> None:
        self.query_one("#sec-input", Input).value = ""
        self.query_one("#sec-result", Static).update("")

    # ── Analysis ─────────────────────────────────────────────────

    def _analyse(self, password: str) -> None:
        result = self.query_one("#sec-result", Static)
        if not password:
            result.update("")
            return

        charset = 0
        has_lower   = any(c.islower()     for c in password)
        has_upper   = any(c.isupper()     for c in password)
        has_digits  = any(c.isdigit()     for c in password)
        has_symbols = any(not c.isalnum() for c in password)
        if has_lower:   charset += 26
        if has_upper:   charset += 26
        if has_digits:  charset += 10
        if has_symbols: charset += 32

        bits = int(len(password) * math.log2(max(charset, 1)))

        bar_filled = min(20, bits // 8)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)

        if bits < 28:
            grade = "F"; colour = "bold red";    advice = "Far too weak — use a password manager to generate a strong one."
        elif bits < 40:
            grade = "D"; colour = "red";         advice = "Weak — too short or too simple. Aim for 12+ chars with symbols."
        elif bits < 60:
            grade = "C"; colour = "#C89A30";     advice = "Fair — could be stronger. Add length or more character types."
        elif bits < 80:
            grade = "B"; colour = "#3A7A9A";     advice = "Good — solid for most purposes."
        elif bits < 128:
            grade = "A"; colour = "green";       advice = "Strong — well above average."
        else:
            grade = "A+"; colour = "bold green"; advice = "Excellent — very high entropy. Great choice."

        charset_desc = ", ".join(filter(None, [
            "lowercase"   if has_lower   else "",
            "uppercase"   if has_upper   else "",
            "digits"      if has_digits  else "",
            "symbols"     if has_symbols else "",
        ]))

        text = (
            f"\n"
            f"  [dim]Entropy[/dim]      [{colour}]{bits} bits[/{colour}]  "
            f"[dim]{bar}[/dim]\n"
            f"  [dim]Grade[/dim]        [{colour}]{grade}[/{colour}]\n"
            f"  [dim]Length[/dim]       {len(password)} characters\n"
            f"  [dim]Charset[/dim]      {charset_desc or '—'}  "
            f"[dim]({charset} symbols)[/dim]\n"
            f"\n"
            f"  [dim]{advice}[/dim]\n"
        )
        result.update(text)

    def _toggle_visibility(self) -> None:
        try:
            inp = self.query_one("#sec-input", Input)
            self._pw_visible = not self._pw_visible
            inp.password = not self._pw_visible
        except Exception:
            pass

    def _record_to_history(self, password: str) -> None:
        if not password:
            return
        charset = 0
        if any(c.islower()     for c in password): charset += 26
        if any(c.isupper()     for c in password): charset += 26
        if any(c.isdigit()     for c in password): charset += 10
        if any(not c.isalnum() for c in password): charset += 32
        bits  = int(len(password) * math.log2(max(charset, 1)))
        grade = (
            "F" if bits < 28 else "D" if bits < 40 else
            "C" if bits < 60 else "B" if bits < 80 else
            "A" if bits < 128 else "A+"
        )
        masked = "●" * min(len(password), 12)
        self._history.append((masked, grade))

        try:
            title = self.query_one("#sec-history-title", Static)
            hist  = self.query_one("#sec-history",       Static)
            title.update("\n  [dim]Session history[/dim]\n")
            lines = []
            for m, g in reversed(self._history[-10:]):
                colour = (
                    "bold red" if g == "F" else "red" if g == "D" else
                    "#C89A30" if g == "C" else "#3A7A9A" if g == "B" else
                    "green"
                )
                lines.append(f"  [{colour}]{g}[/{colour}]  {m}\n")
            hist.update("".join(lines))
        except Exception:
            pass
