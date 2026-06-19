"""
Nyxora TUI v3.0.0 — Shared background and chrome components.

Used by every screen to provide consistent Obsidian Tactical
design language: ambient background, status bars, corner readouts.
"""
from __future__ import annotations

import random
from typing import Any

from textual.widgets import Static

# ── Pre-generated ambient background pattern ─────────────────────

def _make_bg(seed: int = 42, width: int = 110, height: int = 40) -> str:
    rng = random.Random(seed)
    hex_chars = "0123456789ABCDEF"
    phrases = [
        "XCHACHA20-POLY1305", "ARGON2ID", "VAULT HMAC OK",
        "ZERO-KNOWLEDGE", "OFFLINE MODE", "SESSION ACTIVE",
        "AES-256-GCM", "MEMORY GUARD", "SCHEMA v2",
        "POLY1305 MAC", "ENTRY ENCRYPTED", "KDF ACTIVE",
        "INTEGRITY CHECK", "OFFLINE · SECURE", "HMAC-SHA256",
        "MASTER KEY: PENDING", "CSPRNG ENTROPY", "RFC 6238",
        "ARGON2ID · 64MB", "XCHACHA20 NONCE",
    ]
    lines = []
    for _ in range(height):
        line: list[str] = []
        x = 0
        while x < width:
            r = rng.random()
            if r < 0.022 and x < width - 9:
                h = "".join(rng.choice(hex_chars) for _ in range(4))
                h2 = "".join(rng.choice(hex_chars) for _ in range(4))
                frag = f"{h} {h2}"
                line.append(frag)
                x += len(frag)
            elif r < 0.038 and x < width - 20:
                phrase = rng.choice(phrases)
                line.append(phrase)
                x += len(phrase)
            elif r < 0.12:
                line.append("·")
                x += 1
            else:
                line.append(" ")
                x += 1
        lines.append("".join(line[:width]))
    return "\n".join(lines)


BG_PATTERN: str = _make_bg()


# ── Shared widgets ────────────────────────────────────────────────

class NyxBackground(Static):
    """
    Ambient dot-grid + hex-text background layer.
    Place as the first yield in any screen's compose(); use
    layout: overlay on the parent so content renders above it.
    """

    DEFAULT_CSS = """
    NyxBackground {
        width: 100%;
        height: 100%;
        color: #141E28;
        background: transparent;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(BG_PATTERN, **kwargs)


class NyxTopBar(Static):
    """
    One-line top status bar.

    items: list of (text, active) tuples.
    active=True → amber text; False → very dim.
    """

    DEFAULT_CSS = """
    NyxTopBar {
        width: 100%;
        height: 1;
        background: #04060C;
        color: #1E2D3D;
        text-align: center;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        items: list[tuple[str, bool]],
        **kwargs: Any,
    ) -> None:
        parts: list[str] = []
        for i, (text, active) in enumerate(items):
            if active:
                parts.append(f"[#C89A30]{text}[/#C89A30]")
            else:
                parts.append(f"[#1E2D3D]{text}[/#1E2D3D]")
            if i < len(items) - 1:
                parts.append("  [#0E1820]·[/#0E1820]  ")
        super().__init__("".join(parts), **kwargs)


class NyxBottomBar(Static):
    """
    One-line bottom cipher / attribution bar.
    Pass custom text or leave blank for the default cipher info.
    """

    DEFAULT_CSS = """
    NyxBottomBar {
        width: 100%;
        height: 1;
        background: #04060C;
        color: #1E2D3D;
        text-align: center;
        padding: 0 1;
    }
    """

    _DEFAULT_TEXT = (
        "[#1A2535]XCHACHA20-POLY1305[/#1A2535]"
        "  [#0E1820]◆[/#0E1820]  "
        "[#1A2535]ARGON2ID[/#1A2535]"
        "  [#0E1820]◆[/#0E1820]  "
        "[#1A2535]OFFLINE · ZERO-KNOWLEDGE[/#1A2535]"
        "  [#0E1820]◆[/#0E1820]  "
        "[#1A2535]SCORPIOCODEX[/#1A2535]"
    )

    def __init__(self, text: str = "", **kwargs: Any) -> None:
        super().__init__(text or self._DEFAULT_TEXT, **kwargs)


class NyxCornerInfo(Static):
    """
    Small corner readout block.

    label : section heading (rendered in very dim amber)
    lines : 1-3 data lines (rendered very dim)
    """

    DEFAULT_CSS = """
    NyxCornerInfo {
        width: auto;
        height: auto;
        color: #141E28;
        background: transparent;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        label: str,
        lines: list[str],
        **kwargs: Any,
    ) -> None:
        lbl  = f"[#1A2838]{label}[/#1A2838]\n"
        body = "\n".join(
            f"[#0E1820]{line}[/#0E1820]" for line in lines
        )
        super().__init__(lbl + body, **kwargs)


class NyxSep(Static):
    """
    Amber gradient separator line with centre diamond.
    """

    DEFAULT_CSS = """
    NyxSep {
        width: 100%;
        height: 1;
        background: transparent;
        color: #C89A30;
        text-align: center;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            "[#1A2535]──────────────────[/#1A2535]"
            "[#C89A30]◆[/#C89A30]"
            "[#1A2535]──────────────────[/#1A2535]",
            **kwargs,
        )
