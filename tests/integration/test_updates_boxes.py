"""v3.1.0 #4 regression — Updates screen INSTALLED/LATEST legibility.

The INSTALLED/LATEST boxes were already wired (INSTALLED shows the installed
version in gold; LATEST shows a placeholder on mount and the checked version
after CHECK). The defect was contrast: the "INSTALLED"/"LATEST" labels and the
LATEST "—" placeholder used inline markup color #1E2D3D over the box background
#0D1016 — present-but-invisible — and the inline color even overrode the
stylesheet's intended `.version-lbl { color: #344252 }`.

This guards the legibility fix:
  - the two labels render in the legible-dim #344252 (no #1E2D3D span; the
    `.version-lbl` CSS color applies once the inline override is removed)
  - the LATEST placeholder "—" renders in #344252 (not #1E2D3D)
  - the INSTALLED version number is still gold #C89A30 (not regressed)

Driven against the real `NyxoraApp` by revealing the base workspace and
switching it to the updates screen.
"""
from __future__ import annotations

import asyncio

from textual.color import Color
from textual.widgets import Static

from nyxora.tui.app import NyxoraApp

DIM = Color.parse("#344252")   # legible-dim tone (shared with #6 corner readouts)
INVISIBLE = "#1e2d3d"          # the old near-background color (must be gone)
GOLD = "#c89a30"               # the visible version-number color (must remain)


async def _open_updates(pilot, app) -> None:
    """Reveal the base workspace behind the unlock overlay and switch to the
    updates screen."""
    await pilot.pause(0.3)
    app.pop_screen()
    await pilot.pause(0.2)
    app._switch_to("updates")
    await pilot.pause(0.3)


def _span_colors(widget: Static) -> list[str]:
    """Lower-cased hex colors of every span in the widget's rendered content."""
    content = widget.render()
    return [str(span.style).lower() for span in content.spans]


def _label_by_text(app, text: str) -> Static:
    for lbl in app.query(".version-lbl").results(Static):
        if text in lbl.render().plain:
            return lbl
    raise AssertionError(f"no .version-lbl containing {text!r}")


def test_updates_labels_and_placeholder_legible() -> None:
    """Labels + LATEST placeholder must render in legible #344252, never the
    near-invisible #1E2D3D; the version number must stay gold."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=(100, 40)) as pilot:
            await _open_updates(pilot, app)

            installed_lbl = _label_by_text(app, "INSTALLED")
            latest_lbl = _label_by_text(app, "LATEST")
            placeholder = app.query_one("#ver-latest", Static)
            number = app.query_one("#ver-current", Static)

            # (a) INSTALLED label: no invisible #1E2D3D span; resolves to #344252
            assert INVISIBLE not in _span_colors(installed_lbl), (
                f"INSTALLED label still rendered in invisible {INVISIBLE} — "
                f"spans={_span_colors(installed_lbl)}"
            )
            assert installed_lbl.styles.color == DIM, (
                f"INSTALLED label color={installed_lbl.styles.color}, want {DIM}"
            )

            # (b) LATEST label: same
            assert INVISIBLE not in _span_colors(latest_lbl), (
                f"LATEST label still rendered in invisible {INVISIBLE} — "
                f"spans={_span_colors(latest_lbl)}"
            )
            assert latest_lbl.styles.color == DIM, (
                f"LATEST label color={latest_lbl.styles.color}, want {DIM}"
            )

            # (c) LATEST placeholder "—": explicit dim span, not #1E2D3D
            ph_colors = _span_colors(placeholder)
            assert INVISIBLE not in ph_colors, (
                f"LATEST placeholder still invisible {INVISIBLE} — {ph_colors}"
            )
            assert DIM.hex.lower() in ph_colors, (
                f"LATEST placeholder not the legible-dim {DIM.hex} — {ph_colors}"
            )

            # (d) guard: INSTALLED version number still gold (not regressed)
            assert GOLD in _span_colors(number), (
                f"INSTALLED version number lost its gold {GOLD} — "
                f"spans={_span_colors(number)}"
            )

    asyncio.run(scenario())
