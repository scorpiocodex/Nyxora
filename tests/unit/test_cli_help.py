import pytest
from typer.testing import CliRunner

from nyxora.cli.main import app

COMMANDS = [
    [], ["vault"], ["vault", "unlock"], ["vault", "init"], ["vault", "lock"], ["vault", "panic"], ["vault", "status"], ["vault", "health-check"], ["vault", "change-password"],
    ["secret"], ["secret", "add"], ["secret", "list"], ["secret", "get"], ["secret", "update"], ["secret", "delete"], ["secret", "search"], ["secret", "clone"],
    ["generate"], ["generate", "password"], ["generate", "passphrase"], ["generate", "api-key"], ["generate", "ssh-key"], ["generate", "entropy"],
    ["security"], ["security", "audit"], ["security", "stats"], ["security", "log"], ["security", "forensic"], ["security", "breach-scan"],
    ["backup"], ["backup", "create"], ["backup", "list"], ["backup", "restore"], ["backup", "cleanup"], ["backup", "verify"], ["backup", "export"],
    ["recovery"], ["recovery", "setup"], ["recovery", "create-capsule"], ["recovery", "restore-capsule"], ["recovery", "split-secret"], ["recovery", "status"],
    ["locker"], ["locker", "encrypt"], ["locker", "decrypt"], ["locker", "list"], ["locker", "shred"]
]

runner = CliRunner()

@pytest.mark.parametrize("cmd", COMMANDS)
def test_cli_help_output(cmd):
    """Ensure all subcommands render help successfully with exit code 0."""
    args = cmd + ["--help"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, f"Command '{' '.join(args)}' failed to render help."
