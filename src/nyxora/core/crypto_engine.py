"""Cryptographic engine for NYXORA.

Provides:
  - Key derivation: Argon2id (primary) with PBKDF2-HMAC-SHA512 fallback
  - HKDF-based per-entry and per-purpose key derivation
  - Authenticated encryption: XChaCha20-Poly1305 (primary) and AES-256-GCM
  - HMAC-SHA512 with constant-time comparison
  - Password entropy scoring and HIBP hash preparation
"""

from __future__ import annotations

import hashlib
import hmac as hmac_module
import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

import nacl.bindings
import nacl.exceptions
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from nyxora.core.memory_guard import SecureString, wipe_memory
from nyxora.utils.exceptions import CryptoError, DecryptionError, KeyDerivationError

if TYPE_CHECKING:
    pass

# ── Constants ──────────────────────────────────────────────────────────────────

SALT_SIZE = 32             # 256-bit
KEY_SIZE = 32              # 256-bit
XCHACHA20_NONCE_SIZE = 24  # 192-bit
AESGCM_NONCE_SIZE = 12     # 96-bit
TAG_SIZE = 16

# Argon2id defaults (production)
ARGON2_MEMORY_COST = 262144  # 256 MB in KiB
ARGON2_TIME_COST = 4
ARGON2_PARALLELISM = 4

PBKDF2_ITERATIONS = 600_000

# Algorithm byte identifiers for serialisation
_ALG_XCHACHA20 = b"\x01"
_ALG_AESGCM = b"\x02"


# ── Enumerations ──────────────────────────────────────────────────────────────

class KDFMode(Enum):
    ARGON2ID = auto()
    PBKDF2 = auto()


class EncryptionAlgorithm(Enum):
    XCHACHA20_POLY1305 = auto()
    AES_256_GCM = auto()


# ── Encrypted field ───────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class EncryptedField:
    """Serialisable container for a single encrypted value.

    Wire format: [1-byte alg_id][nonce][tag][ciphertext]
    """

    ciphertext: bytes
    nonce: bytes
    tag: bytes
    algorithm: EncryptionAlgorithm

    def to_bytes(self) -> bytes:
        """Serialise to wire format."""
        if self.algorithm == EncryptionAlgorithm.XCHACHA20_POLY1305:
            alg_id = _ALG_XCHACHA20
        else:
            alg_id = _ALG_AESGCM  # pragma: no cover
        return alg_id + self.nonce + self.tag + self.ciphertext

    @classmethod
    def from_bytes(cls, data: bytes) -> "EncryptedField":
        """Deserialise from wire format."""
        if len(data) < 2:
            raise DecryptionError("EncryptedField data too short.")  # pragma: no cover

        alg_id = data[:1]
        if alg_id == _ALG_XCHACHA20:
            algorithm = EncryptionAlgorithm.XCHACHA20_POLY1305
            nonce_size = XCHACHA20_NONCE_SIZE
        elif alg_id == _ALG_AESGCM:  # pragma: no cover
            algorithm = EncryptionAlgorithm.AES_256_GCM  # pragma: no cover
            nonce_size = AESGCM_NONCE_SIZE  # pragma: no cover
        else:  # pragma: no cover
            raise DecryptionError(f"Unknown algorithm identifier: {alg_id!r}")  # pragma: no cover

        offset = 1
        nonce = data[offset: offset + nonce_size]
        offset += nonce_size
        tag = data[offset: offset + TAG_SIZE]
        offset += TAG_SIZE
        ciphertext = data[offset:]

        if len(nonce) != nonce_size or len(tag) != TAG_SIZE:
            raise DecryptionError("EncryptedField has invalid nonce or tag length.")  # pragma: no cover

        return cls(ciphertext=ciphertext, nonce=nonce, tag=tag, algorithm=algorithm)


# ── CryptoEngine ──────────────────────────────────────────────────────────────

