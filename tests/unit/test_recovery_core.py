import os

import pytest

from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.recovery_core import RecoveryManager
from nyxora.utils.exceptions import RecoveryError


@pytest.fixture
def crypto():
    return CryptoEngine()

@pytest.fixture
def recovery(crypto):
    return RecoveryManager(crypto)

def test_totp_setup_and_verify(recovery):
    secret = recovery.generate_totp_secret()
    uri = recovery.get_totp_uri(secret, "user@nyxora")
    assert secret.isupper()
    assert ("user@nyxora" in uri) or ("user%40nyxora" in uri)

    # We can't easily verify a current TOTP token since it requires current time,
    # but we can check if it verifies a clearly invalid token as False
    assert recovery.verify_totp("000000", secret) is False

def test_recovery_capsule_lifecycle(recovery, tmp_path):
    root_key = bytearray(os.urandom(32))
    password = "emergency_password"
    capsule_path = tmp_path / "recovery.capsule"
    vault_id = "test-vault-id"

    # Create capsule
    recovery.create_recovery_capsule(root_key, vault_id, password, capsule_path)
    assert capsule_path.exists()

    # Restore capsule
    recovered_key = recovery.restore_from_capsule(capsule_path, password)
    assert recovered_key == root_key

    # Restore with wrong password
    with pytest.raises(RecoveryError):
        recovery.restore_from_capsule(capsule_path, "wrong_password")

def test_shamir_split_and_combine(recovery):
    secret = os.urandom(32)

    # Split into 5 shares, 3 required
    shares = recovery.split_secret(secret, n=5, k=3)
    assert len(shares) == 5

    # Combine with 3 shares (0, 2, 4 just to pick subset)
    subset = [shares[0], shares[2], shares[4]]
    recovered = recovery.combine_shares(subset, k=3)
    assert recovered == secret

    # Combine with 5 shares (even if we pass more, it just uses k)
    recovered_all = recovery.combine_shares(shares, k=3)
    assert recovered_all == secret

    # Combine with 2 shares (fails assertion or raises RecoveryError)
    with pytest.raises(RecoveryError):
        recovery.combine_shares([shares[0], shares[1]], k=3)

def test_verify_yubikey_removed(recovery):
    # Ensure this method doesn't exist anymore
    with pytest.raises(AttributeError):
        recovery.verify_yubikey("ykkkkkkkkkkkkkkkkk")
