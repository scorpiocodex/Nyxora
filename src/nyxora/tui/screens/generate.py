"""
Nyxora TUI v3.0.0 — GenerateScreen.

Section 6: password and passphrase generation with live strength.
"""
from __future__ import annotations

import math
import secrets
import string
from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Static

from nyxora.tui._markup import escape
from nyxora.tui.screens._shared_bg import (
    NyxBottomBar,
    NyxCornerInfo,
    NyxTopBar,
)


class GenerateScreen(Static):
    """
    Generator screen — Section 6.

    Two modes toggled with p (password) / w (passphrase):
      Password   : length slider-like input, charset toggles,
                   live strength bar, copy button
      Passphrase : word count, separator input, copy button
    """

    BINDINGS = [
        Binding("p", "mode_password",   "Password",   show=True),
        Binding("w", "mode_passphrase", "Passphrase", show=True),
        Binding("g", "generate",        "Generate",   show=True),
        Binding("c", "copy_result",     "Copy",       show=True),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._mode   = "password"
        self._result = ""

    def compose(self) -> ComposeResult:
        yield NyxTopBar([("GENERATOR", True), ("SECTION 6", False), ("CSPRNG", False)])
        with Horizontal(classes="nyx-corners-top"):
            yield NyxCornerInfo(
                "ENTROPY SOURCE", ["secrets.choice()", "OS CSPRNG", "CRYPTOGRAPHIC"]
            )
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo(
                "CHARSET", ["UPPER+LOWER+DIGITS", "+SYMBOLS=94", "EFF WORDLIST"]
            )
        yield Static(" ◆  GENERATE", classes="screen-title")

        # Mode selector (card-btns -> height: auto; otherwise this Horizontal
        # inherits the default height: 1fr and balloons on tall windows).
        with Horizontal(classes="card-btns"):
            yield Button("p  PASSWORD",   id="btn-mode-pw",  classes="primary")
            yield Button("w  PASSPHRASE", id="btn-mode-pp")

        # ── Password options ─────────────────────────────
        with Vertical(id="panel-password"):
            yield Label("Length  (8 – 128)", classes="form-label")
            yield Input(value="24", id="gen-length")
            # card-btns -> height: auto; without it this Horizontal inherits the
            # default height: 1fr and inflates into an empty bordered strip below
            # the Length input on any window with vertical slack.
            with Horizontal(classes="card-btns"):
                yield Checkbox("Uppercase",  value=True,  id="chk-upper")
                yield Checkbox("Lowercase",  value=True,  id="chk-lower")
                yield Checkbox("Digits",     value=True,  id="chk-digits")
                yield Checkbox("Symbols",    value=True,  id="chk-symbols")
            yield Button("  GENERATE PASSWORD", id="btn-gen-pw",
                         classes="primary")

        # ── Passphrase options ───────────────────────────
        with Vertical(id="panel-passphrase"):
            yield Label("Word count  (3 – 12)", classes="form-label")
            yield Input(value="5", id="gen-words")
            yield Label("Separator", classes="form-label")
            yield Input(value="-", id="gen-sep")
            yield Checkbox("Capitalise first letter", value=False,
                           id="chk-capitalize")
            yield Button("  GENERATE PASSPHRASE", id="btn-gen-pp",
                         classes="primary")

        # ── Shared result area ───────────────────────────
        yield Static("", id="gen-result")
        yield Static("", id="gen-strength")
        # card-btns -> height: auto (otherwise this Horizontal inherits 1fr and
        # balloons / collapses with the rest of the column).
        with Horizontal(classes="card-btns"):
            yield Button("  COPY", id="btn-copy-gen", classes="primary")

        with Horizontal(classes="nyx-corners-bot"):
            yield NyxCornerInfo("ALGORITHM", ["UNIFORM RANDOM", "NO BIAS"])
            yield Static("", classes="corner-spacer")
            yield NyxCornerInfo("CLIPBOARD", ["AUTO-CLEAR 30s", "PYPERCLIP"])
        yield NyxBottomBar()

    def on_mount(self) -> None:
        self._set_mode("password")
        self._generate_password()

    def on_show(self) -> None:
        self._generate()

    # ── Mode switching ────────────────────────────────────────────

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        try:
            pw_panel = self.query_one("#panel-password")
            pp_panel = self.query_one("#panel-passphrase")
            pw_panel.styles.display = "block" if mode == "password"   else "none"
            pp_panel.styles.display = "block" if mode == "passphrase" else "none"

            btn_pw = self.query_one("#btn-mode-pw", Button)
            btn_pp = self.query_one("#btn-mode-pp", Button)
            if mode == "password":
                btn_pw.add_class("primary")
                btn_pp.remove_class("primary")
            else:
                btn_pp.add_class("primary")
                btn_pw.remove_class("primary")
        except Exception:
            pass

    def action_mode_password(self)   -> None: self._set_mode("password")
    def action_mode_passphrase(self) -> None: self._set_mode("passphrase")

    def action_generate(self) -> None:
        self._generate()

    def _generate(self) -> None:
        if self._mode == "password":
            self._generate_password()
        else:
            self._generate_passphrase()

    # ── Password generation ───────────────────────────────────────

    def _generate_password(self) -> None:
        try:
            length_raw = self.query_one("#gen-length", Input).value.strip()
            length = max(8, min(128, int(length_raw))) if length_raw.isdigit() else 24

            use_upper   = self.query_one("#chk-upper",   Checkbox).value
            use_lower   = self.query_one("#chk-lower",   Checkbox).value
            use_digits  = self.query_one("#chk-digits",  Checkbox).value
            use_symbols = self.query_one("#chk-symbols", Checkbox).value

            alphabet = ""
            if use_upper:
                alphabet += string.ascii_uppercase
            if use_lower:
                alphabet += string.ascii_lowercase
            if use_digits:
                alphabet += string.digits
            if use_symbols:
                alphabet += "!@#$%^&*()_+-=[]{}|;:,.<>?"

            if not alphabet:
                alphabet = string.ascii_letters + string.digits

            pw = "".join(secrets.choice(alphabet) for _ in range(length))
            self._result = pw
            self._show_result(pw)

        except Exception as exc:
            try:
                self.query_one("#gen-result", Static).update(
                    f"  [red]Generation failed: {escape(str(exc))}[/red]"
                )
            except Exception:
                pass

    # ── Passphrase generation ─────────────────────────────────────

    def _generate_passphrase(self) -> None:
        try:
            words_raw = self.query_one("#gen-words", Input).value.strip()
            n_words   = max(3, min(12, int(words_raw))) if words_raw.isdigit() else 5
            sep       = self.query_one("#gen-sep",  Input).value or "-"
            capitalize = self.query_one("#chk-capitalize", Checkbox).value

            wordlist = _load_wordlist()
            words    = [secrets.choice(wordlist) for _ in range(n_words)]
            if capitalize:
                words = [w.capitalize() for w in words]
            phrase       = sep.join(words)
            self._result = phrase
            self._show_result(phrase)

        except Exception as exc:
            try:
                self.query_one("#gen-result", Static).update(
                    f"  [red]Generation failed: {escape(str(exc))}[/red]"
                )
            except Exception:
                pass

    # ── Result display ────────────────────────────────────────────

    def _show_result(self, value: str) -> None:
        try:
            # The generated value may contain [ ] = which Textual would
            # parse as markup and raise MarkupError at render time.
            self.query_one("#gen-result", Static).update(
                f"  [bold #C89A30]{escape(value)}[/bold #C89A30]"
            )
            self.query_one("#gen-strength", Static).update(
                f"  {_strength_label(value)}\n"
            )
        except Exception:
            pass

    # ── Copy ─────────────────────────────────────────────────────

    def action_copy_result(self) -> None:
        self._do_copy()

    def _do_copy(self) -> None:
        if not self._result:
            return
        try:
            import pyperclip
            pyperclip.copy(self._result)
            self.app.notify(
                "Copied. Clears in 30 s.",
                title="◆ Copied",
                timeout=3,
            )
            self.set_timer(30.0, lambda: pyperclip.copy(""))
        except Exception as exc:
            self.app.notify(
                f"Copy failed: {escape(str(exc))}", severity="error", timeout=3
            )

    # ── Button events ─────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        dispatch = {
            "btn-mode-pw":  lambda: self._set_mode("password"),
            "btn-mode-pp":  lambda: self._set_mode("passphrase"),
            "btn-gen-pw":   self._generate_password,
            "btn-gen-pp":   self._generate_passphrase,
            "btn-copy-gen": self._do_copy,
        }
        handler = dispatch.get(event.button.id or "")
        if handler:
            handler()


