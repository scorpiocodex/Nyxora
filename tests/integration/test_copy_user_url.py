"""v3.1.0 #26 — Copy Username / Copy URL actions on the Manage screen.

Feature originally proposed by @neoastra303 in PR #1 (closed), reimplemented to
the project's bar. These regressions lock the requirements PR #1 missed:

  (a) SECURITY — user-controlled username/url must never be funnelled raw into a
      Rich-markup notification. The implementation does not echo the value (the
      safest option), so a malicious-markup username/url is copied verbatim to
      the clipboard and never appears (interpreted or otherwise) in any notify
      text. A future change that echoes the value unescaped (PR #1's bug) would
      reintroduce the markup string and fail these assertions.
  (b) CORRECT FIELD — copy-user copies .username, copy-url copies .url; never
      the password / a secret.
  (c) BUTTON STATES — the two new buttons follow #5's rule (disabled with no
      selection, enabled on selection).
  (d) LAYOUT — the action bar grows 4 -> 6 buttons and must not overflow the
      detail panel at a narrow terminal width (each button region contained).
  (e) NO AUTO-CLEAR — unlike the password copy, username/url copies do NOT
      schedule the 30s clipboard clear (non-secret; clearing pasteable data is
      worse UX).
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

from textual.widgets import Button, ListView

from nyxora.core.vault_store import EntryRecord
from nyxora.tui.app import NyxoraApp
from nyxora.tui.screens.manage import ManageScreen

NEW_BTNS = ("#btn-copy-user", "#btn-copy-url")
ALL_ACTION_BTNS = (
    "#btn-copy", "#btn-copy-user", "#btn-copy-url",
    "#btn-edit", "#btn-totp", "#btn-delete",
)
MAL_USER = "[red]evil[/red]"
MAL_URL = "[bold]http://x[/]"
SECRET_PW = "S3cretPasswordValue!"


async def _open_manage(pilot, app) -> ManageScreen:
    await pilot.pause(0.3)
    app.pop_screen()
    await pilot.pause(0.2)
    app._switch_to("manage")
    await pilot.pause(0.4)
    return app.query_one("#screen-manage", ManageScreen)


def _record_notify(app) -> list[tuple[str, dict]]:
    calls: list[tuple[str, dict]] = []

    def fake_notify(message: str = "", **kwargs) -> None:
        calls.append((message, kwargs))

    app.notify = fake_notify  # type: ignore[method-assign]
    return calls


def test_copy_user_url_escaping_and_correct_field() -> None:
    """(a) security + (b) correct field: malicious-markup username/url are
    copied verbatim and never echoed into a notification; password never
    copied."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_manage(pilot, app)
            screen._selected = EntryRecord(
                id="m1", title="Malicious", username=MAL_USER,
                password=SECRET_PW, url=MAL_URL,
            )
            notifies = _record_notify(app)

            with patch("pyperclip.copy") as copy_mock:
                screen.action_copy_user()
                assert copy_mock.call_args is not None
                assert copy_mock.call_args.args[0] == MAL_USER, (
                    "copy-user must copy the exact username verbatim"
                )
                assert SECRET_PW not in str(copy_mock.call_args), (
                    "copy-user must never copy the password"
                )

            with patch("pyperclip.copy") as copy_mock:
                screen.action_copy_url()
                assert copy_mock.call_args.args[0] == MAL_URL, (
                    "copy-url must copy the exact url verbatim"
                )

            # No notification echoed the user-controlled value (no markup
            # injection surface). Guards against a future unescaped echo.
            joined = " ".join(m for m, _ in notifies)
            assert "evil" not in joined and "[red]" not in joined, (
                f"username value leaked into a notification: {notifies!r}"
            )
            assert "[bold]" not in joined and "http://x" not in joined, (
                f"url value leaked into a notification: {notifies!r}"
            )
            assert notifies, "copy actions should still confirm with a notify"

    asyncio.run(scenario())


def test_copy_user_url_button_states_track_selection() -> None:
    """(c) the two new buttons disable with no selection, enable on selection."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_manage(pilot, app)

            assert screen._selected is None
            for bid in NEW_BTNS:
                assert app.query_one(bid, Button).disabled is True, (
                    f"{bid} must be disabled with no selection"
                )

            rec = EntryRecord(
                id="sel1", title="Example", username="alice",
                password="hunter2pw", url="https://e",
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

            assert screen._selected is not None
            for bid in NEW_BTNS:
                assert app.query_one(bid, Button).disabled is False, (
                    f"{bid} must be enabled once an entry is selected"
                )

            screen.action_clear_search()
            await pilot.pause(0.3)
            for bid in NEW_BTNS:
                assert app.query_one(bid, Button).disabled is True, (
                    f"{bid} must re-disable when selection clears"
                )

    asyncio.run(scenario())


def test_action_bar_six_buttons_no_overflow_narrow() -> None:
    """(d) all six action buttons stay within the action-bar row at a narrow
    terminal width (no horizontal overflow / clip)."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=(80, 24)) as pilot:
            screen = await _open_manage(pilot, app)
            bar = screen.query_one("#action-bar")
            btns = [app.query_one(bid, Button) for bid in ALL_ACTION_BTNS]
            assert len(btns) == 6
            for b in btns:
                br, rr = b.region, bar.region
                assert rr.x <= br.x and br.right <= rr.right, (
                    f"{b.id} overflows the action bar (bar x={rr.x}..{rr.right}, "
                    f"button x={br.x}..{br.right}) — clipped at a narrow width"
                )

    asyncio.run(scenario())


def test_copy_user_url_no_auto_clear() -> None:
    """(e) username/url copies must NOT schedule the 30s clipboard clear that
    the password copy does."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=(120, 40)) as pilot:
            screen = await _open_manage(pilot, app)
            screen._selected = EntryRecord(
                id="m1", title="t", username="alice",
                password="hunter2pw", url="https://e",
            )
            _record_notify(app)

            timers: list[float] = []
            orig_set_timer = screen.set_timer

            def spy_set_timer(delay, callback, *a, **k):  # type: ignore[no-untyped-def]
                timers.append(delay)
                return None

            screen.set_timer = spy_set_timer  # type: ignore[method-assign]
            try:
                with patch("pyperclip.copy"):
                    screen.action_copy_pw()
                assert 30.0 in timers, (
                    "password copy should schedule the 30s auto-clear (control)"
                )

                timers.clear()
                with patch("pyperclip.copy"):
                    screen.action_copy_user()
                    screen.action_copy_url()
                assert 30.0 not in timers, (
                    "username/url copies must NOT schedule the 30s clear"
                )
            finally:
                screen.set_timer = orig_set_timer  # type: ignore[method-assign]

    asyncio.run(scenario())
