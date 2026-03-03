# NYXORA Security Model

## Threat Model

NYXORA is designed to protect password data against:

1. **Offline vault file access** — attacker obtains the vault file from disk
2. **Memory forensics** — attacker reads process memory after vault is locked
3. **Field-level tampering** — attacker modifies individual ciphertext fields
4. **Entry deletion/insertion** — attacker adds or removes entries without the key
5. **Structural tampering** — attacker modifies the SQLite schema
6. **Brute-force attacks** — attacker repeatedly attempts master passwords
7. **Breach exposure** — passwords reused from known breach lists

NYXORA does **not** protect against:
- A fully compromised system (root-level keyloggers, OS compromise)
- Social engineering attacks
- Physical coercion ("rubber-hose cryptanalysis")
- Side-channel attacks on the host OS
- Quantum computers with sufficient qubit counts (Argon2id is a classical algorithm)

---

## Cryptographic Specification

### Key Derivation

**Primary: Argon2id**
- Memory: 256 MB (262,144 KiB)
- Time cost: 4 iterations
- Parallelism: 4 threads
- Output: 256-bit key
- Salt: 256-bit random (stored alongside vault)

**Fallback: PBKDF2-HMAC-SHA512**
- Iterations: 600,000
- Output: 256-bit key

**Per-entry key isolation: HKDF-SHA512**
```
entry_key = HKDF(root_key, info="nyxora:entry:<entry_id>")
```
Each entry is encrypted with an independently derived key. A compromise of one entry key cannot cascade to others.

**Purpose-bound key derivation:**
- HMAC key: `HKDF(root_key, info="nyxora:hmac:vault")`
- Backup key: `HKDF(root_key, info="nyxora:backup:<backup_id>")`
- Locker key: `HKDF(root_key, info="nyxora:locker:<filename>")`

### Encryption

**Primary: XChaCha20-Poly1305**
- Nonce: 192-bit random (avoids birthday bounds vs 96-bit ChaCha20)
- Tag: 128-bit Poly1305 MAC
- Library: PyNaCl (libsodium bindings)

**Secondary: AES-256-GCM**
- Nonce: 96-bit random
- Tag: 128-bit GHASH MAC
- Library: cryptography (OpenSSL bindings)

### Integrity Model (Three Layers)

#### Layer 1: Per-entry HMAC
```
entry_hmac = HMAC-SHA512(hmac_key,
    entry_id || sorted(field_name || field_ciphertext))
```
Verified before any decryption. Catches:
- Individual field ciphertext tampering
- Field substitution attacks (swapping fields between entries)
- Entry identity swapping

#### Layer 2: Vault-wide HMAC
```
vault_hmac = HMAC-SHA512(hmac_key,
    concat_sorted(entry_id || entry_hmac for all active entries))
```
Stored in the `metadata` table. Verified on `open()`. Catches:
- Entry deletion (without proper vault update)
- Entry insertion (without the root key)
- Entry HMAC substitution

#### Layer 3: Schema Fingerprint
```
schema_fingerprint = HMAC-SHA512(hmac_key,
    sorted_CREATE_TABLE_statements)
```
Verified on `open()`. Catches:
- Structural modification of the SQLite schema
- Column addition/removal attempts

### Salt Storage

The 256-bit random salt is stored alongside the vault file (`.salt` extension). This is standard practice — security comes from key derivation strength (Argon2id), not salt secrecy. The salt prevents precomputed (rainbow table) attacks.

---

## Memory Security

### Best-effort Key Protection

NYXORA uses `bytearray` for all key material to enable in-place zeroing:

1. **3-pass wipe**: `os.urandom(n)` → `0xFF * n` → `0x00 * n`
2. **GC trigger**: `gc.collect()` after wipe
3. **mlock (Linux)**: Attempts to prevent swap-out via `mlock(2)`

**Limitations (CPython):**
- Python's garbage collector may have already copied key bytes before wipe
- `bytes` objects are immutable and cannot be zeroed in CPython
- The JIT compiler or interpreter may cache values
- These routines reduce but cannot eliminate the window during which keys are recoverable

### Session Key Storage

The root key is held exclusively in RAM as a `bytearray` under a `threading.Lock`. It is:
- Never serialized to disk in its raw form
- Wiped via 3-pass overwrite on lock/panic
- Never passed as a `str` or `bytes` internally

---

## Database Security

### Hardened SQLite PRAGMAs
```sql
PRAGMA journal_mode=WAL          -- write-ahead logging
PRAGMA synchronous=FULL          -- OS-level fsync on every write
PRAGMA foreign_keys=ON           -- enforce referential integrity
PRAGMA secure_delete=ON          -- SQLite zero-fills deleted pages
PRAGMA auto_vacuum=FULL          -- prevent data remnants in free pages
PRAGMA temp_store=MEMORY         -- no temp files on disk
PRAGMA trusted_schema=OFF        -- disable untrusted schema extensions
PRAGMA locking_mode=EXCLUSIVE    -- single writer; prevents race conditions
PRAGMA mmap_size=0               -- no memory-mapped I/O
```

On close: `PRAGMA wal_checkpoint(TRUNCATE)` zeroes and removes the WAL file.

---

## Brute-force Protection

Progressive lockout ladder:

| Failed Attempts | Lockout Duration |
|---|---|
| 3 | 5 seconds |
| 5 | 30 seconds |
| 7 | 5 minutes |
| 10 | 30 minutes |
| 15 | 24 hours |

A successful unlock resets the counter. The `panic` command immediately wipes the session and exits.

---

## Breach Intelligence (HIBP)

NYXORA uses **k-anonymity** for HIBP queries:

1. Compute SHA-1 of the password (uppercase hex)
2. Send only the first 5 characters to the API
3. Compare the full hash locally against the returned suffix list

The HIBP API never receives the password or its full hash.

---

## Recovery Capsule Format

```
[4-byte magic: NYX\x01]
[4-byte version (big-endian)]
[32-byte random salt]
[N-byte EncryptedField blob]
```

The blob decrypts (with capsule password → Argon2id key) to a JSON payload containing the double-encrypted root key. The root key is encrypted twice:
1. With the capsule-derived key (inner layer)
2. The inner EncryptedField bytes are then re-encrypted (outer layer)

This ensures the payload is opaque even if the outer layer's metadata leaks.

---

## Design Decisions

| Decision | Rationale |
|---|---|
| XChaCha20-Poly1305 as primary | 192-bit nonce avoids birthday attack bounds at scale |
| Per-entry HKDF key isolation | Compartmentalizes compromise; one entry key ≠ all entries |
| Per-entry + vault-wide HMAC | Defense-in-depth: catches both field and entry-level attacks |
| `pretty_exceptions_enable=False` | No Python tracebacks reach the terminal |
| WAL + EXCLUSIVE locking | Prevents partial reads of in-flight encrypted writes |
| 3-pass memory wipe | Best-effort mitigation; CPython doesn't guarantee erasure |
| Salt stored next to vault | Standard practice; security is in the KDF, not salt secrecy |
| No cloud sync, no GUI | Eliminates entire threat classes (MITM, browser vulns, SaaS breach) |
