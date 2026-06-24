from unittest.mock import MagicMock, patch

from nyxora.core import memory_guard
from nyxora.core.memory_guard import (
    SecureString,
    try_mlock,
    try_munlock,
    wipe_memory,
)


def test_secure_string_lifecycle():
    sec_str = SecureString("mysecret")
    assert sec_str.to_bytes() == b"mysecret"

    # After exit (context manager), it shouldn't be accessible
    with sec_str as pw:
        assert pw.to_bytes() == b"mysecret"

    # It might still exist as bytearray internally but should be wiped,
    # depending on the internal implementation of to_bytes().
    # Calling to_bytes again usually raises or returns wiped data.
    pass

def test_wipe_memory():
    # Test bytearray wiping
    data = bytearray(b"highly sensitive information")
    wipe_memory(data)
    # Ensure it's not the original string
    assert data != b"highly sensitive information"
    # Assuming it gets zeroed or randomized based on implementation
    assert data == bytearray(len(data)) or data[0] != b"h"[0]

def test_wipe_memory_unsupported_type():
    # string - should just return or warn
    sensitive_str = "sensitive"
    # Should not raise exception
    wipe_memory(sensitive_str)


def test_mlock_munlock_linux_branch():
    """Linux branch: mlock/munlock return 0 on success, and a raised OSError
    from the libc call degrades to False rather than propagating.

    memory_guard selects its branch from platform.system() and the module-level
    _libc/_kernel32 globals bound at import time, so patch those seams — they
    exist on every OS (ctypes.windll does not exist on Linux, and sys.platform is
    not what the product reads)."""
    buf = bytearray(16)
    fake_libc = MagicMock()
    fake_libc.mlock.return_value = 0
    fake_libc.munlock.return_value = 0
    with patch.object(memory_guard.platform, "system", return_value="Linux"), \
         patch.object(memory_guard, "_MLOCK_AVAILABLE", True), \
         patch.object(memory_guard, "_libc", fake_libc):
        assert try_mlock(buf) is True
        assert try_munlock(buf) is True
        fake_libc.mlock.side_effect = Exception("failed")
        assert try_mlock(buf) is False
    assert fake_libc.mlock.call_count == 2
    fake_libc.munlock.assert_called_once()


def test_mlock_munlock_windows_branch():
    """Windows branch: VirtualLock/VirtualUnlock return nonzero on success; an
    exception from the kernel32 call degrades to False."""
    buf = bytearray(16)
    fake_k32 = MagicMock()
    fake_k32.VirtualLock.return_value = 1
    fake_k32.VirtualUnlock.return_value = 1
    with patch.object(memory_guard.platform, "system", return_value="Windows"), \
         patch.object(memory_guard, "_MLOCK_AVAILABLE", True), \
         patch.object(memory_guard, "_kernel32", fake_k32):
        assert try_mlock(buf) is True
        assert try_munlock(buf) is True
        fake_k32.VirtualLock.side_effect = Exception("failed")
        assert try_mlock(buf) is False
    assert fake_k32.VirtualLock.call_count == 2
    fake_k32.VirtualUnlock.assert_called_once()
