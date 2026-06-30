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

### v3.1.0 "Sentinel" — 2026-06-29
Quality-, CI-, and supply-chain-hardening release. Restored ruff/mypy gates to
blocking; removed the legacy v2 TUI screens and their build-spec references;
fixed the vault-store connection leak; added `NYXORA_HOME` for test isolation;
replaced coverage-padding tests with honest behavioral tests. Added a
supply-chain security layer to CI — gitleaks secret scanning and an SBOM +
grype dependency-CVE gate, both required checks — with SHA-pinned actions and
scoped-OIDC trusted publishing. UI polish: fixed the Updates version-box clip
and the Generate/Updates density/footer layout. No vault-format or crypto
changes — existing vaults open unchanged.

### v3.0.1 — 2026-06-18
Stabilization patch. Scroll-and-fit layout so unlock/create-vault/workspace
screens no longer clip on short terminals (with an 80x24 regression test);
cp1252 console safety for `nyx --help`; publish-workflow Actions bumped to
Node-24-compatible versions. Published the project ROADMAP.

### v3.0.0 "Nexus" — 2026-06-13
Complete TUI v3 rewrite on the Obsidian Tactical design system. Resolved
every CRITICAL/HIGH data-integrity item from the pre-release security audit
(C1 change-password data preservation, C2 focus-aware navigation, C3 SDK/CLI
KDF alignment, H2 crash-safe change-password). First release validated by a
fully green cross-platform CI matrix (Linux + Windows; Python 3.12/3.13/3.14).

## Planned

### v3.2.0 "Aegis" — Security-hardening completeness (minor)
Closes the remaining pre-release-audit items and pays down internal quality
debt, completing the security posture before new feature work.

Security:
- Persistent failed-attempt lockout that survives process restart (H1).
- Hash-chained, tamper-evident audit log (H3/H4).
- Encrypted session key on Linux, at parity with the Windows keyring path (H5).
- Persist KDF parameters in vault metadata — groundwork for crypto-agility.

### v3.3.0 "Janus" — Import / export & interoperability (minor)
Makes Nyxora adoptable by users migrating from other tools.
- Importer for KeePass (.kdbx) — the one major format not yet supported.
- A first-class encrypted export format for Nyxora-to-Nyxora transfer.
- Field mapping and de-duplication on import.

CSV, JSON, Bitwarden, and 1Password import already ship today via
`nyx vault import` (since 2.0.0).

### v3.4.0 "Argus" — Organization & visibility (minor)
Helps users manage and understand large vaults.
- Folders/groups, favorites, and richer tagging.
- A natively rebuilt search experience.
- A password-health dashboard: reused/weak/old-password detection and a
  breach-summary rollup from the existing HIBP intelligence.
- Bulk operations (multi-select move/tag/delete).

### v3.5.0 "Daedalus" — Automation & extensibility (minor, optional)
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
  gates returned to blocking in 3.1 (Sentinel); every release pre-flight includes a visual
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
