from unittest.mock import MagicMock, patch

from nyxora.cli.commands import backup, locker, vault
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.intel_engine import IntelEngine


def test_intel_direct():
    engine = CryptoEngine()
    intel = IntelEngine(engine)

    with patch("httpx.Client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "00000000000000000000000000000000000:5\r\n"
        mock_client.return_value.__enter__.return_value.get.return_value = mock_resp

        intel.check_breach_hibp("password123")
        intel.audit_all([("1", "t", "password123")], check_hibp=True)

    with patch("httpx.Client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_client.return_value.__enter__.return_value.get.return_value = mock_resp
        intel.check_breach_hibp("password123")

    # hit real intel methods
    intel.score_entropy("password123")
    intel.classify_strength(50.0)
    intel.scan_patterns("qwerty")
    intel.detect_duplicates([("1", "pw"), ("2", "pw")])
    intel.generate_reuse_heatmap([("1", "pw"), ("2", "pw")])

def test_backup_direct(tmp_path):
    with patch("nyxora.cli.commands.backup._open_vault") as m_open:
        store = MagicMock()
        m_open.return_value = (store, bytearray(32), tmp_path / "v.vault")

        # export plaintext
        store.list_entries.return_value = [MagicMock(title="T", password="P", tags=["tag1"], username="u", url="", notes="", custom=None, id="id")]
        with patch("questionary.confirm") as m_conf, patch("questionary.text") as m_text:
            m_conf.return_value.ask.return_value = True
            m_text.return_value.ask.return_value = "CONFIRM"
            backup.export(tmp_path / "exp.csv", plaintext=True)

        # export encrypted
        with patch("questionary.password") as m_pass:
            m_pass.return_value.ask.side_effect = ["pw", "pw"]
            backup.export(tmp_path / "exp.nyx", plaintext=False)

def test_backup_more_direct(tmp_path):
    import typer
    with patch("nyxora.cli.commands.backup._open_vault") as m_open:
        store = MagicMock()
        m_open.return_value = (store, bytearray(32), tmp_path / "v.vault")
        (tmp_path / "v.vault").write_text("stub_data")

        # test list empty
        backup.list_backups(tmp_path)

        # test create
        with patch("nyxora.cli.commands.backup.ui"):
            backup.create(tmp_path, "note")

        # test list with items
        backup.list_backups(tmp_path)

        # test verify nonexistent
        try:
            backup.verify(tmp_path / "nope.bak")
        except typer.Exit:
            pass

        # test verify fail exit
        f = tmp_path / "fake.bak"
        f.write_text("fake")
        try:
            backup.verify(f)
        except typer.Exit:
            pass

def test_vault_health(tmp_path):
    with patch("nyxora.cli.commands.vault.load_session") as m_load:
        (tmp_path / "v.vault").write_text("stub")
        m_load.return_value = ("id", tmp_path / "v.vault", bytearray(32))
        with patch("nyxora.cli.commands.vault.VaultStore"), patch("nyxora.cli.commands.vault.ui"):
            vault.health_check()

def test_locker_direct(tmp_path):
    with patch("nyxora.cli.commands.locker.load_session") as m_load:
        m_load.return_value = ("id", tmp_path / "v.vault", bytearray(32))

        f = tmp_path / "test.txt"
        f.write_text("hello foo")
        locker.encrypt(f, output=None, delete_original=False)
        enc = list(tmp_path.glob("*.nyx"))[0]
        locker.decrypt(enc, output=None)

def test_intel_offline(tmp_path):
    engine = CryptoEngine()
    intel = IntelEngine(engine)

    db_file = tmp_path / "offline.txt"
    db_file.write_text("5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8:5\n")
    intel.import_offline_breach_db(db_file)
    intel.check_breach_offline("password")

def test_memory_guard_direct(tmp_path):
    from nyxora.core.memory_guard import secure_allocate, secure_buffer, try_mlock, try_munlock

    b = secure_allocate(16)
    assert len(b) == 16

    try_mlock(b)
    try_munlock(b)

    with secure_buffer(16) as buf:
        assert len(buf) == 16


def test_locker_shred_direct(tmp_path):
    import nyxora.cli.commands.locker as locker
    path = tmp_path / "dummy_shred.txt"
    path.write_text("X" * 1024 * 1024 * 5)  # 5 MB file to trigger chunk paths
    locker._shred_file(path)
    assert not path.exists()

def test_backup_export_cancel(tmp_path):
    from typer.testing import CliRunner
    from nyxora.cli.commands.backup import app
    runner = CliRunner()
    out = tmp_path / "out.csv"
    with patch("nyxora.cli.commands.backup.load_session") as ms, \
         patch("nyxora.cli.commands.backup.danger_panel"), \
         patch("questionary.confirm") as mc:
        ms.return_value = ("sid", tmp_path / "v.nyx", bytearray(32))
        mc.return_value.ask.return_value = False
        result = runner.invoke(app, ["export", str(out), "--plaintext"])
    assert result.exit_code == 0


def test_helpers_direct(tmp_path):
    from unittest.mock import MagicMock

    import nyxora.cli.helpers as h

    mock_kr = MagicMock()
    mock_kr.get_password.return_value = "deadbeef"

    with patch("nyxora.cli.helpers.SESSION_FILE", tmp_path / "sess.json"), patch("nyxora.cli.helpers.keyring", mock_kr):
        h.save_session("test_id", "/some/path", "deadbeef")
        mock_kr.get_password.return_value = "deadbeef"
        data = h.load_session()
        assert data is not None
        h.clear_session()

        # Test clear session with empty file
        (tmp_path / "sess.json").write_text("{}")
        h.clear_session()

        # Test load session empty keyring
        (tmp_path / "sess.json").write_text("{\"session_id\": \"id\", \"vault_path\": \"\"}")
        mock_kr.get_password.return_value = None
        assert h.load_session() is None
        assert h.load_session() is None


def test_import_parsers(tmp_path):
    import csv as csv_mod
    from nyxora.cli.commands.import_ import (
        _parse_csv, _parse_nyxora_json, _parse_bitwarden,
        _parse_1password, _detect_format,
    )
    import orjson

    # CSV parser
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "title,username,password,url,notes\n"
        "GitHub,alice,gh-token,https://github.com,work\n"
        "Gmail,bob,gm-pass,,\n"
    )
    entries = _parse_csv(csv_file)
    assert len(entries) == 2
    assert entries[0]["title"] == "GitHub"
    assert entries[0]["password"] == "gh-token"
    assert entries[1]["title"] == "Gmail"

    # _detect_format — CSV by extension
    assert _detect_format(csv_file) == "csv"

    # _detect_format — JSON by extension
    json_file = tmp_path / "export.json"
    json_file.write_bytes(orjson.dumps([{"title": "t", "password": "p"}]))
    assert _detect_format(json_file) == "json"

    # _detect_format — Bitwarden by content
    bw_file = tmp_path / "bw.json"
    bw_file.write_bytes(orjson.dumps({
        "items": [], "folders": []
    }))
    assert _detect_format(bw_file) == "bitwarden"

    # Nyxora JSON parser — list format
    entries2 = _parse_nyxora_json(json_file)
    assert len(entries2) == 1
    assert entries2[0]["title"] == "t"

    # Nyxora JSON parser — dict with "entries" key
    json_file2 = tmp_path / "export2.json"
    json_file2.write_bytes(orjson.dumps(
        {"entries": [{"title": "X", "password": "y"}]}
    ))
    entries3 = _parse_nyxora_json(json_file2)
    assert len(entries3) == 1

    # Bitwarden parser
    bw_data_file = tmp_path / "bw_data.json"
    bw_data_file.write_bytes(orjson.dumps({
        "items": [
            {
                "type": 1,
                "name": "BW Entry",
                "login": {
                    "username": "bwuser",
                    "password": "bwpass",
                    "uris": [{"uri": "https://example.com"}]
                },
                "notes": "bw note",
                "folderId": None,
            },
            {"type": 2, "name": "Card", "notes": ""},  # non-login, skipped
        ],
        "folders": []
    }))
    bw_entries = _parse_bitwarden(bw_data_file)
    assert len(bw_entries) == 1
    assert bw_entries[0]["title"] == "BW Entry"
    assert bw_entries[0]["username"] == "bwuser"

    # 1Password parser (delegates to CSV)
    assert _parse_1password(csv_file) == _parse_csv(csv_file)


def test_generate_min_strength(tmp_path):
    from typer.testing import CliRunner
    from nyxora.cli.commands.generate import app
    runner = CliRunner()
    # --min-strength with a short low-entropy alphabet should trigger the
    # warning panel after 10 attempts
    result = runner.invoke(app, [
        "password", "--length", "4", "--no-symbols",
        "--no-digits", "--no-upper", "--min-strength", "excellent"
    ])
    # Should either meet the threshold or print the warning — either way
    # the command must not crash
    assert result.exit_code == 0


def test_secret_custom_and_tags():
    from unittest.mock import patch, MagicMock
    from typer.testing import CliRunner
    from nyxora.cli.commands.secret import app

    runner = CliRunner()
    mock_store = MagicMock()
    mock_store.add_entry.return_value = "test-id-1234"

    with patch("nyxora.cli.commands.secret.open_vault") as mv, \
         patch("nyxora.cli.commands.secret.wipe_memory"), \
         patch("questionary.text") as qt, \
         patch("questionary.password") as qp, \
         patch("questionary.confirm") as qc:
        mv.return_value = (mock_store, "sid", bytearray(32), None)
        qt.return_value.ask.return_value = "My Entry"
        qp.return_value.ask.return_value = "mypassword"
        qc.return_value.ask.return_value = False  # no questionary confirm

        result = runner.invoke(app, [
            "add", "--title", "TestEntry", "--custom", "pin=1234,token=abc"
        ])
        assert result.exit_code == 0
        call_kwargs = mock_store.add_entry.call_args[1]
        assert call_kwargs.get("custom") == {"pin": "1234", "token": "abc"}
