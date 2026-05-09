# Security Policy

## Supported Versions

Only the current main version of Nyxora is supported for security updates.

| Version | Supported          |
| ------- | ------------------ |
| v2.6.x  | ✅                 |
| v2.0.x  | ✅ (security fixes only) |
| v1.2.x  | ❌                 |
| v1.1.x  | ❌                 |
| v1.0.x  | ❌                 |

## Reporting a Vulnerability

Security is the core component of Nyxora. I take all vulnerabilities incredibly seriously.

Please DO NOT publicly disclose or open a public GitHub issue for suspected vulnerabilities. Instead, report them directly to me via email:

**Email:** scorpiocodex0@gmail.com
**Author:** ScorpioCodeX

When reporting, please provide:
1. Nyxora version (`nyx --version`)
2. Operating System
3. Step-by-step instructions to reproduce the vulnerability
4. Your analysis of the potential impact

I will verify the report and issue a patch as quickly as possible.

## Security Improvements in v2.0.0

The following issues identified in an independent audit were resolved:

- **Constant-time HMAC** — All HMAC comparisons now use `hmac.compare_digest()`
  eliminating the timing oracle present in v1.0.0
- **Atomic vault replacement** — Password change uses a three-step atomic
  swap with rollback; power loss can no longer destroy the vault
- **Session management** — Brute-force lockout ladder is now enforced at the
  CLI level; failed attempts correctly increment the counter
- **Capsule key separation** — Recovery capsule inner and outer encryption
  use HKDF-derived independent keys
- **Per-file locker salt** — Each encrypted file gets a unique 16-byte salt;
  identical filenames no longer share a key
- **Passphrase entropy** — Full EFF large wordlist (7,776 words) corrects
  the ~27-bit overstatement in v1.0.0

## Breaking Changes in v2.0.0 (Security-Related)

`.nyx` locker files and recovery capsules created with v1.x are not
compatible with v2.0.0 due to cryptographic improvements. See CHANGELOG.md.
