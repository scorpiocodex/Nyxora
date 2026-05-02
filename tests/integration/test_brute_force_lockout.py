import time

import pytest

from nyxora.core.crypto_engine import CryptoEngine
from nyxora.core.memory_guard import generate_session_token, wipe_memory
from nyxora.core.session_core import SessionManager
from nyxora.utils.exceptions import BruteForceLockedError


def test_failed_attempts_trigger_lockout():
    session = SessionManager(inactivity_timeout=300)
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("correct-password", salt)

    # 3 failures triggers the first rung of the ladder (5s lockout)
    for _ in range(3):
        session.record_failed_attempt()

    assert session.get_lockout_remaining() > 0
    assert session.get_failed_attempts() == 3

    with pytest.raises(BruteForceLockedError):
        session.unlock(root_key, generate_session_token())

    wipe_memory(root_key)


def test_successful_unlock_resets_counter():
    session = SessionManager(inactivity_timeout=300)
    engine = CryptoEngine(argon2_memory=8192, argon2_time=1, argon2_parallelism=1)
    salt = engine.generate_salt()
    root_key = engine.derive_key("correct-password", salt)

    # Two failures — below the threshold of 3, no lockout yet
    session.record_failed_attempt()
    session.record_failed_attempt()
    assert session.get_failed_attempts() == 2
    assert session.get_lockout_remaining() == 0.0

    # Successful unlock followed by explicit reset clears the counter
    session.unlock(root_key, generate_session_token())
    session.record_successful_unlock()
    assert session.get_failed_attempts() == 0
    assert session.get_lockout_remaining() == 0.0
    session.lock()

    wipe_memory(root_key)


def test_lockout_ladder_escalation():
    # 3 failures → 5s lockout
    session = SessionManager(inactivity_timeout=300)
    for _ in range(3):
        session.record_failed_attempt()
    remaining_at_3 = session.get_lockout_remaining()
    assert 4 <= remaining_at_3 <= 6

    # 5 failures → 30s lockout
    session2 = SessionManager(inactivity_timeout=300)
    for _ in range(5):
        session2.record_failed_attempt()
    remaining_at_5 = session2.get_lockout_remaining()
    assert 28 <= remaining_at_5 <= 32

    # 7 failures → 300s lockout
    session3 = SessionManager(inactivity_timeout=300)
    for _ in range(7):
        session3.record_failed_attempt()
    remaining_at_7 = session3.get_lockout_remaining()
    assert 298 <= remaining_at_7 <= 302
