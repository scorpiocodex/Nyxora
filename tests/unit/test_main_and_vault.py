from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from nyxora.cli.main import app, cli_main, version_callback

runner = CliRunner()

def test_main_cli_exception_handling():
    # Test typer.Exit pass-through
    with patch("nyxora.cli.main.app", side_effect=SystemExit(0)):
        try:
            cli_main()
        except SystemExit:
            pass

    # Test NyxoraError
    from nyxora.utils.exceptions import VaultError
    with patch("nyxora.cli.main.app") as mock_app:
        # Mock exceptions
        mock_app.side_effect = VaultError("test vault error")
        with patch("nyxora.cli.ui.error_panel") as m_panel:
            try:
                cli_main()
            except SystemExit:
                pass
            m_panel.assert_called_once()

    # Test version callback
    import typer
    with pytest.raises(typer.Exit):
        version_callback(True)


def test_main_cli_generic_exception_exits_1():
    """A non-NyxoraError bubbling out of app() flows through the generic
    handler: an error panel is shown and the process exits with code 1
    (distinct from the NyxoraError path, which uses the error's own code)."""
    import os

    with patch("nyxora.cli.main.app", side_effect=RuntimeError("boom")), \
         patch.dict(os.environ, {"NYX_DEBUG": "1"}), \
         patch("nyxora.cli.ui.error_panel") as m_panel:
        with pytest.raises(SystemExit) as exc_info:
            cli_main()
    assert exc_info.value.code == 1
    m_panel.assert_called_once()

@patch("nyxora.cli.commands.vault.load_session")
@patch("nyxora.cli.commands.vault.ui")
def test_vault_commands_extra(m_ui, m_load, tmp_path):
    runner.invoke(app, ["vault", "status"])
    runner.invoke(app, ["vault", "lock"])

    with patch("nyxora.cli.commands.vault.clear_session") as m_clear:
        runner.invoke(app, ["vault", "panic"])
        m_clear.assert_called()

    m_load.return_value = ("sess", tmp_path / "v.nyx", bytearray(b"key"))
    runner.invoke(app, ["vault", "status"])
    runner.invoke(app, ["vault", "lock"])
    runner.invoke(app, ["vault", "health-check"])
