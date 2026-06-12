"""HANDOFF §13 Step 4 — automated 9-block TUI test plan (Phase A).

Drives all nine manual test blocks via Textual Pilot, asserting every
machine-checkable expectation and saving an SVG snapshot of each major
state for the maintainer's Phase B visual review (design-system checks
like colour and spacing are "visual: Phase B" and live in the SVGs).

Isolation:
  - Block 1 uses a genuine on-disk vault in tmp_path. UnlockScreen
    resolves its vault through unlock._get_default_vault_path and
    persists sessions through cli.helpers — both are patched, so the
    real ~/.nyxora is never read or written.
  - Blocks 2-9 patch the same helper seams (load_session / open_vault)
    but back them with a real VaultStore on tmp_path. The FakeStore in
    tests.unit.test_tui._patch_fake_vault only implements
    set_metadata_value/close, which cannot support Manage
    (list_entries) or the health check (verify_integrity).
  - Backup writes are redirected to tmp_path via BackupScreen._backup_dir.
  - The updates network check is mocked at nyxora.core.update_engine.
"""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
from pathlib import Path
from typing import NamedTuple

import pytest
from textual.widgets import Button, Checkbox, ContentSwitcher, Input, ListView, Static

from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.vault_store import VaultStore
from nyxora.tui.app import NyxoraApp
from nyxora.tui.screens.backup import BackupScreen
from nyxora.tui.screens.generate import GenerateScreen
from nyxora.tui.screens.manage import EntryItem, ManageScreen
from nyxora.tui.screens.recovery import RecoveryScreen
from nyxora.tui.screens.security import SecurityScreen
from nyxora.tui.screens.totp_qr_overlay import TotpQrOverlay
from nyxora.tui.screens.unlock import UnlockScreen
from nyxora.tui.screens.updates import UpdatesScreen
from nyxora.tui.screens.vault import VaultScreen

SVG_DIR = Path(tempfile.gettempdir()) / "nyxora_verify" / "9block"
SVG_DIR.mkdir(parents=True, exist_ok=True)

TEST_PW = "Test-Vault-Pw-12345"  # digits 1-5: doubles as a C2 confirmation
SIZE = (140, 50)


def _svg(app: NyxoraApp, name: str) -> None:
    """Save a Phase B snapshot. Visual judgement happens on these files."""
    app.save_screenshot(str(SVG_DIR / f"{name}.svg"))


_MARKUP_TAG = re.compile(r"\[/?[^\[\]]*?\]")


def _text(widget: Static) -> str:
    """Plain text of a Static — str(content) keeps Rich tags, strip them."""
    return _MARKUP_TAG.sub("", str(widget.content))


def _notifications(app: NyxoraApp) -> list[str]:
    """Flatten current toast notifications to searchable strings."""
    notes = getattr(app, "_notifications", [])
    return [
        f"{getattr(n, 'title', '')} {getattr(n, 'message', '')}"
        for n in notes
    ]


# ── Fixtures ──────────────────────────────────────────────────────


class RealVaultCtx(NamedTuple):
    path: Path
    sessions: dict[str, tuple[str, Path, str]]


class SyntheticCtx(NamedTuple):
    path: Path
    key_hex: str


@pytest.fixture
def real_vault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> RealVaultCtx:
    """Genuine on-disk vault + isolated session plumbing (Block 1)."""
    import nyxora.cli.helpers as helpers
    import nyxora.tui.screens.unlock as unlock_mod

    engine = CryptoEngine()
    vp = tmp_path / "vault.nyx"
    salt = engine.generate_salt()
    root_key = engine.derive_key(TEST_PW, salt)
    store = VaultStore(engine)
    store.initialize(vp, root_key)
    store.add_entry("TestEntry", "entry-pw-999", username="tester")
    store.close()
    (tmp_path / "vault.salt").write_bytes(salt)

    sessions: dict[str, tuple[str, Path, str]] = {}

    def fake_save(session_id: str, vault_path: str, key_hex: str) -> None:
        sessions["live"] = (session_id, Path(vault_path), key_hex)

    def fake_load() -> tuple[str, Path, bytearray] | None:
        if "live" not in sessions:
            return None
        sid, path, key_hex = sessions["live"]
        return sid, path, bytearray.fromhex(key_hex)

    def fake_clear() -> None:
        sessions.pop("live", None)

    monkeypatch.setattr(unlock_mod, "_get_default_vault_path", lambda: vp)
    monkeypatch.setattr(helpers, "save_session", fake_save)
    monkeypatch.setattr(helpers, "load_session", fake_load)
    monkeypatch.setattr(helpers, "clear_session", fake_clear)
    return RealVaultCtx(path=vp, sessions=sessions)


