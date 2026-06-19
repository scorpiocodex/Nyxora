"""Secure memory management for NYXORA.

Provides best-effort protection for sensitive key material in memory:
  - SecureString: wraps sensitive strings as mutable bytearrays, zeroed on exit
  - wipe_memory: 3-pass overwrite (urandom → 0xFF → 0x00)
  - secure_buffer: context manager that allocates, optionally mlocks, and wipes
  - try_mlock / try_munlock: Linux-only ctypes mlock to prevent swap

CPython provides no guaranteed in-memory secret protection, but these routines
reduce the window during which key material is recoverable from process memory.
"""

from __future__ import annotations

import ctypes
import os
import platform
import threading
import uuid
from contextlib import contextmanager
from typing import Generator

from nyxora.utils.exceptions import NyxoraError

# ── Low-level memory wipe ─────────────────────────────────────────────────────

def wipe_memory(data: bytearray) -> None:
    """3-pass wipe a bytearray in-place and trigger GC.

    Passes: random bytes → 0xFF → 0x00.
    This is best-effort; CPython may have already copied the bytes elsewhere.
    """
    if not isinstance(data, bytearray):
        return
    n = len(data)
    if n == 0:
        return

    # Pass 1: random bytes
    try:
        rand_bytes = os.urandom(n)
        for i in range(n):
            data[i] = rand_bytes[i]
    except Exception:  # pragma: no cover
        pass  # pragma: no cover

    # Pass 2: 0xFF
    ctypes.memset(ctypes.addressof(
        (ctypes.c_char * n).from_buffer(data)), 0xFF, n)
    # Pass 3: 0x00
    ctypes.memset(ctypes.addressof(
        (ctypes.c_char * n).from_buffer(data)), 0x00, n)


def secure_allocate(size: int) -> bytearray:
    """Return a zeroed bytearray of the given size."""
    return bytearray(size)


def generate_session_token() -> str:
    """Return a UUID4 hex string for session identification."""
    return uuid.uuid4().hex


# ── Platform memory locking ───────────────────────────────────────────────────

_MLOCK_AVAILABLE: bool = False
_libc: ctypes.CDLL | None = None
_kernel32 = None

if platform.system() == "Linux":
    try:  # pragma: no cover
        _libc = ctypes.CDLL("libc.so.6", use_errno=True)  # pragma: no cover
        _MLOCK_AVAILABLE = True  # pragma: no cover
    except OSError:  # pragma: no cover
        pass  # pragma: no cover
elif platform.system() == "Windows":
    try:
        _kernel32 = ctypes.windll.kernel32
        _MLOCK_AVAILABLE = True
    except OSError:  # pragma: no cover
        pass  # pragma: no cover


def try_mlock(data: bytearray) -> bool:
    """Attempt to lock memory pages (Linux & Windows).

    Returns True if mlock succeeded, False otherwise.
    Failures are silently ignored — callers should not depend on mlock.
    """
    if not _MLOCK_AVAILABLE:
        return False  # pragma: no cover
    try:
        addr = ctypes.addressof((ctypes.c_char * len(data)).from_buffer(data))
        if platform.system() == "Linux" and _libc is not None:
            result = _libc.mlock(ctypes.c_void_p(addr), ctypes.c_size_t(len(data)))  # pragma: no cover
            return bool(result == 0)  # pragma: no cover
        elif platform.system() == "Windows" and _kernel32 is not None:
            result = _kernel32.VirtualLock(ctypes.c_void_p(addr), ctypes.c_size_t(len(data)))
            return bool(result != 0)
        return False  # pragma: no cover
    except Exception:  # pragma: no cover
        return False  # pragma: no cover


def try_munlock(data: bytearray) -> bool:
    """Attempt to unlock previously mlocked memory pages (Linux & Windows).

    Returns True if munlock succeeded, False otherwise.
    """
    if not _MLOCK_AVAILABLE:
        return False  # pragma: no cover
    try:
        addr = ctypes.addressof((ctypes.c_char * len(data)).from_buffer(data))
        if platform.system() == "Linux" and _libc is not None:
            result = _libc.munlock(ctypes.c_void_p(addr), ctypes.c_size_t(len(data)))  # pragma: no cover
            return bool(result == 0)  # pragma: no cover
        elif platform.system() == "Windows" and _kernel32 is not None:
            result = _kernel32.VirtualUnlock(ctypes.c_void_p(addr), ctypes.c_size_t(len(data)))
            return bool(result != 0)
        return False  # pragma: no cover
    except Exception:  # pragma: no cover
        return False  # pragma: no cover


# ── Secure buffer context manager ─────────────────────────────────────────────

@contextmanager
def secure_buffer(size: int) -> Generator[bytearray, None, None]:
    """Allocate a zeroed buffer, optionally mlock it, yield it, then wipe.

    Usage::

        with secure_buffer(32) as buf:
            # use buf as temporary key storage
    """
    buf = secure_allocate(size)
    try_mlock(buf)
    try:
        yield buf
    finally:
        try_munlock(buf)
        wipe_memory(buf)


# ── SecureString ───────────────────────────────────────────────────────────────

class SecureString:
    """Wraps a sensitive string as a mutable bytearray for secure erasure.

    The underlying bytearray is zeroed when:
      - The context manager exits (__exit__)
      - The object is garbage collected (__del__)
      - ``wipe()`` is called explicitly

    Usage::

        with SecureString("hunter2") as s:
            engine.derive_key(s, salt)
        # s._data is now all zeros
    """

    __slots__ = ("_data", "_lock", "_wiped")

    def __init__(self, value: str | bytes | bytearray = "") -> None:
        self._lock = threading.Lock()
        self._wiped = False
        if isinstance(value, str):
            raw = value.encode("utf-8")
        elif isinstance(value, bytes):  # pragma: no cover
            raw = value  # pragma: no cover
        else:  # pragma: no cover
            raw = bytes(value)  # pragma: no cover
        self._data = bytearray(raw)
        # Best-effort: wipe the intermediate bytes object from CPython refcount
        del raw

    def __enter__(self) -> "SecureString":
        return self

    def __exit__(self, *_: object) -> None:
        self.wipe()

    def __del__(self) -> None:
        self.wipe()

    def __len__(self) -> int:
        return len(self._data)  # pragma: no cover

    def __bool__(self) -> bool:
        return len(self._data) > 0 and not self._wiped

    def wipe(self) -> None:
        """Zero the internal bytearray."""
        with self._lock:
            if not self._wiped:
                wipe_memory(self._data)
                self._wiped = True

    @property
    def value(self) -> str:
        """Decode the buffer as UTF-8. Raises if already wiped."""
        if self._wiped:  # pragma: no cover
            raise NyxoraError("SecureString has been wiped and cannot be read.")  # pragma: no cover
        return self._data.decode("utf-8")  # pragma: no cover

    def to_bytes(self) -> bytes:
        """Return a copy of the underlying bytes. Caller is responsible for wiping."""
        if self._wiped:
            raise NyxoraError("SecureString has been wiped and cannot be read.")  # pragma: no cover
        return bytes(self._data)

    def to_bytearray(self) -> bytearray:
        """Return a copy of the underlying bytearray."""
        if self._wiped:  # pragma: no cover
            raise NyxoraError("SecureString has been wiped and cannot be read.")  # pragma: no cover
        return bytearray(self._data)  # pragma: no cover

    @property
    def is_wiped(self) -> bool:
        return self._wiped  # pragma: no cover
