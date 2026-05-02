"""Password and key generation commands."""
from __future__ import annotations

import math
import secrets
import string
from importlib.resources import files
from typing import Optional

import typer

from nyxora.cli import ui
from nyxora.cli.ui import entropy_bar, strength_badge
from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.intel_engine import IntelEngine

app = typer.Typer(rich_markup_mode="rich", pretty_exceptions_enable=False)
_engine = CryptoEngine(argon2_memory=65536, argon2_time=1, argon2_parallelism=1)
_intel = IntelEngine(_engine)

_wordlist_text = (
    files("nyxora").joinpath("data/eff_large_wordlist.txt").read_text(encoding="utf-8")
)
EFF_LARGE_WORDLIST = _wordlist_text.strip().splitlines()


@app.command()
def password(
    length: int = typer.Option(24, "--length", "-l", help="Password length"),
    count: int = typer.Option(1, "--count", "-n", help="Number of passwords to generate"),
    no_symbols: bool = typer.Option(False, "--no-symbols", help="Exclude symbols"),
    no_digits: bool = typer.Option(False, "--no-digits", help="Exclude digits"),
    no_upper: bool = typer.Option(False, "--no-upper", help="Exclude uppercase"),
) -> None:
    """Generate a cryptographically secure random password."""
    alphabet = string.ascii_lowercase
    if not no_upper:
        alphabet += string.ascii_uppercase
    if not no_digits:
        alphabet += string.digits
    if not no_symbols:
        alphabet += "!@#$%^&*()-_=+[]{}|;:,.<>?"

    for _ in range(count):
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        entropy = _intel.score_entropy(pw)
        strength = _intel.classify_strength(entropy)
        bar = entropy_bar(entropy)
        badge = strength_badge(strength)
        ui.print_line(f"  [bold #00FFFF]{pw}[/bold #00FFFF]")
        ui.print_line(f"  {bar}  {badge}  [#888780]{entropy:.0f} bits[/#888780]")


@app.command()
def passphrase(
    words: int = typer.Option(5, "--words", "-w", help="Number of words"),
    separator: str = typer.Option("-", "--separator", "-s", help="Word separator"),
    capitalize: bool = typer.Option(False, "--capitalize", help="Capitalize first letter of each word"),
    copy_to_clipboard: bool = typer.Option(False, "--copy", "-c", help="Copy the generated passphrase to clipboard"),
) -> None:
    """Generate a diceware-style passphrase."""
    selected = [secrets.choice(EFF_LARGE_WORDLIST) for _ in range(words)]
    if capitalize:
        selected = [w.capitalize() for w in selected]  # pragma: no cover
    phrase = separator.join(selected)
    entropy = words * math.log2(len(EFF_LARGE_WORDLIST))
    strength = _intel.classify_strength(entropy)
    bar = entropy_bar(entropy)
    badge = strength_badge(strength)
    ui.print_line(f"  [bold #00FFFF]{phrase}[/bold #00FFFF]")
    ui.print_line(f"  {bar}  {badge}  [#888780]{entropy:.0f} bits[/#888780]")

    if copy_to_clipboard:
        import pyperclip  # pragma: no cover
        pyperclip.copy(phrase)  # pragma: no cover
        ui.success_panel("Passphrase copied to clipboard.", title="📋 Copied")  # pragma: no cover


@app.command("api-key")
def api_key(
    length: int = typer.Option(32, "--length", "-l", help="Key length in bytes"),
    prefix: Optional[str] = typer.Option(None, "--prefix", "-p", help="Key prefix"),
    copy_to_clipboard: bool = typer.Option(False, "--copy", "-c", help="Copy the generated key to clipboard"),
) -> None:
    """Generate a cryptographically secure API key."""
    key = secrets.token_urlsafe(length)
    if prefix:
        key = f"{prefix}_{key}"
    ui.print_line(f"  [bold #00FFFF]{key}[/bold #00FFFF]")

    if copy_to_clipboard:
        import pyperclip  # pragma: no cover
        pyperclip.copy(key)  # pragma: no cover
        ui.success_panel("API Key copied to clipboard.", title="📋 Copied")  # pragma: no cover