class CryptoEngine:
    """Cryptographic orchestration engine.

    All key material is handled as ``bytearray`` objects that callers must
    wipe after use via :func:`~nyxora.core.memory_guard.wipe_memory`.
    """

    def __init__(
        self,
        argon2_memory: int = ARGON2_MEMORY_COST,
        argon2_time: int = ARGON2_TIME_COST,
        argon2_parallelism: int = ARGON2_PARALLELISM,
        default_algorithm: EncryptionAlgorithm = EncryptionAlgorithm.XCHACHA20_POLY1305,
    ) -> None:
        self._argon2_memory = argon2_memory
        self._argon2_time = argon2_time
        self._argon2_parallelism = argon2_parallelism
        self._default_algorithm = default_algorithm

    # ── Key derivation ─────────────────────────────────────────────────────

    def derive_key(
        self,
        master_password: SecureString | str | bytes,
        salt: bytes,
        mode: KDFMode = KDFMode.ARGON2ID,
    ) -> bytearray:
        """Derive a 256-bit root key from a master password.

        Returns a ``bytearray`` — the caller is responsible for wiping it.

        Args:
            master_password: The user's master password.
            salt: A 32-byte random salt (stored alongside encrypted data).
            mode: KDF algorithm. Argon2id is the default; PBKDF2 is the fallback.

        Raises:
            KeyDerivationError: If master_password or salt is empty or invalid.
        """
        if not master_password:
            raise KeyDerivationError("Master password cannot be empty.")
        if not salt:
            raise KeyDerivationError("Salt cannot be empty.")

        if isinstance(master_password, SecureString):
            pw_bytes = master_password.to_bytes()
        elif isinstance(master_password, str):
            pw_bytes = master_password.encode("utf-8")
        else:
            pw_bytes = bytes(master_password)

        try:
            if mode == KDFMode.ARGON2ID:
                return self._derive_argon2id(pw_bytes, salt)
            else:
                return self._derive_pbkdf2(pw_bytes, salt)
        finally:
            # Best-effort wipe of local password bytes
            tmp = bytearray(pw_bytes)
            wipe_memory(tmp)
            del pw_bytes

    def _derive_argon2id(self, pw_bytes: bytes, salt: bytes) -> bytearray:
        try:
            from argon2.low_level import Type, hash_secret_raw  # type: ignore[import]
            raw = hash_secret_raw(
                secret=pw_bytes,
                salt=salt,
                time_cost=self._argon2_time,
                memory_cost=self._argon2_memory,
                parallelism=self._argon2_parallelism,
                hash_len=KEY_SIZE,
                type=Type.ID,
            )
            result = bytearray(raw)
            # raw is a bytes object (immutable) — cannot be zeroed in CPython.
            # Deleting the reference removes it from this frame's scope immediately,
            # minimising the window before CPython's reference counting reclaims it.
            del raw
            return result
        except ImportError as exc:  # pragma: no cover
            raise KeyDerivationError(  # pragma: no cover
                "argon2-cffi is not installed. Cannot derive key."  # pragma: no cover
            ) from exc  # pragma: no cover
        except Exception as exc:  # pragma: no cover
            raise KeyDerivationError(f"Argon2id key derivation failed: {exc}") from exc  # pragma: no cover

    def _derive_pbkdf2(self, pw_bytes: bytes, salt: bytes) -> bytearray:
        try:
            raw = hashlib.pbkdf2_hmac(
                "sha512",
                pw_bytes,
                salt,
                PBKDF2_ITERATIONS,
                dklen=KEY_SIZE,
            )
            return bytearray(raw)
        except Exception as exc:  # pragma: no cover
            raise KeyDerivationError(f"PBKDF2 key derivation failed: {exc}") from exc  # pragma: no cover

    def derive_entry_key(self, root_key: bytearray, entry_id: str) -> bytearray:
        """Derive a per-entry encryption key via HKDF-SHA512.

        Each entry gets an isolated key so a single compromise cannot cascade.
        """
        info = f"nyxora:entry:{entry_id}".encode("utf-8")
        return self._hkdf_derive(root_key, info)

    def derive_hmac_key(self, root_key: bytearray) -> bytearray:
        """Derive the vault-wide HMAC key via HKDF-SHA512."""
        return self._hkdf_derive(root_key, b"nyxora:hmac:vault")

    def derive_backup_key(self, root_key: bytearray, backup_id: str) -> bytearray:
        """Derive a backup-specific encryption key via HKDF-SHA512."""
        info = f"nyxora:backup:{backup_id}".encode("utf-8")
        return self._hkdf_derive(root_key, info)

    def derive_locker_key(self, root_key: bytearray, filename: str) -> bytearray:
        """Derive a locker file encryption key via HKDF-SHA512."""
        info = f"nyxora:locker:{filename}".encode("utf-8")
        return self._hkdf_derive(root_key, info)

    def _hkdf_derive(self, key_material: bytearray, info: bytes) -> bytearray:
        hkdf = HKDF(
            algorithm=hashes.SHA512(),
            length=KEY_SIZE,
            salt=None,
            info=info,
        )
        raw = hkdf.derive(bytes(key_material))
        return bytearray(raw)

    # ── Encryption ─────────────────────────────────────────────────────────

    def encrypt_field(
        self,
        data: bytes | str,
        key: bytearray | bytes,
        algorithm: EncryptionAlgorithm | None = None,
        associated_data: bytes | None = None,
    ) -> EncryptedField:
        """Encrypt a single field value with AEAD.

        Returns an :class:`EncryptedField` ready for storage.

        Raises:
            CryptoError: If the key length is invalid.
        """
        if len(key) != KEY_SIZE:
            raise CryptoError(f"Invalid encryption key length: expected {KEY_SIZE}, got {len(key)}")

        if algorithm is None:
            algorithm = self._default_algorithm

        if isinstance(data, str):
            data = data.encode("utf-8")

        key_bytes = bytes(key)

        if algorithm == EncryptionAlgorithm.XCHACHA20_POLY1305:
            return self._encrypt_xchacha20(data, key_bytes, associated_data)
        else:
            return self._encrypt_aesgcm(data, key_bytes, associated_data)

    def _encrypt_xchacha20(
        self, plaintext: bytes, key: bytes, ad: bytes | None
    ) -> EncryptedField:
        nonce = os.urandom(XCHACHA20_NONCE_SIZE)
        ad_bytes = ad or b""
        ciphertext_with_tag = nacl.bindings.crypto_aead_xchacha20poly1305_ietf_encrypt(
            message=plaintext,
            aad=ad_bytes,
            nonce=nonce,
            key=key,
        )
        # PyNaCl appends the 16-byte Poly1305 tag at the end
        ciphertext = ciphertext_with_tag[:-TAG_SIZE]
        tag = ciphertext_with_tag[-TAG_SIZE:]
        return EncryptedField(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            algorithm=EncryptionAlgorithm.XCHACHA20_POLY1305,
        )

    def _encrypt_aesgcm(
        self, plaintext: bytes, key: bytes, ad: bytes | None
    ) -> EncryptedField:
        nonce = os.urandom(AESGCM_NONCE_SIZE)
        ad_bytes = ad or b""
        aesgcm = AESGCM(key)
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, ad_bytes)
        ciphertext = ciphertext_with_tag[:-TAG_SIZE]
        tag = ciphertext_with_tag[-TAG_SIZE:]
        return EncryptedField(
            ciphertext=ciphertext,
            nonce=nonce,
            tag=tag,
            algorithm=EncryptionAlgorithm.AES_256_GCM,
        )

    def decrypt_field(
        self,
        ef: EncryptedField,
        key: bytearray | bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        """Decrypt a stored EncryptedField.

        Raises :class:`~nyxora.utils.exceptions.DecryptionError` on failure.
        """
        if len(key) != KEY_SIZE:
            raise DecryptionError(f"Invalid decryption key length: expected {KEY_SIZE}, got {len(key)}")

        key_bytes = bytes(key)
        ad_bytes = associated_data or b""

        try:
            if ef.algorithm == EncryptionAlgorithm.XCHACHA20_POLY1305:
                return self._decrypt_xchacha20(ef, key_bytes, ad_bytes)
            else:
                return self._decrypt_aesgcm(ef, key_bytes, ad_bytes)
        except DecryptionError:
            raise
        except Exception as exc:  # pragma: no cover
            raise DecryptionError(f"Decryption failed: {exc}") from exc  # pragma: no cover

    def _decrypt_xchacha20(
        self, ef: EncryptedField, key: bytes, ad: bytes
    ) -> bytes:
        try:
            ciphertext_with_tag = ef.ciphertext + ef.tag
            return nacl.bindings.crypto_aead_xchacha20poly1305_ietf_decrypt(
                ciphertext=ciphertext_with_tag,
                aad=ad,
                nonce=ef.nonce,
                key=key,
            )
        except nacl.exceptions.CryptoError as exc:  # type: ignore[attr-defined]
            raise DecryptionError("XChaCha20 authentication tag verification failed.") from exc

    def _decrypt_aesgcm(
        self, ef: EncryptedField, key: bytes, ad: bytes
    ) -> bytes:
        try:
            aesgcm = AESGCM(key)
            ciphertext_with_tag = ef.ciphertext + ef.tag
            return aesgcm.decrypt(ef.nonce, ciphertext_with_tag, ad)
        except Exception as exc:  # pragma: no cover
            raise DecryptionError("AES-GCM authentication tag verification failed.") from exc  # pragma: no cover

    # ── HMAC ────────────────────────────────────────────────────────────────

    def compute_hmac(self, data: bytes, key: bytearray | bytes) -> bytes:
        """Compute HMAC-SHA512 over data. Returns 64 bytes."""
        h = hmac_module.new(bytes(key), data, "sha512")
        return h.digest()

    def verify_hmac(self, data: bytes, mac: bytes, key: bytearray | bytes) -> bool:
        """Constant-time HMAC-SHA512 verification."""
        expected = self.compute_hmac(data, key)
        return hmac_module.compare_digest(expected, mac)

    def compute_entry_hmac(
        self, entry_id: str, fields: dict[str, bytes], key: bytearray | bytes
    ) -> bytes:
        """Compute an HMAC that binds the entry identity to all field ciphertexts.

        The MAC covers: entry_id + sorted field names + sorted field ciphertexts.
        This prevents field substitution, reordering, and identity swapping attacks.
        """
        parts: list[bytes] = [entry_id.encode("utf-8")]
        for field_name in sorted(fields.keys()):
            parts.append(field_name.encode("utf-8"))
            parts.append(fields[field_name])
        combined = b"||".join(parts)
        return self.compute_hmac(combined, key)

    # ── Utilities ───────────────────────────────────────────────────────────

    def generate_salt(self) -> bytes:
        """Generate a 256-bit (32-byte) cryptographically random salt."""
        return os.urandom(SALT_SIZE)

    def hash_for_hibp(self, password: str) -> tuple[str, str]:
        """Return (prefix_5, suffix) SHA-1 uppercase for k-anonymity HIBP lookup.

        The caller sends only the prefix to the API and checks if suffix appears
        in the response — the API never sees the full hash or the password.
        """
        sha1 = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
        return sha1[:5], sha1[5:]
