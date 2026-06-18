# Nyxora Roadmap

This document describes the planned development arc for Nyxora — an offline,
zero-knowledge, terminal-native password manager. It is a living plan: the
near-term releases are firm (they are the known backlog), while later
releases describe a direction steered by real-world use and feedback.

## Versioning policy

Nyxora follows Semantic Versioning, interpreted for a security tool where the
on-disk vault format is the contract users depend on:

- **PATCH (3.0.x)** — Bug fixes only. No new features, no vault-format
  changes, no CLI or SDK signature changes. Safe to upgrade without thought.
- **MINOR (3.x.0)** — New, backwards-compatible features. May add
  vault-metadata fields or screens, but existing vaults continue to open and
  existing CLI/SDK calls continue to work. Additive only.
- **MAJOR (x.0.0)** — Breaking changes: vault-format migration, CLI/SDK
  signature changes, or core re-architecture. Always shipped with a migration
  path and an explicit upgrade guide.

Guiding principle: **the vault format is sacred.** Any change that alters
on-disk bytes in a non-backwards-compatible way is a major release;
everything else is designed to keep existing vaults openable.

## Released

### v3.0.0 "Nexus" — 2026-06-13
Complete TUI v3 rewrite on the Obsidian Tactical design system. Resolved
every CRITICAL/HIGH data-integrity item from the pre-release security audit
(C1 change-password data preservation, C2 focus-aware navigation, C3 SDK/CLI
KDF alignment, H2 crash-safe change-password). First release validated by a
fully green cross-platform CI matrix (Linux + Windows; Python 3.12/3.13/3.14).

## Planned

### 3.0.x — Stabilization (patch line)

**v3.0.1** (in progress)
- Maximize the console window on Windows when the packaged executable is
  launched by double-click.
- Scroll-and-fit layout: the unlock, create-vault, and workspace screens
  scroll instead of clipping their content on short terminals.
- Small-viewport regression test (Textual Pilot) to keep the clip from
  recurring.
- Bump the publish workflow's GitHub Actions to Node-24-compatible versions.
- Make console output encoding-safe on legacy cp1252 Windows consoles
  (fixes a UnicodeEncodeError in `nyx --help` and the release build script).

### v3.1.0 "Aegis" — Security-hardening completeness (minor)
Closes the remaining pre-release-audit items and pays down internal quality
debt, completing the security posture before new feature work.

Security:
- Persistent failed-attempt lockout that survives process restart (H1).
- Hash-chained, tamper-evident audit log (H3/H4).
- Encrypted session key on Linux, at parity with the Windows keyring path (H5).
- Persist KDF parameters in vault metadata — groundwork for crypto-agility.

Quality:
- Restore CI lint and type-check gates to blocking.
- Remove the legacy v2 screens and their build-spec references.
- Fix the vault-open connection leak on integrity-verification failure.
- Add a NYXORA_HOME environment variable for test isolation.
- Rewrite the coverage-gaming test module into honest behavioral tests.

### v3.2.0 "Janus" — Import / export & interoperability (minor)
Makes Nyxora adoptable by users migrating from other tools.
- Importers for KeePass (.kdbx), Bitwarden, 1Password, and generic CSV.
- A first-class encrypted export format for Nyxora-to-Nyxora transfer.
- Field mapping and de-duplication on import.

### v3.3.0 "Argus" — Organization & visibility (minor)
Helps users manage and understand large vaults.
- Folders/groups, favorites, and richer tagging.
- A natively rebuilt search experience.
- A password-health dashboard: reused/weak/old-password detection and a
  breach-summary rollup from the existing HIBP intelligence.
- Bulk operations (multi-select move/tag/delete).

### v3.4.0 "Daedalus" — Automation & extensibility (minor, optional)
Plays to Nyxora's developer-tool heritage; may fold into 3.3 or defer.
- Expanded CLI scripting and non-interactive flows.
- A broader, stable SDK surface.
- Shell completion and improved piping support.
- A possible plugin API.

### v4.0.0 "Cerberus" — Foundations rebuild (major)
The release where accumulated breaking changes are done together, once, with
a clean, well-tested migration from v2 vaults.
- Consolidated vault-format v3 schema (KDF params, audit log, organization
  data) with a one-time migration.
- A crypto-agility layer making cipher and KDF pluggable — the prerequisite
  for post-quantum cryptography.
- SDK 2.0: a cleaned, stable, semver-committed public API.
- Possible first-class multi-vault / vault-profile support.

### v5.0.0 "Prometheus" — Post-quantum (horizon, major)
Built on the 4.0 crypto-agility layer.
- Hybrid classical + post-quantum cryptography: ML-KEM (Kyber) for key
  encapsulation and ML-DSA (Dilithium) for signatures, layered over the
  existing XChaCha20-Poly1305 / Argon2id primitives.
- Enables a truthful post-quantum-resistance claim.

## Cross-cutting commitments

- **Test & CI integrity:** the cross-platform matrix stays green; lint/type
  gates return to blocking in 3.1; every release pre-flight includes a visual
  check of the launched executable.
- **Security posture:** each release remains auditable; a fresh security
  review precedes the 4.0 cryptographic re-architecture.

## Deliberately out of scope (for now)

- **Cloud / hosted sync.** Nyxora's identity is offline and zero-knowledge.
  If synchronization is ever added, it will be limited to encrypted blobs on
  storage the user controls — never a Nyxora-operated server. This is a
  conscious identity decision, not a default direction.

---
*This roadmap is indicative, not a commitment. Priorities for 3.2 and beyond
will be guided by real-world usage.*
