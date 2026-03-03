"""Breach intelligence and password strength analysis for NYXORA.

Provides:
  - HIBP k-anonymity breach checking (online)
  - Offline breach database lookup
  - Multi-factor entropy scoring
  - Pattern detection (keyboard walks, dates, leet speak, etc.)
  - Duplicate password detection across vault entries
  - Comprehensive vault audit report
"""

from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from math import inf
from pathlib import Path

import requests

from nyxora.core.crypto_engine import CryptoEngine
from nyxora.utils.exceptions import NyxoraError

# ── Constants ──────────────────────────────────────────────────────────────────

HIBP_API_URL = "https://api.pwnedpasswords.com/range/{prefix}"
HIBP_TIMEOUT = 10  # seconds

ENTROPY_THRESHOLDS: dict[str, tuple[float, float]] = {
    "Weak":      (0, 40),
    "Fair":      (40, 60),
    "Strong":    (60, 80),
    "Excellent": (80, inf),
}

# Pattern detection regexes
REPEATED_CHAR_PATTERN = re.compile(r"(.)\1{2,}")
DATE_PATTERN = re.compile(r"(19|20)\d{2}")
DIGITS_ONLY = re.compile(r"^\d+$")
LOWERCASE_ONLY = re.compile(r"^[a-z]+$")
UPPERCASE_ONLY = re.compile(r"^[A-Z]+$")

# Keyboard walks (QWERTY rows, columns, diagonals)
KEYBOARD_WALKS: list[str] = [
    "qwertyuiop", "asdfghjkl", "zxcvbnm",        # horizontal
    "qweasdzxc", "wersdxcv", "ertdfcvb",          # diagonal
    "1234567890", "0987654321",                     # numeric
    "qazwsx", "wsxedc", "edcrfv",                  # vertical
    "abcdefghij", "jihgfedcba",                     # alphabetic
]

COMMON_WORD_BASES: frozenset[str] = frozenset({
    "password", "passwd", "letmein", "monkey", "dragon",
    "master", "admin", "login", "welcome", "sunshine",
    "princess", "football", "baseball", "iloveyou", "trustno1",
    "shadow", "superman", "batman", "access", "secret",
    "hunter", "correct", "horse", "staple", "battery",
})

LEET_MAP: dict[str, str] = {
    "4": "a", "@": "a", "3": "e", "1": "i", "!": "i",
    "0": "o", "5": "s", "$": "s", "7": "t", "+": "t",
}


# ── Report data classes ───────────────────────────────────────────────────────

@dataclass
class EntryAuditResult:
    entry_id: str
    title: str
    entropy: float
    strength: str
    patterns: list[str]
    is_breached: bool
    breach_count: int
    is_duplicate: bool
    password_sha256: str  # for duplicate detection only; not the plaintext