# ── Helpers ───────────────────────────────────────────────────────

def _load_wordlist() -> list[str]:
    """Load EFF wordlist from package data, fall back to basic list."""
    try:
        from importlib.resources import files
        data = files("nyxora.data").joinpath("eff_large_wordlist.txt").read_text()
        words = []
        for line in data.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2:
                words.append(parts[-1])
        return words if words else _basic_words()
    except Exception:
        return _basic_words()


def _basic_words() -> list[str]:
    return [
        "apple", "brave", "cedar", "dance", "eagle", "frost",
        "grace", "heart", "ivory", "jazzy", "kneel", "lemon",
        "maple", "noble", "ocean", "piano", "quiet", "river",
        "solar", "tiger", "ultra", "vivid", "water", "xenon",
        "yacht", "zebra",
    ]


def _strength_label(value: str) -> str:
    if not value:
        return ""
    charset = 0
    if any(c.islower()     for c in value):
        charset += 26
    if any(c.isupper()     for c in value):
        charset += 26
    if any(c.isdigit()     for c in value):
        charset += 10
    if any(not c.isalnum() for c in value):
        charset += 32
    bits = int(len(value) * math.log2(max(charset, 1)))
    bar_filled = min(20, bits // 8)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    if bits < 28:
        tag = "[bold red]Very Weak[/bold red]"
    elif bits < 40:
        tag = "[red]Weak[/red]"
    elif bits < 60:
        tag = "[#C89A30]Fair[/#C89A30]"
    elif bits < 128:
        tag = "[#3A7A9A]Strong[/#3A7A9A]"
    else:
        tag = "[bold green]Excellent[/bold green]"
    return f"  [dim]{bar}[/dim]  {tag}  [dim]{bits} bits[/dim]"
