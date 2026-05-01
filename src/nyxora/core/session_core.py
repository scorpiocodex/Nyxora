"""Session management for NYXORA.

Holds the root key securely in memory, enforces inactivity timeouts,
and implements a progressive brute-force lockout ladder.
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid

from nyxora.core.memory_guard import generate_session_token, wipe_memory
from nyxora.utils.exceptions import BruteForceLockedError, VaultLockedError

# Lockout ladder: {fail_count_threshold: lockout_seconds}
LOCKOUT_LADDER: dict[int, int] = {
    3: 5,
    5: 30,
    7: 300,
    10: 1800,
    15: 86400,
}

DEFAULT_INACTIVITY_TIMEOUT: int = 300  # 5 minutes


class SessionManager:
    """In-memory session for an unlocked NYXORA vault.

    The root key is held as a ``bytearray`` under a ``threading.Lock``.
    It is NEVER written to disk. Locking the session wipes the key in-place.
    """

    def __init__(self, inactivity_timeout: int = DEFAULT_INACTIVITY_TIMEOUT) -> None:
        self._lock = threading.Lock()
        self._root_key: bytearray | None = None
        self._session_id: str | None = None
        self._terminal_hash: str = self._compute_terminal_hash()

        self._failed_attempts: int = 0
        self._lockout_until: float = 0.0

        self._last_activity: float = 0.0
        self._inactivity_timeout = inactivity_timeout
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running: bool = False

    # ── Unlock / Lock ──────────────────────────────────────────────────────

    def unlock(
        self, root_key: bytearray, session_token: str | None = None
    ) -> str:
        """Store the root key and start the inactivity monitor.

        Returns the session_id.
        Raises :class:`BruteForceLockedError` if currently locked out.
        """
        self._check_lockout()

        with self._lock:
            # Wipe any existing key
            if self._root_key is not None:
                wipe_memory(self._root_key)

            self._root_key = bytearray(root_key)
            self._session_id = session_token or generate_session_token()
            self._last_activity = time.time()

        self._start_inactivity_monitor()
        return self._session_id  # type: ignore[return-value]

    def lock(self, reason: str = "manual") -> None:
        """Wipe the root key from memory and stop the inactivity monitor."""
        with self._lock:
            self._running = False
            if self._root_key is not None:
                wipe_memory(self._root_key)
                self._root_key = None
            self._session_id = None

    def panic_lock(self) -> None:
        """Immediate wipe, clear all state. No cleanup — fast and brutal."""
        with self._lock:
            self._running = False
            if self._root_key is not None:
                wipe_memory(self._root_key)
                self._root_key = None
            self._session_id = None
            self._failed_attempts = 0
            self._lockout_until = 0.0

    def is_locked(self) -> bool:
        """Return True if no root key is held in memory."""
        with self._lock:
            return self._root_key is None

    def get_root_key(self) -> bytearray:
        """Return a reference to the in-memory root key.

        Raises :class:`VaultLockedError` if session is locked.
        Updates last_activity timestamp.
        """
        with self._lock:
            if self._root_key is None:
                raise VaultLockedError()
            self._last_activity = time.time()
            return self._root_key

    def get_session_id(self) -> str | None:
        """Return the current session ID, or None if locked."""
        with self._lock:
            return self._session_id

    # ── Brute-force protection ─────────────────────────────────────────────

    def record_failed_attempt(self) -> None:
        """Increment the failed-attempt counter and apply lockout if needed."""
        with self._lock:
            self._failed_attempts += 1
            count = self._failed_attempts

        lockout = self._get_lockout_for(count)
        if lockout > 0:
            with self._lock:
                self._lockout_until = time.time() + lockout

    def record_successful_unlock(self) -> None:
        """Reset the failed-attempt counter on a successful authentication."""
        with self._lock:
            self._failed_attempts = 0
            self._lockout_until = 0.0

    def _get_lockout_for(self, count: int) -> int:
        """Return the lockout duration for the given failure count."""
        result = 0
        for threshold, duration in sorted(LOCKOUT_LADDER.items()):
            if count >= threshold:
                result = duration
        return result

    def _check_lockout(self) -> None:
        """Raise BruteForceLockedError if currently in a lockout period."""
        with self._lock:
            lockout_until = self._lockout_until

        remaining = lockout_until - time.time()
        if remaining > 0:
            raise BruteForceLockedError(lockout_seconds=int(remaining))

    def get_failed_attempts(self) -> int:
        with self._lock:
            return self._failed_attempts

    def get_lockout_remaining(self) -> float:
        """Seconds remaining in lockout, or 0 if not locked."""
        with self._lock:
            remaining = self._lockout_until - time.time()
        return max(0.0, remaining)

    # ── Inactivity monitor ─────────────────────────────────────────────────

    def _start_inactivity_monitor(self) -> None:
        """Start (or restart) the daemon thread that auto-locks on inactivity."""
        with self._lock:
            self._running = True
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                return  # already running

        def _monitor() -> None:
            while True:
                time.sleep(5)  # check every 5 seconds
                with self._lock:
                    if not self._running:
                        break
                    if self._root_key is None:
                        break  # pragma: no cover
                    elapsed = time.time() - self._last_activity
                if elapsed >= self._inactivity_timeout:
                    self.lock(reason="inactivity")  # pragma: no cover
                    break  # pragma: no cover

        self._monitor_thread = threading.Thread(
            target=_monitor,
            daemon=True,
            name="nyxora-inactivity-monitor",
        )
        self._monitor_thread.start()

    def _compute_terminal_hash(self) -> str:
        """Fingerprint for session binding: Machine Node + User + Session Id."""
        node = uuid.getnode()
        user = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))
        sess = os.environ.get("SESSIONNAME", os.environ.get("XDG_SESSION_ID", "local"))
        raw = f"{node}:{user}:{sess}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @property
    def terminal_hash(self) -> str:
        return self._terminal_hash
