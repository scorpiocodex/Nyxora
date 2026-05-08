"""YAML configuration with environment variable override for NYXORA.

Default paths:
  - Windows: %APPDATA%/nyxora/config.yaml
  - Linux/Mac: $XDG_CONFIG_HOME/nyxora/config.yaml (fallback: ~/.config/nyxora/config.yaml)

Environment overrides (take precedence over config file):
  - NYX_VAULT_PATH   → vault.default_path
  - NYX_TIMEOUT      → vault.timeout
  - NYX_KDF_MODE     → crypto.kdf_mode
  - NYX_DEBUG        → ui.debug
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import Any

import yaml

from nyxora.utils.exceptions import ConfigError

# ── Default configuration ──────────────────────────────────────────────────────

DEFAULT_CONFIG: dict[str, Any] = {
    "vault": {
        "default_path": None,       # set at runtime
        "timeout": 300,             # inactivity timeout in seconds
        "auto_lock": True,
        "backup_on_close": False,
    },
    "crypto": {
        "kdf_mode": "argon2id",     # argon2id | pbkdf2
        "argon2_memory": 262144,    # KiB
        "argon2_time": 4,
        "argon2_parallelism": 4,
        "default_algorithm": "xchacha20",  # xchacha20 | aesgcm
    },
    "generate": {
        "default_length": 24,
        "default_wordcount": 5,
        "include_uppercase": True,
        "include_digits": True,
        "include_symbols": True,
        "symbol_set": "!@#$%^&*()-_=+",
        "separator": "-",
    },
    "intel": {
        "hibp_enabled": True,
        "hibp_timeout": 10,
        "offline_db_path": None,
        "entropy_warn_below": 60,
    },
    "ui": {
        "color": True,
        "debug": False,
        "show_passwords": False,
    },
    "backup": {
        "directory": None,
        "keep_count": 10,
        "auto_backup": False,
    },
    "update": {
        "channel": "stable",          # stable | pre-release
        "check_on_startup": True,
        "check_interval_hours": 24,
    },
}

# Allowed top-level sections and their value types (for validation)
_ALLOWED_SECTIONS: set[str] = set(DEFAULT_CONFIG.keys())


class Config:
    """YAML configuration manager with environment variable overrides."""

    def __init__(self, config_path: Path | None = None) -> None:
        if config_path is not None:
            self._path = config_path
        else:
            self._path = self._default_path()
        self._data: dict[str, Any] = {}
        self._loaded = False

    @staticmethod
    def _default_path() -> Path:
        system = platform.system()
        if system == "Windows":
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            return Path(appdata) / "nyxora" / "config.yaml"
        else:
            xdg = os.environ.get("XDG_CONFIG_HOME", "")  # pragma: no cover
            base = Path(xdg) if xdg else Path.home() / ".config"  # pragma: no cover
            return base / "nyxora" / "config.yaml"  # pragma: no cover

    def load(self) -> None:
        """Load configuration from disk, merging with defaults."""
        import copy
        self._data = copy.deepcopy(DEFAULT_CONFIG)

        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    file_data = yaml.safe_load(f) or {}
                self._deep_merge(self._data, file_data)
            except yaml.YAMLError as exc:  # pragma: no cover
                raise ConfigError(f"Failed to parse config file: {exc}") from exc  # pragma: no cover
            except OSError as exc:  # pragma: no cover
                raise ConfigError(f"Failed to read config file: {exc}") from exc  # pragma: no cover

        self._apply_env_overrides()
        self._loaded = True
        self.validate()

    def save(self) -> None:
        """Persist current configuration to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)
        except OSError as exc:  # pragma: no cover
            raise ConfigError(f"Failed to write config file: {exc}") from exc  # pragma: no cover

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by dot-notation key (e.g., 'vault.timeout').

        Auto-loads if not yet loaded.
        """
        if not self._loaded:
            self.load()

        parts = key.split(".")
        node: Any = self._data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any) -> None:
        """Set a value by dot-notation key. Auto-loads if not yet loaded."""
        if not self._loaded:
            self.load()

        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def validate(self) -> None:
        """Validate configuration structure and types.

        Raises :class:`ConfigError` on unknown sections or invalid types.
        """
        if not self._loaded:
            self.load()  # pragma: no cover

        for key in self._data:
            if key not in _ALLOWED_SECTIONS:
                raise ConfigError(  # pragma: no cover
                    f"Unknown configuration section: '{key}'. "
                    f"Allowed: {sorted(_ALLOWED_SECTIONS)}"
                )

        # Type checks
        timeout = self.get("vault.timeout")
        if timeout is not None and not isinstance(timeout, int):
            raise ConfigError("vault.timeout must be an integer.")

        kdf_mode = self.get("crypto.kdf_mode")
        if kdf_mode not in ("argon2id", "pbkdf2"):
            raise ConfigError("crypto.kdf_mode must be 'argon2id' or 'pbkdf2'.")  # pragma: no cover

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides directly to _data (no self.set to avoid recursion)."""
        vault_path = os.environ.get("NYX_VAULT_PATH")
        if vault_path:
            self._data.setdefault("vault", {})["default_path"] = vault_path  # pragma: no cover

        timeout = os.environ.get("NYX_TIMEOUT")
        if timeout:
            try:
                self._data.setdefault("vault", {})["timeout"] = int(timeout)
            except ValueError:  # pragma: no cover
                pass  # silently ignore invalid env var  # pragma: no cover

        kdf_mode = os.environ.get("NYX_KDF_MODE")
        if kdf_mode and kdf_mode in ("argon2id", "pbkdf2"):
            self._data.setdefault("crypto", {})["kdf_mode"] = kdf_mode  # pragma: no cover

        debug = os.environ.get("NYX_DEBUG")
        if debug:
            self._data.setdefault("ui", {})["debug"] = debug.lower() in ("1", "true", "yes")

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
        """Recursively merge override into base."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                Config._deep_merge(base[key], value)
            else:
                base[key] = value

    @property
    def path(self) -> Path:
        return self._path  # pragma: no cover
