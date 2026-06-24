"""v3.1.0 #5 (PART B) regression — Manage action-button enabled state.

The Manage screen's COPY/EDIT/TOTP/DELETE buttons were always enabled, even
with no entry selected ("Select an entry from the list" / 0 entries), implying
actions that can't run. They must be disabled when there is no selection and
enabled when an entry is selected — disabled, not hidden, so the bar stays
stable (no layout jump).

Driven against the real `NyxoraApp` by revealing the base workspace and
switching it to the manage screen. With the test vault locked the list starts
empty (no selection → disabled); an entry is injected and selected through the
real ListView path to assert the buttons enable, then the selection is cleared
to assert they re-disable.
"""
from __future__ import annotations

import asyncio

from textual.widgets import Button, ListView

from nyxora.core.vault_store import EntryRecord
from nyxora.tui.app import NyxoraApp
from nyxora.tui.screens.manage import ManageScreen

ACTION_BTNS = ("#btn-copy", "#btn-edit", "#btn-totp", "#btn-delete")


async def _open_manage(pilot, app) -> ManageScreen:
    await pilot.pause(0.3)
    app.pop_screen()
    await pilot.pause(0.2)
    app._switch_to("manage")
    await pilot.pause(0.4)
    return app.query_one("#screen-manage", ManageScreen)


def _disabled(app) -> dict[str, bool]:
    return {bid: app.query_one(bid, Button).disabled for bid in ACTION_BTNS}


def test_manage_action_buttons_track_selection() -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_manage(pilot, app)

            # (a) no selection on mount → all four disabled
            assert screen._selected is None
            states = _disabled(app)
            assert all(states.values()), (
                f"action buttons must be disabled with no selection — {states}"
            )

            # inject one entry and select it through the real ListView path
            rec = EntryRecord(
                id="sel1", title="Example", username="alice", password="hunter2pw"
            )
            screen._entries = [rec]
            screen._filtered = [rec]
            screen._rebuild_list()
            await pilot.pause(0.3)
            lv = screen.query_one("#entry-items", ListView)
            lv.focus()
            lv.index = 0
            await pilot.pause(0.1)
            await pilot.press("enter")
            await pilot.pause(0.3)

            # (b) entry selected → all four enabled
            assert screen._selected is not None and screen._selected.id == "sel1"
            states = _disabled(app)
            assert not any(states.values()), (
                f"action buttons must be enabled once an entry is selected — {states}"
            )

            # (c) clear selection → re-disable
            screen.action_clear_search()
            await pilot.pause(0.3)
            assert screen._selected is None
            states = _disabled(app)
            assert all(states.values()), (
                f"action buttons must re-disable when selection clears — {states}"
            )

    asyncio.run(scenario())