@pytest.fixture
def synthetic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> SyntheticCtx:
    """Unlocked-vault state for Blocks 2-9, backed by a real tmp vault."""
    import nyxora.cli.helpers as helpers

    engine = CryptoEngine()
    vp = tmp_path / "vault.nyx"
    root_key = bytearray(os.urandom(32))
    key_hex = bytes(root_key).hex()
    store = VaultStore(engine)
    store.initialize(vp, root_key)
    store.add_entry(
        "TestA", "testa-password-123", username="alice",
        url="https://a.example.com", tags=["test"],
    )
    store.close()

    def fake_load() -> tuple[str, Path, bytearray]:
        # fresh bytearray per call: callers wipe the key after use
        return "9block-session", vp, bytearray.fromhex(key_hex)

    def fake_open(
        engine_: CryptoEngine,
    ) -> tuple[VaultStore, str, bytearray, Path]:
        s = VaultStore(engine_)
        s.open(vp, bytearray.fromhex(key_hex))
        return s, "9block-session", bytearray.fromhex(key_hex), vp

    monkeypatch.setattr(helpers, "load_session", fake_load)
    monkeypatch.setattr(helpers, "open_vault", fake_open)
    return SyntheticCtx(path=vp, key_hex=key_hex)


# ── BLOCK 1 — Authentication (real vault) ─────────────────────────


def test_block1_authentication(real_vault: RealVaultCtx) -> None:
    async def scenario() -> None:
        sessions = real_vault.sessions
        app = NyxoraApp(start_screen="unlock", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.3)
            assert isinstance(app.screen, UnlockScreen)
            _svg(app, "block1_cold_launch")

            # Wrong password → error message, still locked
            pw = app.screen.query_one("#unlock-password", Input)
            pw.focus()
            await pilot.pause()
            await pilot.press(*"wrong-password")
            await pilot.press("enter")
            await pilot.pause(1.0)
            err = _text(app.screen.query_one("#unlock-error", Static))
            assert "Wrong password" in err
            assert isinstance(app.screen, UnlockScreen)
            assert not sessions
            _svg(app, "block1_wrong_pw")

            # Correct password — every char (incl. digits 1-5) must land
            assert pw.value == ""  # handler clears the field on failure
            await pilot.press(*TEST_PW)
            await pilot.pause()
            assert pw.value == TEST_PW  # real-vault C2 confirmation
            await pilot.press("enter")
            await pilot.pause(1.0)
            assert not isinstance(app.screen, UnlockScreen)
            switcher = app.query_one("#workspace", ContentSwitcher)
            assert switcher.current == "screen-manage"
            assert "live" in sessions
            _svg(app, "block1_unlocked")

            # Relock from the Vault screen → session cleared, re-auth
            await pilot.pause(0.3)
            if isinstance(app.focused, Input):
                app.set_focus(None)
            await pilot.press("1")
            await pilot.pause(0.3)
            assert switcher.current == "screen-vault"
            vault_scr = app.query_one(VaultScreen)
            await pilot.click(vault_scr.query_one("#btn-lock", Button))
            await pilot.pause(0.5)
            assert not sessions
            assert isinstance(app.screen, UnlockScreen)
            _svg(app, "block1_relocked")

    asyncio.run(scenario())


# ── BLOCK 2 — Vault screen ────────────────────────────────────────


def test_block2_vault_info_and_health_check(synthetic: SyntheticCtx) -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="vault", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            vault_scr = app.query_one(VaultScreen)
            badge = _text(vault_scr.query_one("#vault-status-badge", Static))
            info = _text(vault_scr.query_one("#vault-info-grid", Static))
            assert "UNLOCKED" in badge
            for field in ("Path", "Entries", "Size", "Cipher", "Vault ID"):
                assert field in info, field
            assert "vault.nyx" in info
            assert re.search(r"Entries\s+1\b", info)
            _svg(app, "block2_vault_info")

            await pilot.click(vault_scr.query_one("#btn-health", Button))
            await pilot.pause(0.5)
            health = _text(vault_scr.query_one("#health-result", Static))
            for check in (
                "Schema fingerprint",
                "Vault-wide HMAC chain",
                "Entry integrity",
                "Audit log integrity",
            ):
                assert check in health, check
            assert "PASSED" in health
            _svg(app, "block2_health_check")

    asyncio.run(scenario())


