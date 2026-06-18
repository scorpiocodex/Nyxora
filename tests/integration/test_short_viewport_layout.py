"""v3.0.1 regression — screens must scroll, not clip, on short terminals.

The unlock / create-vault cards used `align: center middle` on a non-scrolling
`Vertical` wrapper around an auto-height box. On a short console (the default
~24-row Windows console that the packaged exe opens into) the bottom of the
card — including the UNLOCK VAULT / QUIT buttons — was pushed off-screen with
no way to scroll to it.

This test drives the app at a small viewport and asserts the unlock buttons are
*reachable*: either fully inside the viewport, or inside a scrollable ancestor
that can bring them into view. It is RED on the pre-fix layout (no scrollable
ancestor, button region off-screen) and GREEN once the cards scroll.
"""
from __future__ import annotations

import asyncio

from textual.containers import ScrollableContainer
from textual.widgets import Button

from nyxora.tui.app import NyxoraApp
from nyxora.tui.screens.unlock import CreateVaultScreen, UnlockScreen

SHORT = (80, 24)  # a default-sized console — the real-world clip case


def _has_scrollable_ancestor(widget) -> bool:
    """True if some ancestor is a ScrollableContainer (can scroll to widget)."""
    node = widget.parent
    while node is not None:
        if isinstance(node, ScrollableContainer):
            return True
        node = node.parent
    return False


def _reachable(app: NyxoraApp, widget) -> bool:
    """A widget is reachable if it is fully on-screen, or scroll-reachable."""
    region = widget.region
    fully_visible = region.height > 0 and app.screen.region.contains_region(region)
    return fully_visible or _has_scrollable_ancestor(widget)


def test_unlock_buttons_not_clipped_on_short_viewport() -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=SHORT) as pilot:
            await pilot.pause(0.3)
            assert isinstance(app.screen, UnlockScreen)
            unlock_btn = app.screen.query_one("#btn-unlock", Button)
            quit_btn = app.screen.query_one("#btn-quit-unlock", Button)
            assert _reachable(app, unlock_btn), (
                "UNLOCK VAULT button is clipped off a 24-row viewport with no "
                "scrollable ancestor to reach it"
            )
            assert _reachable(app, quit_btn), (
                "QUIT button is clipped off a 24-row viewport with no "
                "scrollable ancestor to reach it"
            )

    asyncio.run(scenario())


def test_create_vault_buttons_not_clipped_on_short_viewport() -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="create", exe_mode=False)
        async with app.run_test(size=SHORT) as pilot:
            await pilot.pause(0.3)
            assert isinstance(app.screen, CreateVaultScreen)
            create_btn = app.screen.query_one("#btn-create", Button)
            quit_btn = app.screen.query_one("#btn-quit-create", Button)
            assert _reachable(app, create_btn), (
                "CREATE VAULT button is clipped off a 24-row viewport with no "
                "scrollable ancestor to reach it"
            )
            assert _reachable(app, quit_btn), (
                "QUIT button is clipped off a 24-row viewport with no "
                "scrollable ancestor to reach it"
            )

    asyncio.run(scenario())
