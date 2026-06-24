import itertools
import time
from unittest.mock import patch

import pytest

from nyxora.core.session_core import SessionManager
from nyxora.utils.exceptions import BruteForceLockedError, VaultLockedError


def test_session_init():
    sm = SessionManager()
    assert sm.is_locked() is True
    assert sm.get_session_id() is None
    assert sm.get_failed_attempts() == 0
    assert sm.get_lockout_remaining() == 0.0
    assert len(sm.terminal_hash) == 64  # SHA256 hex length

def test_unlock_and_lock():
    sm = SessionManager()
    key = bytearray(b"my-secret-root-key")

    sid = sm.unlock(key)
    assert sid is not None
    assert sm.is_locked() is False
    assert sm.get_session_id() == sid

    # Check we get the same root key out
    out_key = sm.get_root_key()
    assert out_key == b"my-secret-root-key"

    # Unlock again while already unlocked -> wipe root key
    key2 = bytearray(b"another")
    sid2 = sm.unlock(key2)
    assert sid2 is not None

    # Test manual lock
    sm.lock()
    assert sm.is_locked() is True
    assert sm.get_session_id() is None
    with pytest.raises(VaultLockedError):
        sm.get_root_key()

    # Test panic lock
    sm.panic_lock()
    assert sm.is_locked() is True

def test_panic_lock_active():
    sm = SessionManager()
    sm.record_failed_attempt()  # fails=1
    sm.unlock(bytearray(b"key")) # Valid unlock

    sm.panic_lock()
    assert sm.is_locked() is True
    assert sm.get_failed_attempts() == 0
    assert sm.get_lockout_remaining() == 0.0
    assert sm.get_session_id() is None

def test_lockout_ladder():
    sm = SessionManager()

    # Freeze the clock across record -> remaining -> unlock so the
    # get_lockout_remaining() read and the _check_lockout() read inside unlock()
    # see ONE instant. With a live clock the two wall-clock reads can straddle an
    # integer-second boundary and int()-truncate to different values — a
    # test-side flake on coarse-timer platforms (windows time.time() ~15.6ms).
    # The lockout logic itself is unaffected: enforcement uses the float
    # `remaining > 0`, and the int() in the error is display-only.
    now = time.time()
    with patch("nyxora.core.session_core.time.time", return_value=now):
        # Fail 3 times -> 5 sec lockout according to the ladder
        sm.record_failed_attempt()
        sm.record_failed_attempt()
        sm.record_failed_attempt()

        assert sm.get_failed_attempts() == 3
        remaining = sm.get_lockout_remaining()
        assert remaining == 5.0  # frozen clock: exactly the ladder value

        # Unlocking during lockout should fail with the ladder's lockout seconds
        with pytest.raises(BruteForceLockedError) as exc:
            sm.unlock(bytearray(b"test"))

        assert exc.value.lockout_seconds == 5  # the 3-fail ladder rung, not a clock sample

    # Simulate time passing by returning a fixed time 15 seconds in the future
    future_time = now + 15
    with patch("nyxora.core.session_core.time.time", return_value=future_time):
        # Now 15 seconds later, lockout should be over
        assert sm.get_lockout_remaining() == 0.0
        sm.record_successful_unlock()
        assert sm.get_failed_attempts() == 0

def test_lockout_ladder_high_count():
    sm = SessionManager()
    for _ in range(16):
        sm.record_failed_attempt()

    # 15+ fails = 86400 seconds
    rem = sm.get_lockout_remaining()
    assert rem > 80000

@patch("nyxora.core.session_core.time.sleep", return_value=None)
def test_inactivity_monitor(mock_sleep):
    sm = SessionManager(inactivity_timeout=5)

    # _last_activity must be set from mock time, not a real Unix timestamp.
    # Use a constant value so elapsed = time.time() - _last_activity = 0 always,
    # which keeps the monitor looping without locking. Infinite values prevent
    # StopIteration from being raised in the daemon thread.
    with patch("nyxora.core.session_core.time.time", side_effect=itertools.repeat(1000.0)):
        key = bytearray(b"temp")
        sm.unlock(key)
        assert sm.is_locked() is False

        if sm._monitor_thread:
            sm._monitor_thread.join(timeout=0.5)

def test_terminal_hash_no_ppid():
    import os
    original = None
    if hasattr(os, "getppid"):
        original = os.getppid
        del os.getppid

    try:
        sm = SessionManager()
        # Should drop back to fallback PPID = 0
        assert len(sm.terminal_hash) == 64
    finally:
        if original:
            os.getppid = original
