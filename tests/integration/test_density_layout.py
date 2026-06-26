"""Regression: vertical-density bugs from 1fr-collapse on Updates + Generate.

Both screens had unclassed Horizontal / panel containers inheriting Textual's
default ``height: 1fr``. On tall viewports those balloon (Updates' CHECK+INSTALL
row stretches into a big mid-screen gap); on short viewports Generate's
passphrase panel collapses to ~2 rows and its fixed-height children overlap the
blocks below it — and because the collapse misreports the panel's size, the
workspace ``virtual_size`` never exceeds the viewport, so ``overflow-y: auto``
never engages (overlap garble instead of a graceful scroll).

These mount the real screens inside a faithful ContentSwitcher #workspace with
the production theme and assert honest layout: the Updates button row is not
ballooned, and the Generate short-viewport passphrase panel neither overlaps its
siblings nor defeats the scroll container.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, ContentSwitcher, Input, Static

from nyxora.tui.screens.generate import GenerateScreen
from nyxora.tui.screens.updates import UpdatesScreen

THEME = str(Path(__file__).resolve().parents[2] / "src" / "nyxora" / "tui" / "theme.tcss")


def _rows(widget) -> range:
    """The half-open row range [y, y+height) a widget occupies on screen."""
    r = widget.region
    return range(r.y, r.y + r.height)


def _overlap(a: range, b: range) -> bool:
    return max(a.start, b.start) < min(a.stop, b.stop)


class _UpdatesHarness(App[None]):
    CSS_PATH = THEME

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-body"):
            with ContentSwitcher(id="workspace", initial="screen-updates"):
                yield UpdatesScreen(id="screen-updates")


class _GenerateHarness(App[None]):
    CSS_PATH = THEME

    def compose(self) -> ComposeResult:
        with Horizontal(id="app-body"):
            with ContentSwitcher(id="workspace", initial="screen-generate"):
                yield GenerateScreen(id="screen-generate")


def test_updates_button_row_not_ballooned() -> None:
    """The CHECK+INSTALL row holds height-3 buttons; it must not stretch to 1fr."""
    async def scenario() -> None:
        app = _UpdatesHarness()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            scr = app.query_one("#screen-updates")
            btn_row = scr.query_one("#btn-check", Button).parent  # the Horizontal
            h = btn_row.region.height
            assert h <= 5, (
                f"CHECK+INSTALL row ballooned to height {h} (1fr) — expected ~3 "
                f"(button height); the slack is the mid-screen gap"
            )

    asyncio.run(scenario())


def test_generate_passphrase_short_viewport_no_overlap_and_scrolls() -> None:
    """On a short terminal the passphrase panel must report honest height:
    no child overlap, and the workspace must actually scroll."""
    async def scenario() -> None:
        app = _GenerateHarness()
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.pause()
            scr = app.query_one("#screen-generate")
            scr._set_mode("passphrase")
            await pilot.pause()

            ws = app.query_one("#workspace", ContentSwitcher)
            sep = scr.query_one("#gen-sep", Input)
            strength = scr.query_one("#gen-strength", Static)
            result = scr.query_one("#gen-result", Static)

            # No vertical overlap between the Separator input and the shared
            # result/strength readouts below the panel.
            assert not _overlap(_rows(sep), _rows(strength)), (
                f"Separator rows {_rows(sep)} overlap gen-strength "
                f"{_rows(strength)} — panel collapsed and painted over siblings"
            )
            assert not _overlap(_rows(sep), _rows(result)), (
                f"Separator rows {_rows(sep)} overlap gen-result {_rows(result)}"
            )

            # The panel reports honest height, so total content exceeds the
            # viewport and the existing overflow-y: auto engages (Separator is
            # reachable by scroll rather than garbled).
            assert ws.virtual_size.height > ws.content_region.height, (
                f"workspace did not scroll: virtual={ws.virtual_size.height} "
                f"<= viewport content={ws.content_region.height} (1fr-collapse "
                f"hid the overflow)"
            )

    asyncio.run(scenario())
