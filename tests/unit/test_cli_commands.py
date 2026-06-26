"""Behavioral CLI tests over a real, session-backed vault.

These replace the former ``test_massive_coverage_shotgun`` — a single test that
fired ~30 ``runner.invoke`` calls with one real assertion, executing code paths
purely to inflate the coverage percentage (#33, the second instance of the
coverage-theater pattern #10 removed).

The valuable thing the shotgun did — and the reason a straight delete would drop
honest coverage below the gate — was driving the vault / secret / security /
backup / recovery commands end-to-end against a *genuine* vault (real
``CryptoEngine`` + ``VaultStore``) reached through an in-memory session, rather
than the heavily-mocked stand-ins in ``test_interactive_mocks``. These tests keep
that real-session coverage but assert exit codes, command output, and on-disk /
in-store state at every step, so each one fails on a real regression.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nyxora.cli.main import app
from nyxora.cli.ui import set_json_mode

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_json_mode():
    """``--json`` flips a module-level global that is never reset to False;
    isolate every test from leakage by clearing it before and after."""
    set_json_mode(False)
    yield
    set_json_mode(False)


@pytest.fixture
def session(tmp_path):
    """An initialized, unlocked vault backed by an in-memory session.

    Only the session save/load/clear handlers are patched (everywhere they are
    imported) with shared in-memory state; a real ``vault init`` then runs, so
    every command under test operates on a genuine on-disk vault through a real
    authenticated session.
    """
    state: dict[str, str] = {}

    def m_save(command: str, vpath: str, root_key_hex: str) -> None:
        state["path"] = vpath
        state["key"] = root_key_hex

    def m_load():
        if not state:
            return None
        return (str(uuid.uuid4()), Path(state["path"]), bytearray.fromhex(state["key"]))

    def m_clear() -> None:
        state.clear()

    # ``backup`` and ``recovery`` import ``load_session`` directly into their own
    # namespace, so patching only ``helpers``/``vault`` (as the old shotgun did)
    # left them hitting the locked-vault guard — which is exactly why the shotgun
    # never actually exercised those command bodies. Patch the direct bindings too
    # so the session is genuinely live for them. (secret/security reach the vault
    # via ``helpers.open_vault``, which resolves ``load_session`` in the helpers
    # namespace, so the helpers patch covers them.)
    with patch("nyxora.cli.commands.vault.save_session", side_effect=m_save), \
         patch("nyxora.cli.commands.vault.load_session", side_effect=m_load), \
         patch("nyxora.cli.commands.vault.clear_session", side_effect=m_clear), \
         patch("nyxora.cli.commands.backup.load_session", side_effect=m_load), \
         patch("nyxora.cli.commands.recovery.load_session", side_effect=m_load), \
         patch("nyxora.cli.helpers.save_session", side_effect=m_save), \
         patch("nyxora.cli.helpers.load_session", side_effect=m_load), \
         patch("nyxora.cli.helpers.clear_session", side_effect=m_clear):
        vault_file = tmp_path / "test.vault"
        with patch("questionary.password") as m_pass:
            m_pass.return_value.ask.side_effect = ["masterpw1", "masterpw1"]
            res = runner.invoke(app, ["vault", "init", "--vault", str(vault_file)])
        assert res.exit_code == 0, res.output
        # init really produced a vault + salt and saved the session
        assert vault_file.exists()
        assert vault_file.with_suffix(".salt").exists()
        assert state.get("path") == str(vault_file)
        yield {"state": state, "vault_file": vault_file, "tmp_path": tmp_path}


def _json(output: str):
    """Parse the JSON object/array a ``--json`` command writes to stdout."""
    text = output.strip()
    return json.loads(text)


def _add_secret(title: str, username: str, password: str = "supersecretpw123") -> str:
    """Add an entry via the CLI and return its parsed ID."""
    with patch("questionary.password") as m_pass, patch("questionary.text") as m_text:
        m_pass.return_value.ask.return_value = password
        m_text.return_value.ask.return_value = ""
        res = runner.invoke(
            app, ["secret", "add", "--title", title, "--username", username]
        )
    assert res.exit_code == 0, res.output
    match = re.search(r"ID:\s*([0-9a-fA-F][0-9a-fA-F-]+)", res.output)
    assert match, f"no entry ID in add output:\n{res.output}"
    return match.group(1)


def test_vault_status_reports_real_state_and_lock_wipes_session(session):
    res = runner.invoke(app, ["--json", "vault", "status"])
    assert res.exit_code == 0, res.output
    data = _json(res.output)
    assert data["locked"] is False
    assert data["entry_count"] == 0
    assert data["vault_path"] == str(session["vault_file"])

    # lock must actually clear the (in-memory) session
    res = runner.invoke(app, ["vault", "lock"])
    assert res.exit_code == 0, res.output
    assert session["state"] == {}


def test_secret_add_get_list_search_delete_roundtrip(session):
    eid = _add_secret("My Email", "u@e.com", password="hunter2pw!")

    # get returns the entry we stored, password and all
    res = runner.invoke(app, ["--json", "secret", "get", eid])
    assert res.exit_code == 0, res.output
    rec = _json(res.output)
    assert rec["title"] == "My Email"
    assert rec["username"] == "u@e.com"
    assert rec["password"] == "hunter2pw!"

    # a second entry, then list reflects exactly the two
    eid2 = _add_secret("Bank", "acct@bank.com")
    res = runner.invoke(app, ["--json", "secret", "list"])
    assert res.exit_code == 0, res.output
    titles = {e["title"] for e in _json(res.output)}
    assert titles == {"My Email", "Bank"}

    # search narrows to the matching entry
    res = runner.invoke(app, ["--json", "secret", "search", "Bank"])
    assert res.exit_code == 0, res.output
    found = _json(res.output)
    assert [e["id"] for e in found] == [eid2]

    # delete removes only the targeted entry
    res = runner.invoke(app, ["secret", "delete", eid, "--yes"])
    assert res.exit_code == 0, res.output
    res = runner.invoke(app, ["--json", "secret", "list"])
    assert res.exit_code == 0, res.output
    remaining = {e["title"] for e in _json(res.output)}
    assert remaining == {"Bank"}


def test_secret_get_renders_richly_and_resolves_by_title(session):
    eid = _add_secret("Personal Mail", "me@home.com", password="richpw1")

    # default (non-JSON) get renders the entry through the rich panels
    res = runner.invoke(app, ["secret", "get", eid])
    assert res.exit_code == 0, res.output
    assert "Personal Mail" in res.output
    assert "richpw1" in res.output

    # an unknown ID falls back to a title search and still resolves the entry
    res = runner.invoke(app, ["--json", "secret", "get", "Personal Mail"])
    assert res.exit_code == 0, res.output
    assert _json(res.output)["id"] == eid


def test_secret_update_persists_changed_fields(session):
    eid = _add_secret("Old Title", "olduser")

    with patch("typer.confirm", return_value=False):  # don't prompt for a password
        res = runner.invoke(
            app,
            [
                "secret", "update", eid,
                "--title", "New Title",
                "--username", "newuser",
                "--url", "https://new.example",
                "--notes", "updated notes",
                "--tags", "alpha,beta",
            ],
        )
    assert res.exit_code == 0, res.output

    res = runner.invoke(app, ["--json", "secret", "get", eid])
    assert res.exit_code == 0, res.output
    rec = _json(res.output)
    assert rec["title"] == "New Title"
    assert rec["username"] == "newuser"
    assert rec["url"] == "https://new.example"
    assert rec["notes"] == "updated notes"
    assert set(rec["tags"]) == {"alpha", "beta"}


def test_security_audit_stats_log_forensic_breach_scan(session):
    # a deliberately weak password so the audit has something to flag
    _add_secret("Weak", "user", password="123")

    res = runner.invoke(app, ["security", "audit", "--no-hibp"])
    assert res.exit_code == 0, res.output

    res = runner.invoke(app, ["security", "stats"])
    assert res.exit_code == 0, res.output
    assert "Total entries" in res.output

    res = runner.invoke(app, ["security", "log"])
    assert res.exit_code == 0, res.output

    res = runner.invoke(app, ["security", "forensic"])
    assert res.exit_code == 0, res.output

    # keep the breach scan offline + deterministic
    with patch(
        "nyxora.core.intel_engine.IntelEngine.check_breach_hibp",
        return_value=(False, 0),
    ):
        res = runner.invoke(app, ["security", "breach-scan"])
    assert res.exit_code == 0, res.output
    assert "No breached passwords" in res.output


def test_backup_create_list_verify_restore_cleanup(session):
    _add_secret("ToBackUp", "user")
    bdir = session["tmp_path"] / "backups"

    res = runner.invoke(app, ["backup", "create", "--dir", str(bdir), "--note", "t"])
    assert res.exit_code == 0, res.output
    baks = list(bdir.glob("*.nyx.bak"))
    assert len(baks) == 1, f"expected one backup file, got {baks}"

    res = runner.invoke(app, ["backup", "list", "--dir", str(bdir)])
    assert res.exit_code == 0, res.output

    res = runner.invoke(app, ["backup", "verify", str(baks[0])])
    assert res.exit_code == 0, res.output
    assert "valid" in res.output

    res = runner.invoke(app, ["backup", "restore", str(baks[0])])
    assert res.exit_code == 0, res.output
    # restore rewrote the live vault from the backup
    assert session["vault_file"].exists()

    res = runner.invoke(app, ["backup", "cleanup", "--dir", str(bdir), "--keep", "1"])
    assert res.exit_code == 0, res.output


def test_backup_export_plaintext_and_encrypted(session):
    _add_secret("Exported", "user", password="exportpw1")
    tmp = session["tmp_path"]

    csv_path = tmp / "export.csv"
    with patch("questionary.confirm") as m_conf, patch("questionary.text") as m_text:
        m_conf.return_value.ask.return_value = True
        m_text.return_value.ask.return_value = "CONFIRM"
        res = runner.invoke(
            app, ["backup", "export", str(csv_path), "--plaintext"]
        )
    assert res.exit_code == 0, res.output
    assert csv_path.exists()
    body = csv_path.read_text(encoding="utf-8")
    assert "Exported" in body and "exportpw1" in body  # plaintext really written

    nyx_path = tmp / "export.nyx"
    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.side_effect = ["exppw", "exppw"]
        res = runner.invoke(app, ["backup", "export", str(nyx_path)])
    assert res.exit_code == 0, res.output
    assert nyx_path.exists()
    # encrypted export must NOT contain the plaintext password
    assert b"exportpw1" not in nyx_path.read_bytes()


def test_recovery_capsule_roundtrip_split_and_status(session):
    tmp = session["tmp_path"]
    capsule = tmp / "rec.capsule"

    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.side_effect = ["capsulepw1", "capsulepw1"]
        res = runner.invoke(app, ["recovery", "create-capsule", str(capsule)])
    assert res.exit_code == 0, res.output
    assert capsule.exists()

    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.return_value = "capsulepw1"
        res = runner.invoke(app, ["recovery", "restore-capsule", str(capsule)])
    assert res.exit_code == 0, res.output
    assert "recovered" in res.output.lower()

    # a wrong capsule password must fail, not silently "succeed"
    with patch("questionary.password") as m_pass:
        m_pass.return_value.ask.return_value = "wrong-password"
        res = runner.invoke(app, ["recovery", "restore-capsule", str(capsule)])
    assert res.exit_code == 1

    sdir = tmp / "shares"
    res = runner.invoke(
        app,
        ["recovery", "split-secret", "--shares", "3", "--threshold", "2", "-o", str(sdir)],
    )
    assert res.exit_code == 0, res.output
    assert len(list(sdir.glob("share_*_of_3.bin"))) == 3

    res = runner.invoke(app, ["recovery", "status"])
    assert res.exit_code == 0, res.output