# ── BLOCK 3 — Manage ──────────────────────────────────────────────


def test_block3_manage_list_detail_copy(
    synthetic: SyntheticCtx, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Headless CI runners have no clipboard backend, so stub pyperclip.copy
    # and assert the app's copy SUCCESS path deterministically everywhere.
    # (The app's graceful "Copy failed" handling is exercised by real
    # pyperclip failures, not by this test.)
    import pyperclip

    copied: list[str] = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)

    async def scenario() -> None:
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            manage = app.query_one(ManageScreen)
            lv = manage.query_one("#entry-items", ListView)
            items = list(lv.query(EntryItem))
            assert len(items) == 1
            assert items[0].record.title == "TestA"
            _svg(app, "block3_list")

            # Select → detail panel renders (masked pw, strength, …)
            lv.focus()
            await pilot.pause()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause(0.3)
            detail = _text(manage.query_one("#entry-detail", Static))
            for part in ("TestA", "USERNAME", "alice", "PASSWORD",
                         "●", "STRENGTH"):
                assert part in detail, part
            assert "testa-password-123" not in detail  # masked by default
            _svg(app, "block3_detail")

            # COPY → no crash, status reflects copy, stub got the password
            await pilot.click(manage.query_one("#btn-copy", Button))
            await pilot.pause(0.3)
            assert any("Copied" in n for n in _notifications(app))
            assert copied == ["testa-password-123"]
            _svg(app, "block3_copy")

            # DELETE first press → confirm prompt only, nothing deleted
            lv.focus()
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause(0.2)
            detail = _text(manage.query_one("#entry-detail", Static))
            assert "Press D again to confirm deletion." in detail
            assert len(list(lv.query(EntryItem))) == 1
            _svg(app, "block3_delete_confirm")

    asyncio.run(scenario())


def test_block3_manage_search(synthetic: SyntheticCtx) -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            manage = app.query_one(ManageScreen)
            lv = manage.query_one("#entry-items", ListView)
            search = manage.query_one("#entry-search", Input)
            search.focus()
            await pilot.pause()

            await pilot.press(*"test")
            await pilot.pause(0.2)
            assert search.value == "test"  # 80829d5: no focus steal
            assert len(list(lv.query(EntryItem))) == 1  # matches TestA
            _svg(app, "block3_search")

            await pilot.press("escape")  # clears the query
            await pilot.pause(0.2)
            assert search.value == ""
            await pilot.press(*"zzz")
            await pilot.pause(0.2)
            assert len(list(lv.query(EntryItem))) == 0
            detail = _text(manage.query_one("#entry-detail", Static))
            assert "0 entries" in detail
            _svg(app, "block3_search_nomatch")

    asyncio.run(scenario())


# ── BLOCK 4 — Backup ──────────────────────────────────────────────


