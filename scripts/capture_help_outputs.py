import os
from pathlib import Path
from typer.testing import CliRunner
from nyxora.cli.main import app

runner = CliRunner()

COMMANDS = [
    [],
    ["vault"], ["vault", "unlock"], ["vault", "init"], ["vault", "lock"], ["vault", "panic"], ["vault", "status"], ["vault", "health-check"], ["vault", "change-password"],
    ["secret"], ["secret", "add"], ["secret", "list"], ["secret", "get"], ["secret", "update"], ["secret", "delete"], ["secret", "search"], ["secret", "clone"],
    ["generate"], ["generate", "password"], ["generate", "passphrase"], ["generate", "api-key"], ["generate", "ssh-key"], ["generate", "entropy"],
    ["security"], ["security", "audit"], ["security", "stats"], ["security", "log"], ["security", "forensic"], ["security", "breach-scan"],
    ["backup"], ["backup", "create"], ["backup", "list"], ["backup", "restore"], ["backup", "cleanup"], ["backup", "verify"], ["backup", "export"],
    ["recovery"], ["recovery", "setup"], ["recovery", "create-capsule"], ["recovery", "restore-capsule"], ["recovery", "split-secret"], ["recovery", "status"],
    ["locker"], ["locker", "encrypt"], ["locker", "decrypt"], ["locker", "list"], ["locker", "shred"],
]

def main():
    report = ["# Nyxora CLI Help Output Report\n\n"]
    
    success = True
    for cmd in COMMANDS:
        args = cmd + ["--help"]
        cmd_str = "nyx " + " ".join(args)
        
        result = runner.invoke(app, args)
        
        status = "✅ PASS" if result.exit_code == 0 else f"❌ FAIL ({result.exit_code})"
        if result.exit_code != 0:
            success = False
            
        report.append(f"## {cmd_str.strip()} ({status})\n")
        report.append("```console\n")
        report.append(f"$ {cmd_str.strip()}\n")
        
        if result.stdout:
            report.append(result.stdout.strip() + "\n")
        report.append("```\n\n")

    out_file = Path("docs/help_output_report.md")
    out_file.parent.mkdir(exist_ok=True)
    out_file.write_text("".join(report), encoding="utf-8")
    
    print(f"Help output test complete. All passed: {success}. Report saved to {out_file}.")
    if not success:
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
