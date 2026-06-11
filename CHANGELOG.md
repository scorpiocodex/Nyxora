# Changelog

All notable changes to Nyxora are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [3.0.0] "Nexus" - 2026-06-11

### Added
- **TUI v3 complete rewrite** with the Obsidian Tactical design system:
  7 sections (Vault, Manage, Backup, Recovery, Updates, Generate,
  Security) plus unlock/create screens and add/edit entry overlays,
  with shared chrome (top status bar, corner readouts, cipher bar)

### Fixed
- **CRITICAL: change-password data preservation** — `nyx vault
  change-password` now preserves the TOTP secret, all vault metadata,
  and the vault_id (was: silently destroyed TOTP secrets and changed
  the vault's identity on every password rotation)
- **Focus-aware navigation** — digit keys 1-7 now reach password and
  search Inputs instead of being swallowed by navigation bindings
  (was: untypeable fields)
- **Manage search focus** — search keeps focus while typing; list
  rebuild awaits widget removal so no zombie widgets are left behind
- **Manage after unlock** — entry list populates correctly immediately
  after cold-launch unlock (was: showed an empty vault)
- **TOTP QR overlay** — recovery QR is rendered in a full-screen modal
  overlay so it is actually scannable (was: clipped and unscannable in
  the side panel)
- **Overlay binding suppression** — quit and section navigation are
  suppressed while entry-form and QR overlays are active, so a stray
  q/1-7 can no longer abandon in-progress work
- **Recovery side panel** — no longer shows stale TOTP confirmation
  text in Capsule/Shamir modes; entry-form overlay layout tidied

### Known deferred (targeted for v3.0.1 / v3.1.0 per roadmap)
- SDK KDF defaults differ from CLI, so the SDK cannot yet open
  CLI-created vaults (C3)
- change-password salt swap is not yet atomic (H2)

---

## [2.6.6] - 2026-05-18

### Fixed
- **Recovery QR code size** — now renders at half size using Unicode
  half-block characters (▀ ▄ █) combining two matrix rows per terminal
  line. Output is approximately half the previous height and width
  while remaining fully scannable.

---

## [2.6.5] - 2026-05-18

### Fixed
- **nyx backup verify** — argument is now optional; when omitted, automatically
  selects the most recent backup from ~/.nyxora/backups/ with an info panel
  showing which file was selected
- **nyx script pipe/run on Windows** — Windows built-in commands (more, type,
  findstr, etc.) now work via shell=True routing through cmd.exe; non-Windows
  systems continue to use direct subprocess without shell

---

## [2.6.4] - 2026-05-13

### Fixed
- **VaultStore.set_metadata_value** — method was missing, causing TOTP
  secret persistence to fail with AttributeError after setup verification
- **Recovery QR code** — now renders using solid block characters (██) with
  explicit black foreground on white background across the entire row,
  producing a correctly scannable dark-on-light QR code in Windows Terminal,
  PowerShell, and any ANSI terminal

---

## [2.6.3] - 2026-05-13

### Fixed
- **Recovery QR code scanning** — QR code now renders with explicit black
  module on white background (dark-on-light) instead of the inverted
  terminal-color rendering that prevented camera scanning. Quiet zone
  border increased from 1 to 2 for better scanner lock-on.

---

## [2.6.2] - 2026-05-13

### Fixed
- **Recovery TOTP persistence** — `nyx recovery setup` now saves the TOTP
  secret to vault metadata after successful verification, so
  `nyx recovery status` correctly shows ✓ TOTP two-factor authentication
- **Recovery status detection** — `nyx recovery status` now uses recursive
  glob (rglob) to find capsule files and Shamir share files in subdirectories
  under ~/.nyxora/, not just the top-level directory

### Added
- **QR code in terminal** — `nyx recovery setup` now renders the TOTP QR
  code directly in the terminal as Unicode block characters so users can
  scan with any authenticator app without manually typing the URI.
  Falls back to URI display if qrcode package is unavailable.

### Dependencies
- Added `qrcode>=7.4.2` to package dependencies

---

## [2.6.1] - 2026-05-10

### Fixed
- **vault unlock --create**: parent directory now created before vault
  initialisation — prevented sqlite3.OperationalError on fresh installs
- **Linux keyring fallback**: when no keyring daemon is available on Linux,
  session key falls back to ~/.nyxora/session.key (mode 0o600) with a clear
  warning; error message now includes actionable fix commands
- **Wrong password message**: IntegrityError on unlock now shows "Wrong
  password or corrupted vault" instead of the misleading
  "Schema fingerprint mismatch — structural tampering detected"
- **Title search on all entry commands**: nyx secret get/update/delete/
  clone/totp and nyx script pipe/run/fzf now accept entry titles as well
  as UUIDs
- **TUI keybindings**: moved all bindings to App level to bypass ListView
  key capture; j/k/c/t/d/A/slash/Esc/q all functional
- **TUI CSS**: replaced invalid 'gap' property with 'grid-gutter'
- **TUI delete**: two-press D confirmation now performs actual vault deletion
  and refreshes the entry list in real time

---

## [2.6.0] - 2026-05-03

### Added
- **Auto-updater** (`nyx update check/install/rollback/channel`) — GitHub
  Releases API integration with SHA-256 integrity verification, rollback
  support, and non-blocking startup version notification after unlock
- **Named vault profiles** (`nyx vault profiles/use/add-profile/remove-profile`)
  — multiple vaults managed from one installation; active profile auto-resolves
  vault path across all commands
- **JSON output mode** (`nyx --json`) — any command emits machine-readable JSON;
  supported on secret get/list/search, vault status, generate password/passphrase
- **TOTP per entry** — store a TOTP secret alongside credentials;
  `nyx secret totp [entry]` shows live 6-digit code with countdown bar;
  `--watch` flag auto-refreshes every 30 seconds
- **Vault health score** (`nyx security health`) — 0–100 composite grade
  across strength, breach-free, no-reuse, age, and TOTP coverage
- **Rotation reminders** (`nyx security due [--days N]`) — lists entries
  whose password hasn't changed in N days, sorted oldest-first
- **nyx vault import** — extended with `--totp-secret` on update command
- **Scripting layer** — `nyx script pipe`, `nyx script run`, `nyx script fzf`
  for credential injection into subprocesses without shell history exposure
- **Python SDK** (`from nyxora import VaultClient`) — high-level programmatic
  vault access with context manager, session-based and password-based modes
- **Textual TUI** (`nyx tui`) — Obsidian Tactical interactive vault browser;
  entry list with j/k navigation, live search overlay, detail panel with
  TOTP countdown, audit dashboard, amber #C89A30 tactical theme
- **Shell completions v2** — entry titles complete live from vault on Tab
  for `nyx secret get`, `nyx secret update`, `nyx secret delete`
- **PyInstaller build** — Windows standalone `nyx.exe` with gem icon;
  `python scripts_build/build_windows.py` produces a single-file executable

### Security
- Schema version bumped to "2"; silent migration adds `totp_secret_enc` column
  to existing v2.0.0 vaults on first open — HMAC stays consistent

### Breaking Changes
- None — fully backward-compatible with v2.0.0 vault files

---

## [2.0.0] - 2026-05-03

### Added
- `nyx vault import` — batch import from CSV, Bitwarden JSON, 1Password CSV,
  and Nyxora JSON export formats with auto-detection and dry-run preview
- In-session entry cache on VaultStore — eliminates O(N) decryptions on
  repeated list/search operations; invalidated on every mutation
- `VaultStore.get_metadata_value()` — public API for metadata queries,
  replacing internal `_conn` access in the recovery status command
- `nyx generate password --min-strength` — regenerates up to 10 times until
  the requested entropy threshold (weak/fair/strong/excellent) is met
- `nyx generate passphrase --count/-n` — generate multiple passphrases in
  one call, matching the `password` command's existing `--count` flag
- `nyx secret update --tags` — replace tags on an existing entry
- `nyx secret add --custom` — attach arbitrary key=value custom fields
- Full EFF Large Wordlist (7,776 words) replaces the 204-word sample —
  5-word passphrase entropy: 37.7 bits → 64.6 bits
- 9 new terminal UI components: `entropy_bar`, `strength_badge`,
  `checklist_panel`, `danger_panel`, `session_dashboard`,
  `audit_summary_panel`, `clipboard_countdown`, `update_diff_panel`,
  `recovery_status_panel`
- Visual entropy bar and strength badge on all generation commands
- `nyx vault status` now shows a rich session dashboard (entries, session
  token prefix, inactivity timeout, failed attempt count, cipher suite)
- `nyx vault health-check` renders a pass/fail integrity checklist
- `nyx security audit` appends a colour-coded summary panel
- `nyx backup export --plaintext` requires a two-step danger confirmation
  (confirm prompt + type the word CONFIRM)
- `nyx secret get --copy` auto-clears clipboard after 30 seconds
- `nyx recovery status` now shows real TOTP/capsule/share detection
- Real integration tests replacing empty stubs: full vault lifecycle,
  brute-force lockout ladder, 3-layer tamper detection, entry cache,
  metadata API, and CSV import round-trip (135 tests total)

### Security
- Recovery capsule inner and outer encryption now use HKDF-derived
  independent keys (`nyxora:capsule:inner` / `nyxora:capsule:outer`) —
  previously both layers shared `capsule_key` directly
- Locker `.nyx` files now embed a 16-byte random salt in the header;
  identical filenames always produce a different encryption key
- `nyx secret update --password` flag removed — password no longer exposed
  in shell history or `ps aux`; interactive prompt required instead
- Plaintext backup export now requires double confirmation with exact word
  match to prevent accidental credential exposure

### Performance
- `wipe_memory()` passes 2 and 3 now use `ctypes.memset` — orders of
  magnitude faster for large buffers
- `gc.collect()` removed from `wipe_memory()` — eliminates ResourceWarning
  cascade and unnecessary GC pressure on every key wipe
- GF(256) multiplicative inverse is now an O(1) precomputed lookup table
  (was O(256) brute-force per call)
- `security audit` HIBP checks now run concurrently via
  `ThreadPoolExecutor(max_workers=5)` — ~10× faster for large vaults

### Fixed
- `nyx vault change-password`: atomic three-step file swap with rollback —
  power loss can no longer permanently destroy the vault (Phase 1)
- HMAC comparisons in `_verify_entry_hmac` and `_verify_vault_hmac` now
  use `hmac.compare_digest()` — eliminates timing oracle (Phase 1)
- `SessionManager` brute-force ladder now active at CLI level —
  `record_failed_attempt()` and `record_successful_unlock()` wired in (Phase 1)
- `SessionManager._running` initialised in `__init__` — no more
  `AttributeError` when `lock()` called before `unlock()` (Phase 1)
- `delete_entry` now verifies entry HMAC before soft-deletion, consistent
  with `get_entry` and `update_entry` (Phase 1)
- `unlock --create` branch now writes the `.salt` file — vault can be
  re-opened after creation via `--create` flag (Phase 2)
- Empty tag list `[]` in `migrate_from_store` no longer treated as `None` —
  HMAC mismatch after migration fixed (Phase 2)
- `locker_key` always wiped in `finally` block during encrypt — key no
  longer leaked in memory on exception (Phase 2)
- `_derive_argon2id` removes pointless `tmp` wipe of a bytearray copy;
  `del raw` minimises lifetime of the immutable `bytes` object (Phase 2)
- Dead code removed: unreachable `return` after `raise` in HIBP check;
  unused `sha1` variable in `check_breach_offline` (Phase 4)
- `Config.validate()` called on every `load()` — invalid configs no longer
  silently propagate (Phase 4)
- `nyx recovery status` no longer returns placeholder text (Phase 2 UI)
- Panic exit code changed to 4 — no conflict with brute-force lockout
  exit code 3 (Phase 2 UI)

### Breaking Changes
- `.nyx` locker files created with v1.x are **not compatible** with v2.0.0.
  The file header format changed to include a 16-byte per-file salt.
  Re-encrypt files using `nyx locker decrypt` (v1.x) then
  `nyx locker encrypt` (v2.0.0).
- Recovery capsules created with v1.x are **not compatible** with v2.0.0.
  The HKDF key derivation for inner/outer layers changed.
  Recreate capsules using `nyx recovery create-capsule`.

---

## [1.2.0] - 2026-05-03

### Performance
- `wipe_memory()` passes 2+3 use `ctypes.memset` (single C-level write)
- `gc.collect()` removed from `wipe_memory()` — fixes ResourceWarning flood
- GF(256) inverse now O(1) precomputed lookup table
- HIBP audit requests now concurrent via `ThreadPoolExecutor(max_workers=5)`

### Security
- Recovery capsule: HKDF-separated inner/outer keys
- Locker: per-file 16-byte salt embedded in `.nyx` header
- Full EFF large wordlist (7,776 words) — fixes ~27-bit entropy overstatement

### Fixed
- Dead code removed from `intel_engine.py` (unreachable return, unused sha1)
- `strength_color()` removed from `generate.py` (replaced by `strength_badge`)
- `TYPE_CHECKING` no-op removed from `crypto_engine.py`
- `click` removed as explicit dep (transitive via `typer[all]`)
- `Config.validate()` now called on `load()`
- Inactivity monitor mock exhaustion warning resolved in test suite

### CI
- Matrix expanded: ubuntu + windows × Python 3.12, 3.13, 3.14 (6 jobs)

---

## [1.1.0] - 2026-05-02

### Added
- 9 new UI components: entropy bar, strength badge, checklist panel,
  danger panel, session dashboard, audit summary panel, clipboard countdown,
  update diff panel, recovery status panel
- Real integration tests: full vault lifecycle, brute-force lockout, tamper
  detection (7 tests replacing empty stubs)
- `nyx vault status` → rich session dashboard
- `nyx vault health-check` → integrity checklist panel
- `nyx security audit` → summary panel appended
- `nyx backup export --plaintext` → two-step danger confirmation
- `nyx secret get --copy` → 30-second clipboard auto-clear
- `nyx recovery status` → real TOTP/capsule/share detection

### Fixed
- `unlock --create` writes salt file (vault was uncloseable after creation)
- Empty tag list migration HMAC mismatch resolved
- `locker_key` wiped in `finally` on encrypt exception
- `_derive_argon2id` removes misleading `tmp` wipe
- `nyx secret update --password` flag removed (shell history exposure)

### Security
- Panic exit code 4 (was 3, conflicting with brute-force lockout)

---

## [1.0.1] - 2026-05-01

### Security
- `nyx vault change-password`: atomic file swap prevents vault destruction
- HMAC comparisons use `hmac.compare_digest()` — timing-safe
- `SessionManager` brute-force ladder wired into CLI unlock path
- `SessionManager._running` initialised in `__init__`
- `delete_entry` verifies HMAC before soft-deletion

---

## [1.0.0] - 2026-03-03

### Added
- Initial production release
- Offline zero-knowledge architecture with Argon2id + XChaCha20-Poly1305
- 7 command groups: vault, secret, generate, security, backup, recovery, locker
- 3-layer HMAC integrity (per-entry, vault-wide, schema fingerprint)
- Shamir secret sharing, TOTP, encrypted recovery capsules
- HIBP k-anonymity breach detection
- Neon cyberpunk Rich terminal UI
- Hardened SQLite (WAL, EXCLUSIVE locking, secure_delete)
- Windows VirtualLock / Linux mlock memory protection
- 3-pass secure memory wipe (urandom → 0xFF → 0x00)
