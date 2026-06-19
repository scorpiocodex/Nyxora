"""v3.1.0 #3 regression — Generate screen clipping.

Two pre-existing 3.0.0 layout defects on the GENERATE screen are guarded here:

1. The charset checkbox `Horizontal` row (Uppercase/Lowercase/Digits/Symbols)
   carried no height and inherited `Horizontal`'s default `height: 1fr`. On any
   window with vertical slack the row inflated well past its 1-row checkboxes,
   rendering as an empty bordered strip below the Length input on the password
   sub-view. `height: auto` (the `.card-btns` class) makes it reserve only its
   true content height.

2. The passphrase Separator input (`#gen-sep`) sits low on the screen. On short
   viewports it can fall below the workspace fold — but since 3.0.1's
   `#workspace { overflow-y: auto }` it must stay reachable by scroll and must
   never be cropped to less than its full height. This guards that.

Driven against the real `NyxoraApp` (header/sidebar/footer chrome present) by
revealing the base workspace and switching it to the generate screen.
"""
from __future__ import annotations

import asyncio

from textual.widgets import Checkbox, Input

from nyxora.tui.app import NyxoraApp
from nyxora.tui.screens.generate import GenerateScreen

SEP_INPUT_HEIGHT = 3  # an Input renders 3 rows (top border, field, bottom border)


async def _open_generate(pilot, app) -> None:
    """Reveal the base workspace behind the unlock overlay and switch to the
    generate screen."""
    await pilot.pause(0.3)
    app.pop_screen()
    await pilot.pause(0.2)
    app._switch_to("generate")
    await pilot.pause(0.3)


def test_generate_checkbox_row_auto_height_not_inflated() -> None:
    """On a window with vertical slack the charset checkbox row must fit its
    checkboxes (height: auto), not inflate to Horizontal's 1fr — which renders
    as an empty bordered box below the Length input."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=(80, 50)) as pilot:
            await _open_generate(pilot, app)
            checkboxes = [
                app.query_one(f"#chk-{name}", Checkbox)
                for name in ("upper", "lower", "digits", "symbols")
            ]
            row = checkboxes[0].parent
            assert row is not None
            content_h = max(cb.region.height for cb in checkboxes)
            assert row.region.height == content_h, (
                f"charset checkbox row height={row.region.height} but its "
                f"checkboxes need only {content_h} — the row inherited "
                f"Horizontal's default 1fr and inflated into an empty bordered "
                f"strip below the Length input (height: auto fixes it)"
            )

    asyncio.run(scenario())


def test_generate_separator_not_cropped_and_reachable() -> None:
    """On a short viewport the passphrase Separator input keeps its full height
    (not cropped) and stays reachable — within the fold or via the workspace's
    overflow-y:auto scroll range."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=(80, 16)) as pilot:
            await _open_generate(pilot, app)
            gen = app.query_one("#screen-generate", GenerateScreen)
            gen._set_mode("passphrase")
            await pilot.pause(0.3)
            sep = app.query_one("#gen-sep", Input)
            ws = app.query_one("#workspace")
            assert sep.region.height == SEP_INPUT_HEIGHT, (
                f"Separator input cropped to height {sep.region.height} "
                f"(expected {SEP_INPUT_HEIGHT}) — an overflow ancestor clips it"
            )
            reachable_bottom = ws.region.y + ws.region.height + ws.max_scroll_y
            sep_bottom = sep.region.y + sep.region.height
            assert sep_bottom <= reachable_bottom, (
                f"Separator bottom={sep_bottom} is past the scrollable extent "
                f"{reachable_bottom} — unreachable on a short viewport"
            )

    asyncio.run(scenario())
