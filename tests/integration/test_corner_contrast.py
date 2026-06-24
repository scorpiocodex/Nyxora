"""v3.1.0 #6 regression — corner-readout (NyxCornerInfo) text legibility.

The corner readouts render their data lines via inline markup colored #0E1820 —
rgb(14,24,32) on the Screen background #0B0D12 (rgb 11,13,18) — effectively
invisible. (The CSS `NyxCornerInfo { color: #0E1820 }` is only a fallback for
unmarked text; every line here is marked up, so the inline color is what
renders.) The data lines now use #344252, the legible-dim tone adopted for the
Updates-screen labels in #4 — readable while staying understated.

Asserts the rendered Content spans of a NyxCornerInfo contain #344252 and no
longer contain #0E1820 (the label heading keeps its own dim tone).
"""
from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult

from nyxora.tui.screens._shared_bg import NyxCornerInfo

DIM = "#344252"        # legible-dim tone (shared with #4's labels)
INVISIBLE = "#0e1820"  # the near-background colour the data lines must leave


class _CornerProbe(App[None]):
    def compose(self) -> ComposeResult:
        yield NyxCornerInfo("CIPHER", ["XCHACHA20-POLY1305", "ARGON2ID"])


def _span_colors(widget: NyxCornerInfo) -> list[str]:
    return [str(span.style).lower() for span in widget.render().spans]


def test_corner_readout_text_is_legible() -> None:
    async def scenario() -> None:
        app = _CornerProbe()
        async with app.run_test(size=(60, 10)) as pilot:
            await pilot.pause(0.1)
            ci = app.query_one(NyxCornerInfo)
            colors = _span_colors(ci)
            assert INVISIBLE not in colors, (
                f"corner-readout data lines still render near-invisible "
                f"{INVISIBLE} on the #0B0D12 background — spans={colors}"
            )
            assert DIM in colors, (
                f"corner-readout data lines are not the legible-dim {DIM} — "
                f"spans={colors}"
            )

    asyncio.run(scenario())
