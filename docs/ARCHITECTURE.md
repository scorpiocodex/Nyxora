# NYXORA Architecture

## Layered Dependency Model

```
┌─────────────────────────────────────────────┐
│  CLI Layer  (Typer/Rich — commands/*)        │
│  main.py, ui.py                             │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│  Session Layer  (session_core.py)            │
│  SessionManager — holds root key in RAM      │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│  Business Layer                              │
│  IntelEngine — breach + entropy analysis     │
│  RecoveryManager — TOTP, capsule, Shamir     │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│  Storage Layer  (vault_store.py)             │
│  VaultStore — hardened SQLite + HMAC chain   │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│  Crypto Layer                                │
│  CryptoEngine — KDF, AEAD, HKDF, HMAC       │
│  MemoryGuard — SecureString, wipe_memory     │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│  Utils Layer                                 │
│  exceptions.py — custom exception hierarchy  │
│  config.py — YAML + env var configuration    │
└─────────────────────────────────────────────┘
```

**Rule**: No layer imports from a layer above it. No circular imports.

---

## Module Descriptions

### `src/nyxora/utils/exceptions.py`
Custom exception hierarchy. Every exception has a `user_message` (safe for display) and an `exit_code`. The CLI layer catches all `NyxoraError` subclasses before they reach the terminal.

### `src/nyxora/core/memory_guard.py`
Secure memory handling. `SecureString` wraps sensitive strings as mutable `bytearray`s. `wipe_memory()` performs 3-pass overwrite. `secure_buffer()` is a context manager that allocates, mlocks, and wipes.

### `src/nyxora/core/crypto_engine.py`
All cryptographic operations. Key derivation (Argon2id + PBKDF2), HKDF for per-purpose key isolation, XChaCha20-Poly1305 and AES-256-GCM encryption, HMAC-SHA512 computation and verification, entropy scoring, HIBP hash preparation.

### `src/nyxora/core/vault_store.py`
Hardened SQLite vault. Creates and manages the encrypted database with WAL journal, exclusive locking, and secure_delete. Enforces 3-layer integrity (per-entry HMAC → vault-wide HMAC → schema fingerprint). Maintains an encrypted audit log.

### `src/nyxora/core/session_core.py`
In-memory session management. Holds the root key as a `bytearray` under a `threading.Lock`. Enforces a progressive brute-force lockout ladder. Runs a daemon thread that auto-locks after inactivity.

### `src/nyxora/core/recovery_core.py`
Recovery pathways. TOTP (RFC 6238) via pyotp. Emergency recovery capsule (double-encrypted root key in a portable file). Shamir-like secret splitting using polynomial interpolation in GF(256).

### `src/nyxora/core/intel_engine.py`
Breach and strength intelligence. HIBP k-anonymity checks. Offline SHA-1 database lookup. Multi-factor entropy scoring with deductions for patterns (keyboard walks, dates, common words, leet speak, repeated chars). Duplicate detection via SHA-256 hashing.

### `src/nyxora/utils/config.py`
YAML configuration with environment variable overrides. Platform-aware default paths (`%APPDATA%/nyxora` on Windows, `~/.config/nyxora` on Linux/Mac). Dot-notation key access.

### `src/nyxora/cli/ui.py`
Rich terminal UI with a neon cyber theme. All output functions (`success_panel`, `error_panel`, `spinner`, `progress_bar`, `table_entries`, `forensic_panel`, `audit_table`). No `print()` calls anywhere else in the codebase.

### `src/nyxora/cli/main.py`
Typer app with 7 command groups registered. Global exception handler converts `NyxoraError` → styled panel + exit code. `pretty_exceptions_enable=False` prevents raw tracebacks.

---

## Data Flow: Vault Unlock

```
User enters password
        │
        ▼
SecureString wraps password
        │
        ▼
CryptoEngine.derive_key(password, salt, Argon2id)
   → 256-bit root_key (bytearray)
        │
        ▼
VaultStore.open(path, root_key)
   → verify schema fingerprint
   → verify vault-wide HMAC
   → returns (store ready for operations)
        │
        ▼
SessionManager.unlock(root_key)
   → stores key under threading.Lock
   → starts inactivity monitor thread
   → returns session_id
```

## Data Flow: Entry Storage

```
add_entry(title, password, ...)
        │
        ▼
entry_id = UUID4()
entry_salt = os.urandom(32)
entry_key = HKDF(root_key, info="nyxora:entry:<entry_id>")
        │
        ▼
encrypt_field(title, entry_key)     → EncryptedField
encrypt_field(password, entry_key)  → EncryptedField
...
        │
        ▼
entry_hmac = HMAC(hmac_key,
    entry_id || sorted(field_name || ciphertext))
        │
        ▼
INSERT INTO entries (...)
UPDATE vault_hmac in metadata
INSERT INTO audit_log (ADD event)
        │
        ▼
wipe_memory(entry_key)
```

---

## Database Schema

```sql
entries          -- encrypted fields + per-entry HMAC
metadata         -- vault_id, vault_hmac, schema_version, kdf_mode
audit_log        -- encrypted event log with HMAC per row
schema_fingerprint -- HMAC of all CREATE TABLE statements
```

---

## Dependency Matrix

| Module | Imports From |
|---|---|
| `exceptions.py` | (nothing) |
| `memory_guard.py` | `exceptions` |
| `crypto_engine.py` | `memory_guard`, `exceptions` |
| `vault_store.py` | `crypto_engine`, `memory_guard`, `exceptions` |
| `session_core.py` | `memory_guard`, `exceptions` |
| `recovery_core.py` | `crypto_engine`, `memory_guard`, `exceptions` |
| `intel_engine.py` | `crypto_engine`, `exceptions` |
| `config.py` | `exceptions` |
| `ui.py` | (standalone Rich wrapper) |
| `main.py` | `ui`, `config`, all command modules |
| Command modules | all core modules + `ui` + `config` |
