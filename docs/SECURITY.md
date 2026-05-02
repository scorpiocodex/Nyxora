# NYXORA Security Model

## Threat Model

Nyxora protects against:
- Offline attacks on the vault file (Argon2id with 256 MB memory cost)
- Memory forensics (SecureString, 3-pass wipe, mlock/VirtualLock)
- Vault tampering (3-layer HMAC: per-entry, vault-wide, schema fingerprint)
- Timing attacks on HMAC verification (hmac.compare_digest throughout)
- Brute-force login (progressive lockout: 3 failures → 5s, up to 24h at 15)
- Password reuse and weak passwords (entropy scoring, HIBP k-anonymity)

Nyxora does NOT protect against:
- Malware with root/SYSTEM access running concurrently
- Physical memory dumps while the vault is actively unlocked
- Compromise of the OS keyring (DPAPI on Windows)
- Loss of both the vault file and all recovery pathways simultaneously

## Cryptographic Primitives

| Purpose | Algorithm | Parameters |
|---|---|---|
| Key derivation | Argon2id | 256 MB memory, 4 iterations, 4 threads |
| Fallback KDF | PBKDF2-HMAC-SHA512 | 600,000 iterations |
| Per-entry key isolation | HKDF-SHA512 | unique info string per entry |
| Primary encryption | XChaCha20-Poly1305 | 192-bit nonce via libsodium |
| Secondary encryption | AES-256-GCM | OpenSSL backend |
| Integrity | HMAC-SHA512 | 3-layer chain |
| HIBP lookup | SHA-1 (k-anonymity) | first 5 hex chars only |

## Memory Safety

All sensitive values are held as `bytearray` objects.
`wipe_memory()` performs a 3-pass overwrite:
1. `os.urandom(n)` — randomise
2. `ctypes.memset(..., 0xFF, n)` — fill with 0xFF
3. `ctypes.memset(..., 0x00, n)` — zero

Platform memory locking: `VirtualLock` (Windows), `mlock` (Linux).
Root key is never written to disk — only its hex form is stored in the
OS keyring (DPAPI on Windows) for session persistence.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | General error |
| 2 | Vault locked |
| 3 | Brute-force lockout active |
| 4 | Panic — session destroyed |
