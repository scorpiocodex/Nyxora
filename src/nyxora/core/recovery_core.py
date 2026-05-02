"""Recovery mechanisms for NYXORA.

Provides:
  - TOTP (RFC 6238) via pyotp for two-factor authentication
  - Emergency recovery capsule: encrypted file containing root key
  - Basic Shamir-like secret splitting (XOR-based for two shares,
    polynomial for N shares using GF(256))
"""

from __future__ import annotations

import os
import struct
import time
from pathlib import Path

import orjson
import pyotp

from nyxora.core.crypto_engine import CryptoEngine, EncryptedField
from nyxora.core.memory_guard import wipe_memory
from nyxora.utils.exceptions import RecoveryError

# ── Constants ──────────────────────────────────────────────────────────────────

CAPSULE_MAGIC = b"NYX\x01"  # 4-byte magic header
CAPSULE_VERSION = 1


# ── RecoveryManager ───────────────────────────────────────────────────────────

class RecoveryManager:
    """Manages all recovery pathways: TOTP, capsule, and secret splitting."""

    def __init__(self, crypto: CryptoEngine) -> None:
        self._crypto = crypto

    # ── TOTP ───────────────────────────────────────────────────────────────

    def generate_totp_secret(self) -> str:
        """Generate a new base32-encoded TOTP secret."""
        return pyotp.random_base32()

    def verify_totp(self, token: str, secret: str, window: int = 1) -> bool:
        """Verify a 6-digit TOTP token against the given secret.

        Args:
            token: 6-digit OTP from the authenticator app.
            secret: base32-encoded shared secret.
            window: number of 30-second windows to accept (drift tolerance).
        """
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=window)

    def get_totp_uri(
        self, secret: str, label: str, issuer: str = "NYXORA"
    ) -> str:
        """Return an otpauth:// URI for QR code generation."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=label, issuer_name=issuer)

    def get_totp_current(self, secret: str) -> str:
        """Return the current TOTP value (for testing/display)."""
        return pyotp.TOTP(secret).now()  # pragma: no cover

    # ── Emergency Recovery Capsule ─────────────────────────────────────────
    #
    # File format:
    #   [4-byte magic][4-byte version][32-byte salt][N-byte EncryptedField]
    #
    # Encrypted payload (orjson):
    #   {version, vault_id, encrypted_root_key_hex, created_at, hint}
    #
    # The root key is double-encrypted:
    #   1. capsule_password → HKDF key → encrypt root_key → hex
    #   2. That hex is then stored inside the outer EncryptedField

    def create_recovery_capsule(
        self,
        root_key: bytearray,
        vault_id: str,
        capsule_password: str,
        output_path: Path,
        hint: str = "",
    ) -> None:
        """Encrypt the root key into a portable recovery capsule file.

        The capsule is protected by a separate password (not the vault password).
        Store this file securely, offline, separate from the vault.
        """
        if not vault_id:
            raise ValueError("vault_id cannot be empty")  # pragma: no cover
        if not capsule_password:
            raise ValueError("capsule_password cannot be empty")  # pragma: no cover

        salt = self._crypto.generate_salt()
        capsule_key = self._crypto.derive_key(capsule_password, salt)
        inner_key = self._crypto._hkdf_derive(
            capsule_key, b"nyxora:capsule:inner"
        )
        outer_key = self._crypto._hkdf_derive(
            capsule_key, b"nyxora:capsule:outer"
        )

        try:
            # Inner encryption: encrypt the root key with a dedicated derived key
            inner_ef = self._crypto.encrypt_field(bytes(root_key), inner_key)

            payload = {
                "version": CAPSULE_VERSION,
                "vault_id": vault_id,
                "root_key_enc": inner_ef.to_bytes().hex(),
                "created_at": int(time.time()),
                "hint": hint,
            }
            payload_bytes = orjson.dumps(payload)

            # Outer encryption: encrypt the JSON payload with a dedicated derived key
            outer_ef = self._crypto.encrypt_field(payload_bytes, outer_key)
            outer_blob = outer_ef.to_bytes()

        finally:
            wipe_memory(capsule_key)
            wipe_memory(inner_key)
            wipe_memory(outer_key)

        # Write capsule file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(CAPSULE_MAGIC)
            f.write(struct.pack(">I", CAPSULE_VERSION))
            f.write(salt)
            f.write(outer_blob)

    def restore_from_capsule(
        self, capsule_path: Path, capsule_password: str
    ) -> bytearray:
        """Decrypt a recovery capsule and return the root key.

        Returns:
            bytearray: The recovered root key. Caller must wipe after use.

        Raises:
            RecoveryError: If the capsule is corrupt, invalid, or the password
                           is wrong.
        """
        if not capsule_path.exists():
            raise RecoveryError(f"Capsule file not found: {capsule_path}")

        try:
            with open(capsule_path, "rb") as f:
                magic = f.read(4)
                if magic != CAPSULE_MAGIC:
                    raise RecoveryError("Invalid capsule file (bad magic header).")  # pragma: no cover

                version_bytes = f.read(4)
                version = struct.unpack(">I", version_bytes)[0]
                if version != CAPSULE_VERSION:
                    raise RecoveryError(f"Unsupported capsule version: {version}")  # pragma: no cover

                salt = f.read(32)
                outer_blob = f.read()

        except RecoveryError:  # pragma: no cover
            raise  # pragma: no cover
        except Exception as exc:  # pragma: no cover
            raise RecoveryError(f"Failed to read capsule file: {exc}") from exc  # pragma: no cover

        capsule_key = self._crypto.derive_key(capsule_password, salt)
        inner_key = self._crypto._hkdf_derive(
            capsule_key, b"nyxora:capsule:inner"
        )
        outer_key = self._crypto._hkdf_derive(
            capsule_key, b"nyxora:capsule:outer"
        )
        try:
            # Decrypt outer blob → JSON payload
            try:
                outer_ef = EncryptedField.from_bytes(outer_blob)
                payload_bytes = self._crypto.decrypt_field(outer_ef, outer_key)
            except Exception as exc:
                raise RecoveryError(
                    "Capsule decryption failed — wrong password or corrupted file."
                ) from exc

            payload = orjson.loads(payload_bytes)

            # Decrypt inner root key
            try:
                inner_blob = bytes.fromhex(payload["root_key_enc"])
                inner_ef = EncryptedField.from_bytes(inner_blob)
                root_key_bytes = self._crypto.decrypt_field(inner_ef, inner_key)
            except Exception as exc:  # pragma: no cover
                raise RecoveryError("Failed to decrypt root key from capsule.") from exc  # pragma: no cover

            return bytearray(root_key_bytes)

        finally:
            wipe_memory(capsule_key)
            wipe_memory(inner_key)
            wipe_memory(outer_key)

    # ── Secret Splitting (Shamir-inspired GF(256)) ─────────────────────────

    def split_secret(self, secret: bytes, n: int, k: int) -> list[bytes]:
        """Split a secret into n shares, requiring k to reconstruct.

        Uses a polynomial in GF(256) evaluated at points 1..n.
        Each share is: [1-byte x-coordinate] + [share_data].

        Args:
            secret: The bytes to split.
            n: Total number of shares to create.
            k: Minimum shares required to reconstruct.

        Returns:
            List of n share byte strings.
        """
        if k < 2 or n < k:
            raise ValueError(f"Invalid parameters: k={k}, n={n}. Need 2 <= k <= n.")  # pragma: no cover
        if not secret:
            raise ValueError("Secret cannot be empty")  # pragma: no cover

        shares: list[list[int]] = [[] for _ in range(n)]

        for byte_val in secret:
            # Generate k-1 random coefficients for this byte's polynomial
            coeffs = [byte_val] + [int.from_bytes(os.urandom(1), "big") for _ in range(k - 1)]

            for i in range(1, n + 1):
                y = self._gf256_poly_eval(coeffs, i)
                shares[i - 1].append(y)

        result: list[bytes] = []
        for i, share_data in enumerate(shares):
            x = i + 1  # x-coordinate (1-indexed)
            result.append(bytes([x]) + bytes(share_data))

        return result

    def combine_shares(self, shares: list[bytes], k: int) -> bytes:
        """Reconstruct a secret from k shares using Lagrange interpolation in GF(256).

        Args:
            shares: List of share byte strings (as returned by split_secret).
            k: Number of shares provided (must be >= the original k threshold).
        """
        if k < 2:
            raise ValueError("Threshold k must be at least 2")  # pragma: no cover
        if len(shares) < k:
            raise RecoveryError(
                f"Insufficient shares: need at least {k}, got {len(shares)}."
            )

        # Unpack x-coordinates and share data
        xs: list[int] = [s[0] for s in shares[:k]]
        ys_per_byte: list[list[int]] = [list(s[1:]) for s in shares[:k]]

        secret_length = len(ys_per_byte[0])
        secret: list[int] = []

        for byte_idx in range(secret_length):
            ys = [ys_per_byte[share_idx][byte_idx] for share_idx in range(k)]
            value = self._gf256_lagrange(xs, ys)
            secret.append(value)

        return bytes(secret)

    # ── GF(256) arithmetic ─────────────────────────────────────────────────

    # Precomputed multiplicative inverse table for GF(2^8).
    # _GF256_INV[0] is undefined (zero has no inverse); set to 0 as sentinel.
    _GF256_INV: list[int] = [0] * 256

    @classmethod
    def _build_gf256_inv_table(cls) -> None:
        for a in range(1, 256):
            for b in range(1, 256):
                if cls._gf256_mul(a, b) == 1:
                    cls._GF256_INV[a] = b
                    break

    @staticmethod
    def _gf256_mul(a: int, b: int) -> int:
        """Multiply two elements in GF(2^8) with irreducible polynomial 0x11B."""
        result = 0
        for _ in range(8):
            if b & 1:
                result ^= a
            high = a & 0x80
            a = (a << 1) & 0xFF
            if high:
                a ^= 0x1B
            b >>= 1
        return result

    @staticmethod
    def _gf256_inv(a: int) -> int:
        if a == 0:
            raise ValueError("Zero has no multiplicative inverse in GF(256).")
        return RecoveryManager._GF256_INV[a]

    @staticmethod
    def _gf256_poly_eval(coeffs: list[int], x: int) -> int:
        """Evaluate polynomial with given coefficients at point x in GF(256)."""
        result = 0
        x_pow = 1
        for coeff in coeffs:
            result ^= RecoveryManager._gf256_mul(coeff, x_pow)
            x_pow = RecoveryManager._gf256_mul(x_pow, x)
        return result

    @classmethod
    def _gf256_lagrange(cls, xs: list[int], ys: list[int]) -> int:
        """Lagrange interpolation at x=0 in GF(256)."""
        k = len(xs)
        result = 0
        for i in range(k):
            num = ys[i]
            den = 1
            for j in range(k):
                if i != j:
                    num = cls._gf256_mul(num, xs[j])
                    den = cls._gf256_mul(den, xs[i] ^ xs[j])
            result ^= cls._gf256_mul(num, cls._gf256_inv(den))
        return result


RecoveryManager._build_gf256_inv_table()
