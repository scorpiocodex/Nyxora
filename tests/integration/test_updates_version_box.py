"""Regression: the Updates INSTALLED/LATEST version numbers must be visible.

The version boxes (.version-box) stack two height-1 Statics — a label and the
version number. If the box is one row too short (height 5 = 2 border + 2 padding
+ only 1 content row), the version number (the second child) overflows into the
clipped bottom band and never renders, even though its content is set correctly.

These tests mount the real Updates screen with the real theme and assert each
version-number Static is laid out *inside* its box's visible content viewport —
i.e. not clipped. They fail when .version-box has height 5 and pass at height 6.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Static

from nyxora.tui.screens.updates import UpdatesScreen

THEME = Path(__file__).resolve().parents[2] / "src" / "nyxora" / "tui" / "theme.tcss"


class _UpdatesHarness(App[None]):
    """Minimal host that mounts the Updates screen with the production theme."""

    CSS_PATH = str(THEME)

    def compose(self) -> ComposeResult:
        yield UpdatesScreen()


def test_version_numbers_are_inside_their_box_viewport() -> None:
    async def scenario() -> None:
        app = _UpdatesHarness()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            scr = app.query_one(UpdatesScreen)

            for num_id in ("#ver-current", "#ver-latest"):
                num = scr.query_one(num_id, Static)
                box = num.parent  # the enclosing .version-box
                viewport = box.content_region
                top = viewport.y
                bottom = viewport.y + viewport.height
                num_top = num.region.y
                num_bottom = num.region.y + num.region.height

                # The number Static must sit fully within the box's content
                # viewport (not clipped into the bottom padding/border band).
                assert num.region.height >= 1, f"{num_id} collapsed to height 0"
                assert top <= num_top and num_bottom <= bottom, (
                    f"{num_id} clipped: number rows [{num_top},{num_bottom}) "
                    f"outside box content viewport [{top},{bottom}); "
                    f"box.content_region.height={viewport.height}"
                )

    asyncio.run(scenario())


def test_version_box_has_room_for_label_and_number() -> None:
    """The box content area must fit both stacked height-1 Statics."""
    async def scenario() -> None:
        app = _UpdatesHarness()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            scr = app.query_one(UpdatesScreen)
            for num_id in ("#ver-current", "#ver-latest"):
                box = scr.query_one(num_id, Static).parent
                assert box.content_region.height >= 2, (
                    f"box for {num_id} has only {box.content_region.height} "
                    f"content row(s); needs >= 2 for the label + version number"
                )

    asyncio.run(scenario())