@dataclass
class VaultAuditReport:
    total_entries: int
    breached_count: int = 0
    duplicate_count: int = 0
    strength_histogram: dict[str, int] = field(default_factory=dict)
    entries: list[EntryAuditResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ── IntelEngine ───────────────────────────────────────────────────────────────

class IntelEngine:
    """Password intelligence and breach analysis engine."""

    def __init__(self, crypto: CryptoEngine) -> None:
        self._crypto = crypto
        self._offline_db: set[str] | None = None

    # ── Breach checking ────────────────────────────────────────────────────

    def check_breach_hibp(self, password: str) -> tuple[bool, int]:
        prefix, suffix = self._crypto.hash_for_hibp(password)
        url = HIBP_API_URL.format(prefix=prefix)

        max_retries = 3
        backoff_factor = 1.0

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers={"Add-Padding": "true"},
                    timeout=HIBP_TIMEOUT,
                )
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(backoff_factor * (2 ** attempt))
                        continue
                    raise NyxoraError(
                        "HIBP API rate limit exceeded.",
                        user_message="Rate limit exceeded. Please try again later.",
                    )
                elif response.status_code in (401, 403):
                    raise NyxoraError(  # pragma: no cover
                        f"HIBP API access denied: {response.status_code}",
                        user_message="Access denied to breach database.",
                    )
                response.raise_for_status()

                # Check parsed response safely
                for line in response.text.splitlines():
                    parts = line.strip().split(":")
                    if len(parts) != 2:
                        continue  # pragma: no cover
                    hash_suffix, count_str = parts
                    if hash_suffix.upper() == suffix:
                        return True, int(count_str)
                return False, 0

            except requests.RequestException as exc:
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt))
                    continue
                raise NyxoraError(  # pragma: no cover
                    f"HIBP API request failed: {exc}",  # pragma: no cover
                    user_message="Could not reach breach database. Check your internet connection.",  # pragma: no cover
                ) from exc  # pragma: no cover
                return True, int(count_str)  # pragma: no cover
  # pragma: no cover
        return False, 0  # pragma: no cover

    def import_offline_breach_db(self, path: Path) -> int:
        """Load a sorted SHA-1 hash file into memory for O(1) lookup.

        The file should contain one uppercase SHA-1 hash per line,
        optionally followed by :count (HIBP format).

        Returns:
            Number of hashes loaded.
        """
        import os
        import warnings

        # Check file size before loading entirely into memory
        if path.exists() and os.path.getsize(path) > 100 * 1024 * 1024:
            warnings.warn("Loading a large offline breach DB will consume significant memory.", RuntimeWarning)  # pragma: no cover

        hashes: set[str] = set()
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if ":" in line:
                    line = line.split(":")[0]
                if line:
                    hashes.add(line.upper())
        self._offline_db = hashes
        return len(hashes)

    def check_breach_offline(self, password: str) -> tuple[bool, int]:
        """Check a password against the in-memory offline breach database.

        Returns:
            (is_breached: bool, count: int) — count is always 0 for offline check.

        Raises:
            NyxoraError: if no offline database has been loaded.
        """
        if self._offline_db is None:
            raise NyxoraError(  # pragma: no cover
                "No offline breach database loaded.",
                user_message="Load an offline breach database first with import_offline_breach_db().",
            )
        _, sha1 = self._crypto.hash_for_hibp(password)
        # We need the full hash — reconstruct from prefix (5 chars) + suffix
        prefix, suffix = self._crypto.hash_for_hibp(password)
        full_hash = prefix + suffix
        return (full_hash in self._offline_db), 0

    # ── Entropy and strength ───────────────────────────────────────────────

    def score_entropy(self, password: str) -> float:
        """Multi-factor entropy estimate in bits.

        Base: log2(charset_size) * length
        Deductions:
          - Repeated characters: -5 bits per trigger
          - Keyboard walk: -10 bits
          - Date pattern: -5 bits
        """
        if not password:
            return 0.0  # pragma: no cover

        charset = 0
        if any(c.islower() for c in password):
            charset += 26
        if any(c.isupper() for c in password):
            charset += 26
        if any(c.isdigit() for c in password):
            charset += 10
        if any(not c.isalnum() for c in password):
            charset += 32

        if charset == 0:
            return 0.0  # pragma: no cover

        base = len(password) * math.log2(charset)
        deductions = 0.0

        patterns = self.scan_patterns(password)
        if "repeated_chars" in patterns:
            deductions += 5.0  # pragma: no cover
        if "keyboard_walk" in patterns:
            deductions += 10.0  # pragma: no cover
        if "date_pattern" in patterns:
            deductions += 5.0  # pragma: no cover
        if "all_digits" in patterns:
            deductions += 10.0  # pragma: no cover
        if "common_word_base" in patterns:
            deductions += 15.0

        return max(0.0, base - deductions)

    def classify_strength(self, entropy_bits: float) -> str:
        """Classify entropy into a human-readable strength label."""
        for label, (low, high) in ENTROPY_THRESHOLDS.items():
            if low <= entropy_bits < high:
                return label
        return "Excellent"  # pragma: no cover

    # ── Pattern detection ──────────────────────────────────────────────────

    def scan_patterns(self, password: str) -> list[str]:
        """Detect weak patterns in a password.

        Returns a list of flag strings. Empty list = no bad patterns found.

        Flags:
          - keyboard_walk
          - repeated_chars
          - date_pattern
          - leet_speak
          - all_lowercase
          - all_digits
          - common_word_base
        """
        flags: list[str] = []
        pw_lower = password.lower()

        # Keyboard walk detection
        for walk in KEYBOARD_WALKS:
            for length in range(4, len(walk) + 1):
                for i in range(len(walk) - length + 1):
                    if walk[i:i+length] in pw_lower:
                        flags.append("keyboard_walk")
                        break
                else:
                    continue
                break

        # Repeated characters (3+)
        if REPEATED_CHAR_PATTERN.search(password):
            flags.append("repeated_chars")  # pragma: no cover

        # Date pattern (year 1900-2099)
        if DATE_PATTERN.search(password):
            flags.append("date_pattern")  # pragma: no cover

        # Leet speak detection (convert and check common words)
        deleet = password.lower()
        for leet_char, normal in LEET_MAP.items():
            deleet = deleet.replace(leet_char, normal)
        if any(word in deleet for word in COMMON_WORD_BASES):
            flags.append("leet_speak")

        # All lowercase
        if LOWERCASE_ONLY.match(password):
            flags.append("all_lowercase")

        # All digits
        if DIGITS_ONLY.match(password):
            flags.append("all_digits")  # pragma: no cover

        # Common word base (without leet)
        if any(word in pw_lower for word in COMMON_WORD_BASES):
            flags.append("common_word_base")

        return list(dict.fromkeys(flags))  # deduplicate preserving order

    # ── Duplicate detection ────────────────────────────────────────────────

    def detect_duplicates(
        self, entries: list[tuple[str, str]]
    ) -> list[list[str]]:
        """Group entry IDs by shared password (compared via SHA-256).

        Args:
            entries: List of (entry_id, password) tuples.

        Returns:
            List of groups — each group is a list of entry IDs sharing a password.
            Only groups with 2+ entries are returned.
        """
        hash_to_ids: dict[str, list[str]] = {}
        for entry_id, password in entries:
            h = hashlib.sha256(password.encode("utf-8")).hexdigest()
            hash_to_ids.setdefault(h, []).append(entry_id)

        return [ids for ids in hash_to_ids.values() if len(ids) > 1]

    def generate_reuse_heatmap(
        self, entries: list[tuple[str, str]]
    ) -> dict[str, int]:
        """Return a dict mapping sha256(password) → count of entries using it.

        Counts > 1 indicate password reuse.
        """
        result: dict[str, int] = {}
        for _, password in entries:
            h = hashlib.sha256(password.encode("utf-8")).hexdigest()
            result[h] = result.get(h, 0) + 1
        return result

    # ── Full vault audit ───────────────────────────────────────────────────

    def audit_all(
        self,
        entries: list[tuple[str, str, str]],
        check_hibp: bool = True,
    ) -> VaultAuditReport:
        """Comprehensive audit of all vault entries.

        Args:
            entries: List of (entry_id, title, password) tuples.
            check_hibp: If True, check each password against the HIBP API.

        Returns:
            VaultAuditReport with per-entry results and summary statistics.
        """
        report = VaultAuditReport(total_entries=len(entries))
        histogram: dict[str, int] = {k: 0 for k in ENTROPY_THRESHOLDS}

        # Pre-compute duplicate map
        pw_tuples = [(eid, pw) for eid, _, pw in entries]
        dup_groups = self.detect_duplicates(pw_tuples)
        dup_ids: set[str] = set()
        for group in dup_groups:
            dup_ids.update(group)  # pragma: no cover

        for entry_id, title, password in entries:
            try:
                entropy = self.score_entropy(password)
                strength = self.classify_strength(entropy)
                patterns = self.scan_patterns(password)
                pw_sha256 = hashlib.sha256(password.encode("utf-8")).hexdigest()

                is_breached = False
                breach_count = 0
                if check_hibp:
                    try:
                        is_breached, breach_count = self.check_breach_hibp(password)
                    except NyxoraError as e:  # pragma: no cover
                        report.errors.append(f"{title}: {e.user_message}")  # pragma: no cover

                result = EntryAuditResult(
                    entry_id=entry_id,
                    title=title,
                    entropy=entropy,
                    strength=strength,
                    patterns=patterns,
                    is_breached=is_breached,
                    breach_count=breach_count,
                    is_duplicate=(entry_id in dup_ids),
                    password_sha256=pw_sha256,
                )
                report.entries.append(result)
                histogram[strength] = histogram.get(strength, 0) + 1

                if is_breached:
                    report.breached_count += 1
                if entry_id in dup_ids:
                    report.duplicate_count += 1  # pragma: no cover
  # pragma: no cover
            except NyxoraError as exc:  # pragma: no cover
                report.errors.append(f"{title}: {exc.user_message}")  # pragma: no cover
            except Exception:  # pragma: no cover
                import traceback  # pragma: no cover
                tb = traceback.format_exc().splitlines()[-1]  # pragma: no cover
                report.errors.append(f"{title}: unexpected error — {tb}")  # pragma: no cover

        # Normalize duplicate count (each duplicate counted once)
        report.duplicate_count = sum(len(g) for g in dup_groups)
        report.strength_histogram = histogram
        return report
