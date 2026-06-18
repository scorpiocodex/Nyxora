"""v3.0.1 regression — card buttons must stay reachable AND uncollapsed on
short terminals.

Two distinct short-window defects are guarded here:

1. The unlock / create-vault cards once used `align: center middle` on a
   non-scrolling wrapper, so the bottom of the card (its buttons) was pushed
   off-screen with no way to reach it. Fixed by wrapping the card in a
   `ScrollableContainer` with `align: center top` so over-tall content scrolls.

2. The button rows inherited `Horizontal`'s default `height: 1fr`. On a short
   window that must scroll, a `1fr` row collapses to a single row and
   `overflow: hidden` crops the height-3 buttons to their top border — empty,
   clipped, and unreachable at any scroll position. Fixed by giving every card
   button row `height: auto` (the `.card-btns` class).

This test drives each affected screen at a short 80x24 viewport and asserts,
for every card button, that (a) its containing row reserves at least the
button's height (catching the 1fr collapse — row 1 < button 3) and (b) the row
fully contains the button (so it is not cropped). It is RED on the collapsed
rows and GREEN once they reserve `height: auto`.
"""
from __future__ import annotations

import asyncio

from textual.widgets import Button

from nyxora.core.vault_store import EntryRecord
from nyxora.tui.app import NyxoraApp
from nyxora.tui.screens.add_entry import AddEntryScreen
from nyxora.tui.screens.edit_entry import EditEntryScreen
from nyxora.tui.screens.unlock import CreateVaultScreen, UnlockScreen

SHORT = (80, 24)  # a default-sized console — the real-world clip case


def _assert_button_ok(button: Button, label: str) -> None:
    """A card button is healthy when its row reserves at least the button's
    height (so the button is not cropped to its border on a scrolled short
    window) and the row fully contains the button."""
    row = button.parent
    assert row is not None
    # (1) The row must not have collapsed below the button's height. A 1fr row
    #     on a scrolled short window collapses to 1 while the button needs 3,
    #     cropping it to its top border (no label). This is the decisive check.
    assert row.region.height >= button.region.height, (
        f"{label}: button row collapsed to {row.region.height} row(s) but the "
        f"button needs {button.region.height} — the buttons are cropped to "
        f"their border (no label) and unreachable on a short window"
    )
    # (2) The row must contain the button's full *vertical* extent — a
    #     collapsed (or otherwise too-short) row crops the button's lower rows,
    #     hiding its label. (Vertical only: the collapse bug is on the height
    #     axis; horizontal layout within the row is a separate concern.)
    br, rr = button.region, row.region
    assert rr.y <= br.y and (br.y + br.height) <= (rr.y + rr.height), (
        f"{label}: button row does not contain the button vertically (row "
        f"y={rr.y} h={rr.height}, button y={br.y} h={br.height}) — the button "
        f"is cropped and its label hidden"
    )


def test_unlock_buttons_not_clipped_on_short_viewport() -> None:
    """Control: UnlockScreen already used height: auto and must stay healthy."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=SHORT) as pilot:
            await pilot.pause(0.3)
            assert isinstance(app.screen, UnlockScreen)
            _assert_button_ok(
                app.screen.query_one("#btn-unlock", Button), "unlock"
            )
            _assert_button_ok(
                app.screen.query_one("#btn-quit-unlock", Button), "unlock-quit"
            )

    asyncio.run(scenario())


def test_create_vault_buttons_not_clipped_on_short_viewport() -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="create", exe_mode=False)
        async with app.run_test(size=SHORT) as pilot:
            await pilot.pause(0.3)
            assert isinstance(app.screen, CreateVaultScreen)
            _assert_button_ok(
                app.screen.query_one("#btn-create", Button), "create"
            )
            _assert_button_ok(
                app.screen.query_one("#btn-quit-create", Button), "create-quit"
            )

    asyncio.run(scenario())


def test_add_entry_buttons_not_clipped_on_short_viewport() -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=SHORT) as pilot:
            await pilot.pause(0.2)
            await app.push_screen(AddEntryScreen())
            await pilot.pause(0.3)
            assert isinstance(app.screen, AddEntryScreen)
            _assert_button_ok(
                app.screen.query_one("#btn-save", Button), "add-save"
            )
            _assert_button_ok(
                app.screen.query_one("#btn-cancel", Button), "add-cancel"
            )
            _assert_button_ok(
                app.screen.query_one("#btn-gen-pw", Button), "add-generate"
            )

    asyncio.run(scenario())


def test_edit_entry_buttons_not_clipped_on_short_viewport() -> None:
    async def scenario() -> None:
        record = EntryRecord(id="t1", title="Example", password="hunter2pw")
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=SHORT) as pilot:
            await pilot.pause(0.2)
            await app.push_screen(EditEntryScreen(record))
            await pilot.pause(0.3)
            assert isinstance(app.screen, EditEntryScreen)
            _assert_button_ok(
                app.screen.query_one("#btn-save", Button), "edit-save"
            )
            _assert_button_ok(
                app.screen.query_one("#btn-cancel", Button), "edit-cancel"
            )
            _assert_button_ok(
                app.screen.query_one("#btn-gen-pw", Button), "edit-generate"
            )

    asyncio.run(scenario())
