"""Auto-update engine for NYXORA.

Checks GitHub Releases API for newer versions, downloads the wheel,
verifies its SHA-256 checksum, and installs via pip.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests
from packaging.version import Version

from nyxora import __version__
from nyxora.utils.exceptions import NyxoraError

# ── Constants ──────────────────────────────────────────────────────────────────

GITHUB_API_BASE = "https://api.github.com/repos/scorpiocodex/Nyxora/releases"
GITHUB_LATEST   = f"{GITHUB_API_BASE}/latest"
REQUEST_TIMEOUT = 10  # seconds
STATE_FILE      = Path.home() / ".nyxora" / "update_state.json"


class UpdateError(NyxoraError):
    """Update operation failed."""
    user_message = "Update operation failed."


# ── State persistence ──────────────────────────────────────────────────────────

def _load_state() -> dict[str, Any]:
    """Load persisted update state (last check time, cached release info)."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict[str, Any]) -> None:
    """Persist update state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOINHERIT"):
        flags |= getattr(os, "O_NOINHERIT")
    fd = os.open(str(STATE_FILE), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(state, indent=2))


# ── Release fetching ───────────────────────────────────────────────────────────

def fetch_latest_release(channel: str = "stable") -> dict[str, Any] | None:
    """Fetch the latest release from GitHub.

    Args:
        channel: "stable" (latest non-prerelease) or "pre-release" (any)

    Returns:
        Release dict from GitHub API, or None on network error.
    """
    try:
        if channel == "stable":
            resp = requests.get(GITHUB_LATEST, timeout=REQUEST_TIMEOUT,
                                headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code == 200:
                return resp.json()
            return None
        else:
            # pre-release: fetch all releases, take the first one
            resp = requests.get(GITHUB_API_BASE, timeout=REQUEST_TIMEOUT,
                                headers={"Accept": "application/vnd.github.v3+json"})
            if resp.status_code == 200:
                releases = resp.json()
                return releases[0] if releases else None
            return None
    except Exception:
        return None


def is_newer(release: dict[str, Any]) -> bool:
    """Return True if the release version is newer than the installed version."""
    tag = release.get("tag_name", "").lstrip("v")
    if not tag:
        return False
    try:
        return Version(tag) > Version(__version__)
    except Exception:
        return False


def get_wheel_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    """Find the .whl asset in a release, preferring py3-none-any."""
    assets = release.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if name.endswith(".whl"):
            return asset
    return None


def get_checksums_asset(release: dict[str, Any]) -> dict[str, Any] | None:
    """Find a sha256sums.txt asset in a release."""
    for asset in release.get("assets", []):
        if asset.get("name", "").lower() in ("sha256sums.txt", "checksums.txt"):
            return asset
    return None


# ── Download + verify ──────────────────────────────────────────────────────────

def download_asset(url: str, dest: Path) -> Path:
    """Download a GitHub release asset to dest. Returns dest path."""
    headers = {"Accept": "application/octet-stream"}
    resp = requests.get(url, headers=headers, stream=True,
                        timeout=REQUEST_TIMEOUT * 3)
    if resp.status_code != 200:
        raise UpdateError(f"Download failed: HTTP {resp.status_code}")

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
    return dest


def compute_sha256(path: Path) -> str:
    """Return the hex SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_checksum(wheel_path: Path, checksums_text: str) -> bool:
    """Verify wheel SHA-256 against a checksums file.

    The checksums file format is one line per file:
        <sha256hex>  <filename>
    Returns True if the wheel's hash matches, False if not found/mismatch.
    """
    wheel_name = wheel_path.name
    actual = compute_sha256(wheel_path)
    for line in checksums_text.splitlines():
        parts = line.strip().split()
        if len(parts) == 2 and parts[1] == wheel_name:
            return parts[0].lower() == actual.lower()
    return False


# ── Install + rollback ─────────────────────────────────────────────────────────

def install_wheel(wheel_path: Path) -> tuple[bool, str]:
    """Install a wheel using the current Python executable's pip.

    Returns (success, output_message).
    """
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", str(wheel_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, result.stderr.strip()


def save_rollback_version(version: str) -> None:
    """Store the current version for potential rollback."""
    state = _load_state()
    state["rollback_version"] = version
    state["rollback_timestamp"] = int(time.time())
    _save_state(state)


def get_rollback_version() -> str | None:
    """Return the stored rollback version, if any."""
    return _load_state().get("rollback_version")


def rollback_to_previous() -> tuple[bool, str]:
    """Attempt to reinstall the previous version via pip.

    Returns (success, message).
    """
    prev = get_rollback_version()
    if not prev:
        return False, "No rollback version stored."
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", f"nyxora=={prev}"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, f"Rolled back to v{prev}"
    return False, (
        f"pip rollback failed. Try manually:\n"
        f"  pip install nyxora=={prev}\n"
        f"or reinstall from: https://github.com/scorpiocodex/Nyxora/releases/tag/v{prev}"
    )


# ── Startup check ──────────────────────────────────────────────────────────────

def should_check_now(interval_hours: int = 24) -> bool:
    """Return True if enough time has passed since the last update check."""
    state = _load_state()
    last = state.get("last_check", 0)
    return (time.time() - last) >= (interval_hours * 3600)


def record_check_time() -> None:
    """Record that a check was performed right now."""
    state = _load_state()
    state["last_check"] = int(time.time())
    _save_state(state)


def background_check(channel: str = "stable") -> str | None:
    """Check for updates silently.

    Returns a notification string if an update is available, None otherwise.
    Designed to be called from a daemon thread — never raises.
    """
    try:
        if not should_check_now():
            return None
        record_check_time()
        release = fetch_latest_release(channel)
        if release and is_newer(release):
            tag = release.get("tag_name", "")
            return f"Update available: {tag}  — run 'nyx update install'"
        return None
    except Exception:
        return None
