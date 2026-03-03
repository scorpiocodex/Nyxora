import os

import pytest

from nyxora.core.crypto_engine import CryptoEngine, KDFMode
from nyxora.core.memory_guard import SecureString
from nyxora.utils.exceptions import CryptoError, KeyDerivationError


@pytest.fixture
def engine():
    return CryptoEngine()

def test_generate_salt(engine):
    salt = engine.generate_salt()
    assert len(salt) == 32
    assert isinstance(salt, bytes)

def test_derive_key_argon2id(engine):
    salt = engine.generate_salt()
    with SecureString("password123") as pw:
        key = engine.derive_key(pw, salt)
    assert len(key) == 32
    assert isinstance(key, bytearray)

def test_derive_key_pbkdf2():
    engine = CryptoEngine()
    salt = engine.generate_salt()
    with SecureString("password123") as pw:
        key = engine.derive_key(pw, salt, mode=KDFMode.PBKDF2)
    assert len(key) == 32

def test_derive_key_empty_password(engine):
    salt = engine.generate_salt()
    with pytest.raises(KeyDerivationError):
        with SecureString("") as pw:
            engine.derive_key(pw, salt)

def test_derive_key_empty_salt(engine):
    with pytest.raises(KeyDerivationError):
        with SecureString("password123") as pw:
            engine.derive_key(pw, b"")

def test_encrypt_decrypt_field_xchacha(engine):
    key = os.urandom(32)
    plaintext = b"secret data"
    ciphertext = engine.encrypt_field(plaintext, key)
    assert ciphertext != plaintext

    decrypted = engine.decrypt_field(ciphertext, key)
    assert decrypted == plaintext

def test_encrypt_decrypt_field_aesgcm():
    from nyxora.core.crypto_engine import EncryptionAlgorithm
    engine = CryptoEngine(default_algorithm=EncryptionAlgorithm.AES_256_GCM)
    key = os.urandom(32)
    plaintext = b"secret data"
    ciphertext = engine.encrypt_field(plaintext, key)
    assert ciphertext != plaintext

    decrypted = engine.decrypt_field(ciphertext, key)
    assert decrypted == plaintext

def test_decrypt_invalid_key(engine):
    key1 = os.urandom(32)
    key2 = os.urandom(32)
    plaintext = b"secret data"
    ciphertext = engine.encrypt_field(plaintext, key1)

    with pytest.raises(CryptoError):
        engine.decrypt_field(ciphertext, key2)

def test_encrypt_invalid_key_length(engine):
    key = os.urandom(16)
    with pytest.raises(CryptoError):
        engine.encrypt_field(b"data", key)

def test_decrypt_invalid_key_length(engine):
    key = os.urandom(16)
    from nyxora.utils.exceptions import DecryptionError
    with pytest.raises(DecryptionError):
        engine.decrypt_field(b"data", key)

def test_hmac_generation_and_verification(engine):
    key = os.urandom(32)
    data = b"message to authenticate"
    mac = engine.compute_hmac(data, key)
    assert len(mac) == 64  # SHA512 is 64 bytes

    assert engine.verify_hmac(data, mac, key) is True

    # Tampered data
    assert engine.verify_hmac(b"tampered", mac, key) is False

    # Tampered mac
    tampered_mac = bytearray(mac)
    tampered_mac[0] ^= 1
    assert engine.verify_hmac(data, bytes(tampered_mac), key) is False

def test_hash_for_hibp(engine):
    # known SHA-1 hash for "password" is 5BAA61E4C9B93F3F0682250B6CF8331B7EE68FD8
    prefix, suffix = engine.hash_for_hibp("password")
    assert prefix == "5BAA6"
    assert suffix == "1E4C9B93F3F0682250B6CF8331B7EE68FD8"