def test_block4_backup(
    synthetic: SyntheticCtx,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backups_dir = tmp_path / "backups"
    # Redirect ~/.nyxora/backups to tmp_path — never the real home
    monkeypatch.setattr(
        BackupScreen, "_backup_dir", lambda self: backups_dir
    )

    async def scenario() -> None:
        app = NyxoraApp(start_screen="backup", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            bscr = app.query_one(BackupScreen)
            wrap = _text(bscr.query_one("#backup-table-wrap", Static))
            assert "No backups found" in wrap
            _svg(app, "block4_initial")

            await pilot.click(bscr.query_one("#btn-verify", Button))
            await pilot.pause(0.3)
            status = _text(bscr.query_one("#backup-status", Static))
            assert "No backups to verify" in status
            _svg(app, "block4_verify_empty")

            await pilot.click(bscr.query_one("#btn-create", Button))
            await pilot.pause(0.5)
            status = _text(bscr.query_one("#backup-status", Static))
            assert "Backup created" in status
            wrap = _text(bscr.query_one("#backup-table-wrap", Static))
            assert "1 backup(s) found" in wrap
            assert len(list(backups_dir.glob("*.nyx.bak"))) == 1
            _svg(app, "block4_created")

            # Round-trip: the new backup verifies against the session key
            await pilot.click(bscr.query_one("#btn-verify", Button))
            await pilot.pause(0.5)
            status = _text(bscr.query_one("#backup-status", Static))
            assert "is valid" in status
            assert "1 entries" in status

    asyncio.run(scenario())


# ── BLOCK 5 — Recovery ────────────────────────────────────────────


def test_block5_recovery(synthetic: SyntheticCtx) -> None:
    async def scenario() -> str:
        app = NyxoraApp(start_screen="recovery", exe_mode=False)
        async with app.run_test(size=(140, 46)) as pilot:
            await pilot.pause(0.4)
            rscr = app.query_one(RecoveryScreen)
            status_line = _text(
                rscr.query_one("#recovery-status-line", Static)
            )
            for word in ("TOTP", "Capsule", "Shamir"):
                assert word in status_line, word
            for btn_id in ("#btn-p-totp", "#btn-p-capsule", "#btn-p-shamir"):
                assert rscr.query_one(btn_id, Button) is not None
            _svg(app, "block5_recovery_modes")

            # TOTP setup → overlay opens (e10e5a7)
            rscr.query_one("#totp-label", Input).value = "nyxora@example.com"
            await pilot.pause()
            await pilot.click(rscr.query_one("#btn-totp-setup", Button))
            await pilot.pause(0.4)
            overlay = app.screen
            assert isinstance(overlay, TotpQrOverlay)
            secret: str = overlay.secret
            _svg(app, "block5_totp_overlay")

            # Dismiss → capsule sub-mode, no stale QR (e10e5a7 side fix)
            await pilot.press("escape")
            await pilot.pause(0.3)
            await pilot.click(rscr.query_one("#btn-p-capsule", Button))
            await pilot.pause(0.3)
            assert str(rscr.query_one("#panel-capsule").styles.display) == "block"
            assert str(rscr.query_one("#panel-totp").styles.display) == "none"
            for wid in ("#capsule-pw", "#capsule-pw-confirm", "#capsule-hint"):
                assert rscr.query_one(wid, Input) is not None
            for wid in ("#totp-output", "#qr-placeholder"):
                text = _text(rscr.query_one(wid, Static))
                assert not any(ch in text for ch in "▀▄█"), wid
            _svg(app, "block5_capsule")

            # Shamir sub-mode
            await pilot.click(rscr.query_one("#btn-p-shamir", Button))
            await pilot.pause(0.3)
            assert str(rscr.query_one("#panel-shamir").styles.display) == "block"
            assert rscr.query_one("#shamir-n", Input).value == "5"
            assert rscr.query_one("#shamir-k", Input).value == "3"
            assert rscr.query_one("#shamir-dir", Input) is not None
            _svg(app, "block5_shamir")
            return secret

    secret = asyncio.run(scenario())
    # The setup wrote the secret to the synthetic tmp vault, not ~/.nyxora
    store = VaultStore(CryptoEngine())
    store.open(synthetic.path, bytearray.fromhex(synthetic.key_hex))
    assert store.get_metadata_value("totp_secret") == secret
    store.close()


# ── BLOCK 6 — Updates (network mocked) ────────────────────────────


def test_block6_updates(
    synthetic: SyntheticCtx, monkeypatch: pytest.MonkeyPatch
) -> None:
    import nyxora.core.update_engine as update_engine

    # Deterministic, offline: pretend the latest release is v0.0.1
    monkeypatch.setattr(
        update_engine,
        "fetch_latest_release",
        lambda channel="stable": {"tag_name": "v0.0.1"},
    )
    monkeypatch.setattr(update_engine, "is_newer", lambda release: False)

    async def scenario() -> None:
        app = NyxoraApp(start_screen="updates", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            uscr = app.query_one(UpdatesScreen)
            assert "v" in _text(uscr.query_one("#ver-current", Static))
            assert uscr.query_one("#ver-latest", Static) is not None
            assert uscr.query_one("#btn-check", Button) is not None
            _svg(app, "block6_updates")

            await pilot.click(uscr.query_one("#btn-check", Button))
            await pilot.pause(0.4)
            result = _text(uscr.query_one("#update-result", Static))
            assert "up to date" in result
            assert "v0.0.1" in _text(uscr.query_one("#ver-latest", Static))
            _svg(app, "block6_checked")

    asyncio.run(scenario())


# ── BLOCK 7 — Generate ────────────────────────────────────────────


def test_block7_generate(
    synthetic: SyntheticCtx, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Stub pyperclip.copy — headless CI runners have no clipboard backend.
    import pyperclip

    copied: list[str] = []
    monkeypatch.setattr(pyperclip, "copy", copied.append)

    async def scenario() -> None:
        app = NyxoraApp(start_screen="generate", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            gscr = app.query_one(GenerateScreen)

            # Password mode: length + charset toggles honoured
            gscr.query_one("#gen-length", Input).value = "32"
            gscr.query_one("#chk-upper", Checkbox).value = False
            gscr.query_one("#chk-symbols", Checkbox).value = False
            await pilot.pause()
            await pilot.click(gscr.query_one("#btn-gen-pw", Button))
            await pilot.pause(0.2)
            pw = gscr._result
            assert len(pw) == 32
            assert all(c.islower() or c.isdigit() for c in pw)
            assert "bits" in _text(gscr.query_one("#gen-strength", Static))
            _svg(app, "block7_password")

            # Passphrase mode
            await pilot.click(gscr.query_one("#btn-mode-pp", Button))
            await pilot.pause(0.2)
            await pilot.click(gscr.query_one("#btn-gen-pp", Button))
            await pilot.pause(0.2)
            phrase = gscr._result
            assert len(phrase.split("-")) == 5  # 5 words, '-' separator
            _svg(app, "block7_passphrase")

            # Copy → no crash, toast confirms, stub got the passphrase
            await pilot.click(gscr.query_one("#btn-copy-gen", Button))
            await pilot.pause(0.3)
            assert any("Copied" in n for n in _notifications(app))
            assert copied == [phrase]
            _svg(app, "block7_copy")

    asyncio.run(scenario())


# ── BLOCK 8 — Security analyser ───────────────────────────────────


def test_block8_security(synthetic: SyntheticCtx) -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="security", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            sscr = app.query_one(SecurityScreen)
            inp = sscr.query_one("#sec-input", Input)
            inp.focus()
            await pilot.pause()

            # Weak: "password" = 8 lowercase → 37 bits, grade D
            await pilot.press(*"password")
            await pilot.pause(0.2)
            result = _text(sscr.query_one("#sec-result", Static))
            assert "37 bits" in result
            assert "Grade" in result
            assert "Weak" in result
            _svg(app, "block8_weak")

            # Strong: 24 chars over the full charset → 157 bits, A+
            inp.value = "Xk9#mQ2$vL8@wR5!zT3%nB7&"
            await pilot.pause(0.2)
            result = _text(sscr.query_one("#sec-result", Static))
            assert "157 bits" in result
            assert "A+" in result
            assert "Excellent" in result
            _svg(app, "block8_strong")

            # Show/hide toggle flips the Input's password masking
            assert inp.password is True
            await pilot.click(sscr.query_one("#btn-toggle-pw", Button))
            await pilot.pause(0.2)
            assert inp.password is False
            _svg(app, "block8_showhide")
            await pilot.click(sscr.query_one("#btn-toggle-pw", Button))
            await pilot.pause(0.2)
            assert inp.password is True

    asyncio.run(scenario())


# ── BLOCK 9 — Navigation ──────────────────────────────────────────


def test_block9_navigation_and_help(synthetic: SyntheticCtx) -> None:
    async def scenario() -> None:
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            switcher = app.query_one("#workspace", ContentSwitcher)
            expected = {
                "1": "screen-vault",
                "2": "screen-manage",
                "3": "screen-backup",
                "4": "screen-recovery",
                "5": "screen-updates",
                "6": "screen-generate",
                "7": "screen-security",
            }
            for key, target in expected.items():
                if isinstance(app.focused, Input):
                    app.set_focus(None)
                await pilot.press(key)
                await pilot.pause(0.25)
                assert switcher.current == target, key
                _svg(app, f"block9_nav_{target.removeprefix('screen-')}")

            if isinstance(app.focused, Input):
                app.set_focus(None)
            await pilot.press("?")
            await pilot.pause(0.3)
            assert any("Keybindings" in n for n in _notifications(app))
            _svg(app, "block9_help")
            await pilot.press("escape")

    asyncio.run(scenario())


def test_block9_overlay_binding_suppression(synthetic: SyntheticCtx) -> None:
    """Regression guard for 5fbdb4c: digits must not nav under overlays."""
    async def scenario() -> None:
        app = NyxoraApp(start_screen="manage", exe_mode=False)
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause(0.4)
            switcher = app.query_one("#workspace", ContentSwitcher)
            app.push_screen(TotpQrOverlay(
                secret="ABCDEF234567",
                account_label="test@example.com",
            ))
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            assert isinstance(app.screen, TotpQrOverlay)
            assert switcher.current == "screen-manage"
            _svg(app, "block9_overlay_suppressed")

            await pilot.press("escape")
            await pilot.pause()
            if isinstance(app.focused, Input):
                app.set_focus(None)
            await pilot.press("3")
            await pilot.pause(0.25)
            assert switcher.current == "screen-backup"

    asyncio.run(scenario())