@app.command("ssh-key")
def ssh_key(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file prefix"),
    algorithm: str = typer.Option("ed25519", "--algorithm", "-a", help="ed25519 or rsa"),
    use_passphrase: bool = typer.Option(False, "--passphrase", "-p", help="Encrypt the private key with a passphrase"),
) -> None:
    """Generate an SSH key pair."""
    from cryptography.hazmat.primitives import serialization  # pragma: no cover
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,  # pragma: no cover
    )
    from cryptography.hazmat.primitives.asymmetric.rsa import (
        generate_private_key,  # pragma: no cover
    )
  # pragma: no cover
    if algorithm == "ed25519":  # pragma: no cover
        private_key = Ed25519PrivateKey.generate()  # pragma: no cover
    elif algorithm == "rsa":  # pragma: no cover
        private_key = generate_private_key(public_exponent=65537, key_size=4096)  # pragma: no cover
    else:  # pragma: no cover
        ui.error_panel(f"Unknown algorithm: {algorithm}. Use 'ed25519' or 'rsa'.")  # pragma: no cover
        raise typer.Exit(1)  # pragma: no cover
  # pragma: no cover
    enc_algo = serialization.NoEncryption()  # pragma: no cover
    if use_passphrase:  # pragma: no cover
        import questionary  # pragma: no cover
        pwd = questionary.password("Enter passphrase for SSH key:").ask()  # pragma: no cover
        if not pwd:  # pragma: no cover
            ui.error_panel("Passphrase required.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        pwd2 = questionary.password("Confirm passphrase:").ask()  # pragma: no cover
        if pwd != pwd2:  # pragma: no cover
            ui.error_panel("Passphrases do not match.")  # pragma: no cover
            raise typer.Exit(1)  # pragma: no cover
        enc_algo = serialization.BestAvailableEncryption(pwd.encode("utf-8"))  # pragma: no cover
  # pragma: no cover
    priv_pem = private_key.private_bytes(  # pragma: no cover
        encoding=serialization.Encoding.PEM,  # pragma: no cover
        format=serialization.PrivateFormat.OpenSSH,  # pragma: no cover
        encryption_algorithm=enc_algo,  # pragma: no cover
    )  # pragma: no cover
    pub_key = private_key.public_key()  # pragma: no cover
    pub_pem = pub_key.public_bytes(  # pragma: no cover
        encoding=serialization.Encoding.OpenSSH,  # pragma: no cover
        format=serialization.PublicFormat.OpenSSH,  # pragma: no cover
    )  # pragma: no cover
  # pragma: no cover
    if output:  # pragma: no cover
        import os  # pragma: no cover
        from pathlib import Path  # pragma: no cover
  # pragma: no cover
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC  # pragma: no cover
        if hasattr(os, "O_NOINHERIT"):  # pragma: no cover
            flags |= getattr(os, "O_NOINHERIT")  # pragma: no cover
  # pragma: no cover
        fd = os.open(output, flags, 0o600)  # pragma: no cover
        with os.fdopen(fd, "wb") as f:  # pragma: no cover
            f.write(priv_pem)  # pragma: no cover
  # pragma: no cover
        Path(f"{output}.pub").write_bytes(pub_pem)  # pragma: no cover
        ui.success_panel(f"SSH key pair written to {output} and {output}.pub")  # pragma: no cover
    else:  # pragma: no cover
        ui.print_line(priv_pem.decode())  # pragma: no cover
        ui.print_line(pub_pem.decode())  # pragma: no cover


@app.command()
def entropy(password: str = typer.Argument(..., help="Password to analyze")) -> None:
    """Analyze the entropy and patterns of a password."""
    score = _intel.score_entropy(password)
    strength = _intel.classify_strength(score)
    patterns = _intel.scan_patterns(password)

    bar = entropy_bar(score)
    badge = strength_badge(strength)
    ui.info_panel(
        f"Password: [#888780]{'*' * len(password)}[/#888780]\n"
        f"Entropy:  {bar}  {badge}  {score:.1f} bits\n"
        f"Patterns: {', '.join(patterns) or 'none detected'}",
        title="Password Analysis"
    )
