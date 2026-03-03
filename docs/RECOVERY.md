# NYXORA Recovery Guide

## Overview

NYXORA provides three independent recovery pathways:

1. **TOTP (Time-based One-Time Password)** — second factor for identity verification
2. **Recovery Capsule** — portable encrypted file containing the root key
3. **Shamir Secret Splitting** — split the root key into N shares (K required)

---

## 1. TOTP Setup

TOTP provides an additional authentication factor but does not independently recover your vault — it verifies identity during unlock.

### Setup

```bash
nyx recovery setup
```

Follow the prompts:
1. Enter an account label (e.g., `alice@example.com`)
2. A TOTP secret and `otpauth://` URI will be displayed
3. Scan the URI with your authenticator app (Aegis, Authy, Google Authenticator)
4. Enter the 6-digit code to verify

**Store the TOTP secret securely.** If you lose access to your authenticator app AND the secret, TOTP recovery is impossible.

### Manual Verification

```bash
# The secret is displayed during setup. Store it as:
# otpauth://totp/NYXORA:alice@example.com?secret=BASE32SECRET&issuer=NYXORA
```

---

## 2. Recovery Capsule

The recovery capsule stores your vault's root key, double-encrypted with a separate capsule password.

### Create a Capsule

```bash
nyx vault unlock   # vault must be unlocked first
nyx recovery create-capsule ~/offline_storage/nyxora_recovery.capsule --hint "vault 2024"
```

You will be prompted for a **capsule password** — this must be different from your vault master password. The capsule password is the only thing protecting the capsule file.

**Security recommendations:**
- Store the capsule file in a different physical location from the vault
- Consider printing it as a QR code for paper backup
- Use a long, memorable passphrase for the capsule password
- Test restoration before you need it

### Restore from Capsule

```bash
nyx recovery restore-capsule ~/offline_storage/nyxora_recovery.capsule
```

This decrypts the capsule and displays the recovered root key. You can then use it to initialize a new vault with the same key material.

### Capsule File Format

```
[4-byte magic: NYX\x01]
[4-byte version]
[32-byte random salt]
[EncryptedField blob: outer encryption]
  → decrypts to JSON:
     { version, vault_id, root_key_enc (hex), created_at, hint }
     root_key_enc decrypts (inner layer) to the 32-byte root key
```

---

## 3. Shamir Secret Splitting

Splits your vault root key into N shares where any K shares are sufficient to reconstruct it.

### Create Shares

```bash
nyx vault unlock
nyx recovery split-secret --shares 5 --threshold 3 --output-dir ~/shares/
```

This creates `share_1_of_5.bin` through `share_5_of_5.bin`.

**Distribute shares to trusted parties** or store them in separate locations. With threshold=3, any 3 of the 5 shares can reconstruct the root key.

### Reconstruction (Programmatic)

```python
from nyxora.core.recovery_core import RecoveryManager
from nyxora.core.crypto_engine import CryptoEngine
from pathlib import Path

engine = CryptoEngine()
recovery = RecoveryManager(engine)

shares = [
    Path("share_1_of_5.bin").read_bytes(),
    Path("share_3_of_5.bin").read_bytes(),
    Path("share_5_of_5.bin").read_bytes(),
]
root_key = recovery.combine_shares(shares, k=3)
```

### Mathematical Basis

Shares are computed using polynomial interpolation in GF(2^8) (Galois Field of 256 elements). Each byte of the secret is independently shared. The polynomial is evaluated at points 1..N; recovery uses Lagrange interpolation at x=0 to find the secret byte.

---

## Emergency Checklist

If you cannot unlock your vault:

1. **Check the capsule file** — do you have a `.capsule` file and its password?
2. **Check Shamir shares** — do you have K or more `share_*.bin` files?
3. **Check TOTP** — is your authenticator app accessible?
4. **Check the salt file** — the `.salt` file alongside the vault is required for KDF
5. **Verify the vault file** — run `nyx backup verify <backup>` on a backup copy

If all recovery options are exhausted, the vault data is **unrecoverable by design**.
This is not a bug — it is the zero-knowledge guarantee.
