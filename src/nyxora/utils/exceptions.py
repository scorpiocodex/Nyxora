"""Custom exception hierarchy for NYXORA.

Every exception exposes a `user_message` (safe for terminal display) and
an `exit_code` (for process exit). No raw Python tracebacks ever reach the
terminal — the CLI layer catches all NyxoraError subclasses.
"""

from __future__ import annotations


class NyxoraError(Exception):
    """Base exception for all NYXORA errors."""

    exit_code: int = 1
    user_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, user_message: str | None = None) -> None:
        super().__init__(message or self.user_message)
        if user_message is not None:
            self.user_message = user_message
        elif message is not None:
            self.user_message = message


# ── Cryptographic errors ────────────────────────────────────────────────────

class CryptoError(NyxoraError):
    """Base for all cryptographic failures."""
    user_message = "A cryptographic operation failed."


class KeyDerivationError(CryptoError):
    """KDF failed — insufficient memory, wrong parameters, or platform limitation."""
    user_message = "Key derivation failed. Check available memory and KDF parameters."


class DecryptionError(CryptoError):
    """Authentication tag verification failed or data is corrupted."""
    user_message = "Decryption failed. The data may be corrupted or the key is wrong."


class IntegrityError(NyxoraError):
    """HMAC mismatch — vault has been tampered with."""
    user_message = "Vault integrity check failed. Tampering may have occurred."


# ── Vault errors ─────────────────────────────────────────────────────────────

class VaultError(NyxoraError):
    """Base for vault-level errors."""
    user_message = "A vault operation failed."


class VaultLockedError(VaultError):
    """Attempted an operation on a locked vault."""
    exit_code = 2
    user_message = "Vault is locked. Run 'nyx vault unlock' first."


class VaultNotFoundError(VaultError):
    """Vault file does not exist at the given path."""
    user_message = "Vault file not found. Run 'nyx vault init' to create one."


class VaultAlreadyExistsError(VaultError):
    """Vault file already exists and would be overwritten."""
    user_message = "A vault already exists at that path. Use --force to overwrite."


# ── Session errors ───────────────────────────────────────────────────────────

class SessionError(NyxoraError):
    """Base for session-level errors."""
    user_message = "A session error occurred."


class BruteForceLockedError(SessionError):
    """Too many failed unlock attempts — locked out."""
    exit_code = 3

    def __init__(self, lockout_seconds: int = 0, message: str | None = None) -> None:
        self.lockout_seconds = lockout_seconds
        msg = f"Too many failed attempts. Locked out for {lockout_seconds} seconds."
        super().__init__(message or msg)
        self.user_message = msg


# ── Data errors ───────────────────────────────────────────────────────────────

class EntryNotFoundError(NyxoraError):
    """Requested entry does not exist in the vault."""
    user_message = "Entry not found."


# ── Recovery errors ──────────────────────────────────────────────────────────

class RecoveryError(NyxoraError):
    """Recovery operation failed."""
    user_message = "Recovery operation failed."


# ── Backup errors ─────────────────────────────────────────────────────────────

class BackupError(NyxoraError):
    """Backup or restore operation failed."""
    user_message = "Backup operation failed."


# ── Configuration errors ──────────────────────────────────────────────────────

class ConfigError(NyxoraError):
    """Configuration validation or load failure."""
    user_message = "Configuration error. Check your config file."


# ── Locker errors ─────────────────────────────────────────────────────────────

class LockerError(NyxoraError):
    """File locker operation failed."""
    user_message = "Locker operation failed."


# ── Intel errors ──────────────────────────────────────────────────────────────

class IntelError(NyxoraError):
    """Breach intelligence or scoring failed."""
    user_message = "Security analysis failed."
