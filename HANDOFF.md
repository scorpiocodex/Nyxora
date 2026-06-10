# HANDOFF.md — Nyxora v3.0.0 "Nexus"

> Complete project handoff document. Everything needed to continue development,
> debug outstanding issues, and ship the v3.0.0 release.
>
> Last updated: 2026-05-22 | Author: scorpiocodex | Status: Pre-release, pending final fixes

---

## Table of Contents

1. [Project Identity](#1-project-identity)
2. [Architecture Overview](#2-architecture-overview)
3. [Repository Structure](#3-repository-structure)
4. [Current State](#4-current-state)
5. [Uncommitted Work This Session](#5-uncommitted-work-this-session)
6. [Design System — Obsidian Tactical v3](#6-design-system--obsidian-tactical-v3)
7. [Known Issues — Not Yet Fixed](#7-known-issues--not-yet-fixed)
8. [Critical Bugs From Full Audit](#8-critical-bugs-from-full-audit)
9. [Test Suite State](#9-test-suite-state)
10. [Key API Reference](#10-key-api-reference)
11. [Vault File Locations](#11-vault-file-locations)
12. [Development Environment](#12-development-environment)
13. [Immediate Next Steps](#13-immediate-next-steps)
14. [Final Commit Sequence](#14-final-commit-sequence)
15. [Post-Release Roadmap](#15-post-release-roadmap)
16. [Full Codebase Audit Report](#16-full-codebase-audit-report)
17. [GUI vs TUI Decision](#17-gui-vs-tui-decision)

---

## 1. Project Identity

| Field | Value |
|---|---|
| **Project** | Nyxora — offline, zero-knowledge terminal password manager |
| **PyPI package** | `nyxora` |
| **CLI entry point** | `nyx` |
| **Current PyPI version** | v2.6.6 (NOT yet bumped) |
| **Target release** | v3.0.0 "Nexus" |
| **Repo** | https://github.com/scorpiocodex/Nyxora |
| **Local path (Windows)** | `C:\Users\scorp\dev\python\Other\nyxora\` |
| **Branch** | `main` |
| **GitHub handle** | scorpiocodex |
| **Git email** | 212041449+scorpiocodex@users.noreply.github.com |
| **Python** | 3.12+ (tested on 3.14.3-final-0) |
| **Primary OS** | Windows 11 (dev) + Ubuntu 24.04 (CI) |
| **CLI framework** | Typer + Rich |
| **TUI framework** | Textual |
| **Build** | Hatchling + PyInstaller |
| **Tests** | pytest, 186 tests, 80.78% coverage, 80% gate enforced |
| **Brand** | ScorpioCodeX |

---

## 2. Architecture Overview

```
Master password
      │
      ▼
Argon2id KDF  ←── salt from ~/.nyxora/vault.salt (32-byte sidecar)
      │
      ▼
256-bit root key (bytearray, wiped after use)
      │
      ├── HKDF per-entry key isolation
      │         │
      │         ▼
      │   XChaCha20-Poly1305 field encryption
      │         │
      │         ▼
      │   SQLite BLOB storage with 3-layer HMAC integrity model
      │
      └── Session: root_key.hex() stored in OS keyring
                   session.json pointer at ~/.nyxora/session.json
                   loaded by load_session() → (session_id, vault_path, bytearray)
```

**Session mechanism** (`cli/helpers.py`):
- `save_session(session_id, vault_path_str, root_key_hex)` → OS keyring + JSON pointer
- `load_session()` → `(session_id, Path, bytearray.fromhex(root_key_hex))` or `None`
- `clear_session()` → deletes keyring entry + JSON pointer + fallback file
- `open_vault(engine)` → `(VaultStore, session_id, root_key, vault_path)` — raises `typer.Exit(2)` if locked

**Important**: `typer.Exit(2)` is a `SystemExit` subclass — catch with `except BaseException`, not `except Exception`.

---

## 3. Repository Structure

```
nyxora/
├── src/nyxora/
│   ├── __init__.py              __version__ = "2.6.6"  ← NEEDS BUMP TO 3.0.0
│   ├── core/
│   │   ├── crypto_engine.py     XChaCha20-Poly1305 + Argon2id + HKDF
│   │   ├── vault_store.py       SQLite encrypted storage, ForensicReport dataclass
│   │   ├── session_core.py      In-memory session (process-scoped, see audit §4)
│   │   ├── memory_guard.py      Key wiping, mlock/VirtualLock
│   │   ├── recovery_core.py     TOTP + Shamir GF(256) + recovery capsule
│   │   ├── intel_engine.py      Entropy scoring + HIBP k-anonymity
│   │   └── update_engine.py     GitHub Releases module-level functions
│   ├── cli/
│   │   ├── main.py              Typer root app + global exception handler
│   │   ├── ui.py                Rich panels/tables/spinners/JSON mode
│   │   ├── helpers.py           Session persistence + open_vault helper
│   │   └── commands/
│   │       ├── vault.py         nyx vault (init/unlock/lock/info/change-password)
│   │       ├── secret.py        nyx secret (add/get/edit/delete/copy/totp)
│   │       ├── generate.py      nyx generate
│   │       ├── security.py      nyx security (audit/check/hibp)
│   │       ├── backup.py        nyx backup (create/list/restore/verify)
│   │       ├── recovery.py      nyx recovery (setup/restore/shamir)
│   │       ├── locker.py        nyx locker (encrypt/decrypt files)
│   │       ├── update.py        nyx update (check/install/rollback)
│   │       ├── scripting.py     nyx script (pipe/run/fzf)
│   │       ├── import_.py       nyx import (1password/bitwarden/csv)
│   │       └── tui_cmd.py       nyx tui → launch_tui()
│   ├── tui/
│   │   ├── app.py               NyxoraApp: ContentSwitcher, nav bindings, quit
│   │   ├── launcher.py          _resolve_start_screen() vault-state routing
│   │   ├── theme.tcss           Full Obsidian Tactical v3 CSS (614+ lines)
│   │   └── screens/
│   │       ├── _shared_bg.py    ★ NEW (untracked) — shared chrome components
│   │       ├── unlock.py        UnlockScreen + CreateVaultScreen
│   │       ├── vault.py         Section 1 — vault info + lock/unlock + health
│   │       ├── manage.py        Section 2 — 2-panel entry browser
│   │       ├── backup.py        Section 3 — create/verify/list backups
│   │       ├── recovery.py      Section 4 — TOTP/capsule/Shamir
│   │       ├── updates.py       Section 5 — version check/install
│   │       ├── generate.py      Section 6 — password/passphrase generator
│   │       ├── security.py      Section 7 — strength analyser
│   │       ├── add_entry.py     AddEntryScreen overlay
│   │       ├── edit_entry.py    EditEntryScreen overlay
│   │       ├── vault_browser.py ⚠ LEGACY v2 — not imported, safe to delete
│   │       ├── audit_screen.py  ⚠ LEGACY v2 — not imported, safe to delete
│   │       └── search_overlay.py ⚠ LEGACY v2 — not imported, safe to delete
│   ├── sdk.py                   VaultClient programmatic API
│   ├── data/                    EFF diceware wordlist
│   └── utils/
│       ├── exceptions.py        NyxoraError hierarchy
│       └── config.py            YAML + env overrides
├── tests/
│   ├── unit/                    18 test modules, 186 tests
│   └── integration/             Full lifecycle + tamper detection
├── docs/
│   ├── ARCHITECTURE.md
│   ├── SECURITY.md
│   ├── RECOVERY.md
│   └── CLI_UX_SPEC.md
├── .github/workflows/
│   ├── ci.yml                   lint + mypy + pytest matrix (3 OS × Python)
│   └── publish.yml              PyPI OIDC on GitHub Release
├── build_release.py             wheel/sdist + PyInstaller exe
└── pyproject.toml               hatchling, pytest 80% gate, ruff, mypy strict
```

---

## 4. Current State

### What is on PyPI / GitHub Releases
- **v2.6.6** — stable, all CLI commands working on Windows 11 + Ubuntu 24.04
- All 186 tests passing
- No TUI v3 work in the release yet

### What is in the working tree (uncommitted)
All TUI v3.0.0 screens are built, styled, and tested. The version bump has NOT been applied. `_shared_bg.py` is **untracked** — it must be `git add`-ed before committing or every screen import will fail.

### TUI Launch Flow
```
nyx tui
  └── launch_tui()               app.py
        └── _resolve_start_screen()  launcher.py
              ├── no vault.nyx → push CreateVaultScreen
              ├── vault exists + no session → push UnlockScreen
              └── session active → _switch_to("manage")
```

---

## 5. Uncommitted Work This Session

| File | Change Type | Summary |
|---|---|---|
| `tui/screens/_shared_bg.py` | **NEW UNTRACKED** | NyxBackground, NyxTopBar, NyxBottomBar, NyxCornerInfo, NyxSep, BG_PATTERN |
| `tui/screens/unlock.py` | Redesigned | Full Obsidian Tactical redesign with corner readouts, top/bottom bars, centered form box, proper key derivation via vault.salt sidecar, no SessionManager |
| `tui/screens/vault.py` | Modified | Chrome added, dynamic lock/unlock toggle, correct ForensicReport attribute names |
| `tui/screens/manage.py` | Modified | Chrome, debounced on_show (_load_pending flag), _widgets_ready guard, _refresh_topbar, BaseException catch for typer.Exit, _focus_list helper |
| `tui/screens/backup.py` | Modified | Chrome, VaultStore-based verify (replaced broken sqlite3 probe), len(list_entries()) replacing non-existent count_entries() |
| `tui/screens/recovery.py` | Modified | Chrome, split layout (left panels + right white QR panel), full _render_qr rewrite (plain unicode, no nested markup), session guard on all 3 action methods |
| `tui/screens/updates.py` | Modified | Chrome, module-level functions replacing missing UpdateEngine class, amber Rich markup on version boxes |
| `tui/screens/generate.py` | Modified | Chrome added |
| `tui/screens/security.py` | Modified | Chrome added |
| `tui/screens/add_entry.py` | Modified | Minor fixes |
| `tui/screens/edit_entry.py` | Modified | Minor fixes |
| `tui/app.py` | Modified | Real screens wired in ContentSwitcher (PlaceholderScreen removed), clear_session() in action_quit, priority=True on nav bindings 1-7 |
| `tui/launcher.py` | Modified | _resolve_start_screen routing |
| `tui/theme.tcss` | Modified | Full Obsidian Tactical v3 (614+ lines), recovery QR panel CSS, shared chrome CSS |
| `cli/commands/tui_cmd.py` | Modified | Delegates to launch_tui() with no hardcoded start_screen |
| `tests/unit/test_tui.py` | Modified | 186 tests, smoke tests for all screens + shared chrome components |

---

## 6. Design System — Obsidian Tactical v3

### Colour Tokens

| Role | Hex | Usage |
|---|---|---|
| Background | `#060810` | Screen background |
| Surface | `#08111A` | Card/form box background |
| Surface 2 | `#04060C` | Input fields, top/bottom bars |
| Border | `#1A2535` | Widget borders |
| Accent amber | `#C89A30` | Active states, titles, buttons |
| Accent blue | `#3A7A9A` | URLs, secondary info |
| Success | `#3A9A5A` | Unlocked state, health check pass |
| Danger | `#CC3333` | Lock button, errors, failed checks |
| Dim text | `#1E2D3D` | Inactive status bar items |
| Very dim | `#141E28` | Corner readouts, background labels |
| Extra dim | `#0E1820` | Separators, decorative elements |

### Shared Chrome Components (`_shared_bg.py`)

```python
NyxBackground()
# Pre-generated ambient hex/dot/phrase text pattern
# Color: #141E28 (barely visible tactical background)

NyxTopBar(items: list[tuple[str, bool]])
# One-line status bar at top of every screen
# active=True → [#C89A30] amber, active=False → [#1E2D3D] dim
# Height: 1 line, background: #04060C

NyxBottomBar(text: str = "")
# Default: XCHACHA20-POLY1305 ◆ ARGON2ID ◆ OFFLINE · ZERO-KNOWLEDGE ◆ SCORPIOCODEX
# Height: 1 line, background: #04060C

NyxCornerInfo(label: str, lines: list[str])
# Small info readout block — label in very dim amber, lines in extra dim
# Used in nyx-corners-top and nyx-corners-bot Horizontal containers

NyxSep()
# ──────────────────◆────────────────── gradient separator line
# Used between header and content in form screens
```

### Per-Screen Chrome Configuration

| Screen | Top Bar | Corner TL | Corner TR | Corner BL | Corner BR |
|---|---|---|---|---|---|
| **Unlock** | VAULT:LOCKED · SESSION:CLEARED · KEYRING:ACTIVE · OFFLINE | CIPHER SUITE / XCHACHA20 / ARGON2ID | SESSION STATUS / LOCKED / NO SESSION | VAULT PATH / ~/.nyxora | BUILD INFO / v3.0.0 / NEXUS |
| **Vault** | ● LOCKED/UNLOCKED · SECTION 1 · ARGON2ID | KDF / ARGON2ID / 64MB RAM | INTEGRITY / HMAC/SCHEMA/AUDIT | CIPHER / XCHACHA20 | VAULT ID / 2a4fa4a8… |
| **Manage** | VAULT:UNLOCKED · N/M ENTRIES · SECTION 2 | ENTRIES / TOTAL/FILTERED | SESSION / ACTIVE / KEYRING:OK | CIPHER / XCHACHA20 | VAULT / vault.nyx |
| **Backup** | BACKUP MANAGER · SECTION 3 · OFFLINE | LAST BACKUP / DATE / SIZE | STORAGE / ~/.nyxora/backups | FORMAT / AES SNAPSHOT | VERIFY / VAULTSTORE.OPEN |
| **Recovery** | TOTP:✓/✗ · CAPSULE:✓/✗ · SHAMIR:✓/✗ · SECTION 4 | PROTOCOLS / TOTP/RFC6238 | CAPSULE / ARGON2ID KDF | SHAMIR / GF(2^8) | RECOVERY / OFFLINE ONLY |
| **Updates** | v3.0.0 · STABLE CHANNEL · SECTION 5 · PYPI + GITHUB | CHANNEL / STABLE / PYPI | INSTALLED / v3.0.0 / NEXUS | UPDATE / WHEEL+SHA256 | ROLLBACK / PREV VERSION |
| **Generate** | GENERATOR · SECTION 6 · CSPRNG | ENTROPY SOURCE / CSPRNG | CHARSET / 94 SYMBOLS | ALGORITHM / UNIFORM RANDOM | CLIPBOARD / AUTO-CLEAR 30s |
| **Security** | STRENGTH CHECKER · SECTION 7 · LOCAL ONLY | ANALYSIS / LOCAL ONLY / NO NETWORK | ALGORITHM / SHANNON ENTROPY | PRIVACY / NOTHING STORED | GRADES / A+/A/B/C/D/F |

---

## 7. Known Issues — Not Yet Fixed

These were identified during testing and need fixes before the final commit:

### Issue 1 — CRITICAL: `priority=True` nav bindings break password input

**What happens**: Keys 1–7 are registered as App-level `priority=True` bindings in `app.py:80-93`. Textual processes `priority=True` bindings before ANY focused widget — including the master password `Input` on UnlockScreen and CreateVaultScreen. A master password containing digits 1–7 cannot be typed. Pressing "3" navigates to Backup instead of inserting "3" into the password field.

**Root cause**: `priority=True` was added to stop digits leaking into the Manage search box. This fixed one problem but created a worse one.

**Correct fix**: Replace `priority=True` with a focus-aware `check_action` that suppresses navigation when any `Input` widget has focus:

```python
# In NyxoraApp:
def check_action(self, action: str, parameters: tuple) -> bool:
    """Suppress navigation if an Input has focus."""
    if action == "navigate":
        from textual.widgets import Input
        try:
            focused = self.focused
            if isinstance(focused, Input):
                return False
        except Exception:
            pass
    return True
```

### Issue 2 — Manage entry alternating display

**What happens**: After adding an entry and navigating away and back, TestA alternates between visible and invisible on successive navigations.

**Status**: Partially fixed by debounce + BaseException catch. Still intermittently failing. May be resolved by the priority=True fix (since the Input focus interception was causing spurious reloads).

### Issue 3 — QR code alignment

**What happens**: QR code renders left-middle of the white panel instead of center-top.

**Fix needed**: In `theme.tcss`, the `#totp-output` with `width: auto` should center when its parent has `align: center top` — but the `align` property needs to be on the `#qr-panel`'s content, not the panel itself. Try:

```css
#qr-panel {
    width: 46;
    height: 100%;
    border-left: tall #1A2535;
    background: #FFFFFF;
    padding: 0;
    overflow: hidden hidden;
    align: center top;
}

#totp-output {
    width: auto;
    height: auto;
    background: #FFFFFF;
    color: #000000;
    margin: 1 0 0 0;
}
```

### Issue 4 — QR code size

**What happens**: QR fills ~3/4 of panel width, looks slightly small.

**Fix**: In `recovery.py` `_render_qr()`, increase `border=2` to `border=3`.

---

## 8. Critical Bugs From Full Audit

Identified by the full codebase audit. Must be addressed, severity ordered:

### CRITICAL — Address before any public promotion

| # | Location | Bug | Impact |
|---|---|---|---|
| C1 | `vault_store.py:730-817` | `migrate_from_store` never copies `totp_secret_enc` or metadata rows — change-password silently destroys all TOTP secrets | Data loss |
| C2 | `app.py:80-93` | `priority=True` nav bindings make digits 1-7 untypeable in master password field | Security/usability |
| C3 | `sdk.py:54-57` | SDK KDF defaults (64MB/t=1) differ from CLI (256MB/t=4) — SDK cannot open CLI-created vaults | Data inaccessibility |

### HIGH — Address in v3.1.0

| # | Location | Bug | Impact |
|---|---|---|---|
| H1 | `vault.py:29`, `session_core.py` | Brute-force lockout is per-process only — non-functional across `nyx vault unlock` calls | Security |
| H2 | `vault.py:233-247` | Non-atomic salt/vault swap in `change-password` — crash mid-swap bricks the vault permanently | Data loss |
| H3 | `vault_store.py:288-313` | Schema fingerprint checks hardcoded strings, not actual DB structure | False security |
| H4 | `vault_store.py:833` | `audit_log_ok = True` hardcoded in `verify_integrity()` — audit log never actually verified | False security |
| H5 | `helpers.py:25-38` | Linux session key fallback (`session.key`) is plaintext, not encrypted as docs claim | Security |
| H6 | `recovery.py:108` | TOTP secret stored plaintext in metadata, never enforced as auth factor | Security theater |
| H7 | Coverage | 572 `# pragma: no cover` annotations gaming the 80% gate | Quality |

### MEDIUM

| # | Bug |
|---|---|
| M1 | Clipboard never cleared in CLI — thread dies with process exit |
| M2 | `restore-capsule` decrypts key then wipes it — never creates a session (recovery is a dead end) |
| M3 | Updater fails open on checksum error — installs anyway |
| M4 | Windows `script run` uses `shell=True` with `" ".join(args)` — command injection via spaces |
| M5 | Locker decrypt path traversal — `original_name` not sanitized |
| M6 | Backups bound to current root key — useless after password change or forgotten password |

---

## 9. Test Suite State

```
186 tests passing
80.78% coverage (gate: 80%)
Platform: win32, Python 3.14.3-final-0
Runtime: ~44 seconds

Warnings (non-blocking):
  ResourceWarning: unclosed database in sqlite3.Connection
  (in conftest.py gc.collect() — test cleanup, not production)
```

### Test Files

| File | Tests | Coverage |
|---|---|---|
| `test_tui.py` | 19 smoke tests | All screen instantiation + shared components |
| `test_vault_store.py` | Vault CRUD, integrity, tamper detection | Core storage |
| `test_crypto_engine.py` | Encryption, KDF, HKDF, HMAC | Crypto layer |
| `test_cli_commands.py` | CLI command execution | CLI surface |
| `test_sdk.py` | VaultClient API | SDK layer |
| `test_full_workflow.py` | Full lifecycle integration | End-to-end |
| `test_tamper_detection.py` | HMAC + schema tamper | Integrity |

### How to Run

```bash
pytest tests/ -x -q --timeout=60          # full suite, stop on first fail
pytest tests/unit/test_tui.py -v          # TUI smoke tests only
pytest tests/ --co -q                     # list all tests without running
```

---

## 10. Key API Reference

### Session Management (`cli/helpers.py`)

```python
save_session(
    session_id: str,
    vault_path: str,       # string, not Path
    root_key_hex: str,     # root_key.hex()
) -> None

load_session() -> tuple[str, Path, bytearray] | None
# Returns (session_id, vault_path, bytearray.fromhex(root_key_hex))
# Returns None if no active session

clear_session() -> None
# Deletes keyring entry + session.json + fallback session.key

open_vault(crypto: CryptoEngine) -> tuple[VaultStore, str, bytearray, Path]
# Raises typer.Exit(2) — a SystemExit — if no session
# Catch with: except BaseException
```

### VaultStore (`core/vault_store.py`)

```python
VaultStore(engine: CryptoEngine)

# Lifecycle
store.initialize(path: Path, root_key: bytearray) -> None   # create new vault
store.open(path: Path, root_key: bytearray) -> None          # open existing (returns None)
store.close() -> None

# IMPORTANT: VaultStore.open() takes root_key: bytearray, NOT a password string
# Passing a str raises: TypeError: string argument without an encoding

# Entries
store.list_entries(include_deleted: bool = False) -> list[EntryRecord]
store.add_entry(title, username, password, url, notes, tags) -> str  # returns entry_id
store.update_entry(entry_id, **kwargs) -> None
store.delete_entry(entry_id: str) -> None
# NOTE: count_entries() DOES NOT EXIST — use len(store.list_entries())

# Metadata
store.get_metadata_value(key: str) -> str | None
store.set_metadata_value(key: str, value: str) -> None
store.get_vault_id() -> str

# Integrity
store.verify_integrity() -> ForensicReport  # dataclass, NOT a dict — use getattr
```

### ForensicReport Dataclass

```python
# Correct attribute names (confirmed from vault_store.py source):
report.schema_ok       : bool
report.vault_hmac_ok   : bool        # NOT report.hmac_ok
report.entries_checked : int
report.entries_failed  : list[str]   # list of IDs, NOT a bool
report.audit_log_ok    : bool        # NOT report.audit_ok (hardcoded True in code)
report.passed          : bool
report.details         : list[str]

# Correct health check usage:
checks = {
    "Schema fingerprint":    getattr(report, "schema_ok",     False),
    "Vault-wide HMAC chain": getattr(report, "vault_hmac_ok", False),
    "Entry integrity":       len(getattr(report, "entries_failed", ["x"])) == 0,
    "Audit log integrity":   getattr(report, "audit_log_ok",  False),
}
```

### CryptoEngine (`core/crypto_engine.py`)

```python
engine = CryptoEngine()
engine.derive_key(password: str, salt: bytes) -> bytearray
engine.generate_salt() -> bytes   # 32 random bytes
engine.generate_password(length: int) -> str
```

### TUI Unlock Key Derivation Pattern

```python
# Correct flow (used in unlock.py):
vault_path = Path.home() / ".nyxora" / "vault.nyx"
salt_path  = vault_path.parent / (vault_path.stem + ".salt")
salt       = salt_path.read_bytes()               # raw bytes sidecar

engine   = CryptoEngine()
root_key = engine.derive_key(password, salt)      # password is plain str

store = VaultStore(engine)
store.open(vault_path, root_key)                  # root_key is bytearray
store.close()

session_id = str(uuid.uuid4())
save_session(session_id, str(vault_path), root_key.hex())
wipe_memory(root_key)
```

### Vault Metadata (confirmed from live vault)

```
schema_version = 2
vault_id       = 2a4fa4a8-a6a3-4829-aefe-189ff98c9eb0
created_at     = 1778964584
kdf_mode       = argon2id
totp_secret    = UENN3FEALCZHRLIKBIDTPTO3N6BY4EYH  (set during testing)
vault_hmac     = a169d6278a7bcc91dbef9e64b9499d09b745a7cb
```

**Note**: `kdf_salt` is NOT stored in vault metadata. The KDF salt is the `~/.nyxora/vault.salt` sidecar file (raw 32 bytes).

---

## 11. Vault File Locations

```
~/.nyxora/
├── vault.nyx           Main vault — SQLite, field-level encrypted
├── vault.salt          KDF salt sidecar — raw 32 bytes, REQUIRED for unlock
├── session.json        Session pointer — {"session_id": "...", "vault_path": "..."}
├── session.key         Linux fallback ONLY — root key hex (plaintext, 0o600)
│                       NOTE: docs claim encrypted — it is NOT
├── backups/
│   └── vault_backup_TIMESTAMP.nyx.bak  Encrypted backup snapshots
├── shares/
│   └── share_N_of_M.bin                Shamir secret shares (0o600)
├── *.capsule           Recovery capsule files
└── update_state.json   Last update check timestamp + rollback version
```

---

## 12. Development Environment

```bash
# Setup
cd C:\Users\scorp\dev\python\Other\nyxora\
pip install -e . --quiet          # editable install after code changes

# Run
nyx tui                           # launch TUI
nyx vault unlock                  # unlock from CLI
nyx vault info                    # show vault status

# Test
pytest tests/ -x -q --timeout=60  # full suite
pytest tests/unit/test_tui.py -v  # TUI only

# Lint/type check
ruff check src/
mypy src/

# Build
python build_release.py           # wheel + exe
```

**Tools**: VS Code devcontainer, Zellij (multiplexer), lazygit, conventional commits, branch-per-task

---

## 13. Immediate Next Steps

In priority order — do NOT skip step 1:

### Step 1 — Fix `priority=True` nav binding bug (CRITICAL)

This blocks shipping. A master password with any digit 1-7 cannot be typed.

```python
# In src/nyxora/tui/app.py

# Remove priority=True from all 7 nav bindings:
BINDINGS = [
    Binding("1", "navigate('vault')",    "Vault",    show=False),
    Binding("2", "navigate('manage')",   "Manage",   show=False),
    Binding("3", "navigate('backup')",   "Backup",   show=False),
    Binding("4", "navigate('recovery')", "Recovery", show=False),
    Binding("5", "navigate('updates')",  "Updates",  show=False),
    Binding("6", "navigate('generate')", "Generate", show=False),
    Binding("7", "navigate('security')", "Security", show=False),
    Binding("q", "quit",                 "Quit",     show=True),
    Binding("?", "show_help",            "Help",     show=True),
]

# Add check_action to suppress navigation when Input has focus:
def check_action(self, action: str, parameters: tuple) -> bool:
    if action == "navigate":
        from textual.widgets import Input
        try:
            if isinstance(self.focused, Input):
                return False
        except Exception:
            pass
    return True
```

### Step 2 — Fix Manage search field capturing keys

After removing `priority=True`, the search Input may capture 1-7 again when focused. In `manage.py`, ensure `_focus_list()` is called after every `_deferred_load()` so the Input is blurred and the ListView has focus.

### Step 3 — Fix QR code alignment and size

In `theme.tcss`:
```css
#qr-panel {
    width: 46;
    height: 100%;
    border-left: tall #1A2535;
    background: #FFFFFF;
    align: center top;
    padding: 0;
}
#totp-output {
    width: auto;
    height: auto;
    background: #FFFFFF;
    color: #000000;
    margin: 1 0 0 0;
}
```

In `recovery.py` `_render_qr()`: change `border=2` to `border=3`.

### Step 4 — Run full 9-block test plan

```
BLOCK 1 — Authentication (cold launch, wrong pw, correct pw, lock/unlock)
BLOCK 2 — Vault screen (UNLOCKED display, health check 4 green ✓)
BLOCK 3 — Manage (add, select, copy, edit, search, delete)
BLOCK 4 — Backup (list, create, verify, verify-when-locked)
BLOCK 5 — Recovery (status, TOTP QR, capsule panel, Shamir panel)
BLOCK 6 — Updates (layout, check)
BLOCK 7 — Generate (password mode, passphrase mode, copy)
BLOCK 8 — Security (weak pw, strong pw, show/hide, history, clear)
BLOCK 9 — Navigation (keys 1-7, help ?, quit q, wrong pw retry)
```

### Step 5 — Stage untracked file and bump version

```bash
git add src/nyxora/tui/screens/_shared_bg.py
```

In `src/nyxora/__init__.py`:
```python
__version__ = "3.0.0"
```

In `pyproject.toml`:
```toml
version = "3.0.0"
```

---

## 14. Final Commit Sequence

Run only after ALL test blocks pass and visual verification is confirmed:

```bash
# Stage everything including the untracked new file
git add src/nyxora/tui/screens/_shared_bg.py
git add -A

# Verify nothing is missing
git status
git diff --cached --stat

# Run tests one final time
pytest tests/ -x -q --timeout=60
# Must show: 186 passed

# Commit
git commit -m "feat(tui/v3): Nyxora v3.0.0 Nexus — complete TUI rewrite with Obsidian Tactical design

- Full TUI v3 Nexus: 7 screens + unlock/create overlays + add/edit forms
- Shared Obsidian Tactical chrome: NyxTopBar, NyxBottomBar, NyxCornerInfo, NyxSep, NyxBackground
- UnlockScreen redesigned: centered form box, corner readouts, ambient background
- All screens: top status bar, 4 corner readouts, bottom cipher bar
- Vault: dynamic lock/unlock toggle, health check with correct ForensicReport attrs
- Manage: debounced refresh, BaseException catch for typer.Exit(2), focus management
- Backup: VaultStore-based verify, proper entry count
- Recovery: split QR panel layout, full QR rendering, session guards
- Updates: module-level update_engine functions, amber version markup
- app.py: real screens wired, clear_session() on quit, focus-aware nav bindings
- launcher.py: vault-state routing for nyx tui entry point
- Fixes: lock actually clears session, UnlockScreen properly derives key from vault.salt"

# Tag
git tag -a v3.0.0 -m "Nyxora v3.0.0 — Nexus"

# Push (triggers CI)
git push origin main

# Push tag (triggers publish.yml → PyPI)
git push origin v3.0.0

# Create GitHub Release manually or via gh CLI:
gh release create v3.0.0 \
  --title "Nyxora v3.0.0 — Nexus" \
  --notes "TUI v3 Nexus release — Obsidian Tactical design, full vault lifecycle in TUI" \
  dist/nyxora-3.0.0-py3-none-any.whl \
  dist/nyxora-3.0.0.tar.gz
```

---

## 15. Full Development Roadmap

**8 stable releases total. Version structure: `$MAJOR.$MINOR.$PATCH`**

---

### Summary Timeline

```
2026-03   v1.0.0   Genesis           ✅ Stable #1 — shipped
2026-04   v2.0.0   Cipher            ✅ Stable #2 — shipped
2026-05   v2.6.6   Obsidian Tactical ✅ Stable #3 — current PyPI
2026-Q3   v3.0.0   Nexus             🔲 Stable #4 — in progress (this session)
2027-Q1   v3.5.0   Oracle            🔲 Stable #5 — planned
2027-Q3   v4.0.0   Phantom           🔲 Stable #6 — planned
2028-Q1   v4.5.0   Spectre           🔲 Stable #7 — planned
2028-Q4   v5.0.0   Sovereign         🔲 Stable #8 — planned
```

---

### ✅ Stable #1 — v1.0.0 "Genesis"
**Released: 2026-03-03 | Initial release**

- Argon2id + XChaCha20-Poly1305 field encryption
- SQLite vault with per-entry HMAC integrity
- Session manager with inactivity timeout
- HIBP breach scanning (k-anonymity — only 5-char prefix leaves machine)
- EFF diceware passphrase generator (7,776-word list)
- Shamir secret sharing + recovery capsule
- Basic CLI: vault, secret, generate, security commands

---

### ✅ Stable #2 — v2.0.0 "Cipher"
**Released: 2026-04 | Security hardening + full test suite**

- 15 audit findings resolved (security score 6.5 → 9/10)
- Atomic password change with full vault migration
- 3-pass memory wipe + mlock/VirtualLock for in-memory key protection
- 138 tests, 96.3% coverage gate
- File locker with per-file salt (nyx locker encrypt/decrypt)
- CI matrix: Ubuntu + Windows × Python 3.12/3.13/3.14
- HKDF per-entry key isolation
- Constant-time HMAC comparisons
- Schema fingerprint integrity verification

---

### ✅ Stable #3 — v2.6.x "Obsidian Tactical"
**Released: 2026-05-10 → current | Major feature expansion**

**New features in v2.6.0:**
- Textual TUI with Obsidian Tactical theme (amber on dark)
- Auto-updater with SHA-256 verification (`nyx update check/install/rollback`)
- TOTP per entry with live countdown in TUI
- Vault health score 0–100 (Grade A–F)
- Named vault profiles (`nyx vault profiles`, `nyx vault use <name>`)
- JSON output mode (`nyx --json <command>`)
- Scripting layer — `nyx script pipe / run / fzf`
- Python SDK (`from nyxora import VaultClient`)
- Recovery QR code rendered in terminal
- PyPI distribution + Windows `.exe` via PyInstaller
- Import from Bitwarden, 1Password, CSV

**Patch history:**

| Version | Date | Changes |
|---|---|---|
| v2.6.0 | 2026-05-10 | Feature release — TUI, updater, TOTP, SDK, scripting |
| v2.6.1 | 2026-05-10 | `mkdir` fix, Linux keyring fallback, wrong password message, title search, TUI keybindings, CSS `gap` → `grid-gutter` |
| v2.6.2 | 2026-05-13 | Recovery TOTP persistence, `rglob` capsule/share detection, QR code terminal rendering |
| v2.6.3 | 2026-05-13 | QR code dark-on-light (`[on black]` / `[on white]`) for camera scanning, wider quiet zone |
| v2.6.4 | 2026-05-13 | `set_metadata_value` missing from VaultStore, QR Windows Terminal solid rendering fix |
| v2.6.5 | 2026-05-18 | `nyx backup verify` auto-detects latest backup, `nyx script pipe/run` Windows built-ins via `shell=True` |
| **v2.6.6** | **2026-05-18** | **QR code half-size using Unicode half-block chars (▀▄█) — current** |

---

### 🔲 Stable #4 — v3.0.0 "Nexus"
**Target: Q3 2026 | Full TUI v3 rewrite + cross-platform expansion**

**Status: In progress — all screens built, pending final fixes and version bump**

**TUI v3 Nexus (all built this session, uncommitted):**
- Complete TUI rewrite with Obsidian Tactical v3 design system
- All 7 screens + UnlockScreen + CreateVaultScreen
- Shared chrome: NyxTopBar, NyxBottomBar, NyxCornerInfo, NyxSep, NyxBackground
- `nyx.exe` launches TUI directly (no CLI prompt) — separate entry point via `tui_launcher.py`
- Vault section: lock/unlock toggle, health check with correct ForensicReport attrs
- Manage section: 2-panel entry browser, add/edit/delete/copy/search
- Backup section: create/verify/list with VaultStore-based verify
- Recovery section: TOTP QR split panel layout, capsule, Shamir
- Updates section: version check + install
- Generate section: password + passphrase modes with strength bar
- Security section: Shannon entropy analyser, grade A+ through F

**Cross-platform:**
- macOS full support — Keychain integration, `.app` bundle, Homebrew tap
- Linux packaging — snap package + AppImage

**Security patches (ship with v3.0.1 immediately after v3.0.0):**
- Fix `migrate_from_store` TOTP loss in `change-password` (CRITICAL data loss)
- Fix `audit_log_ok = True` hardcoded in `verify_integrity()`
- Fix clipboard daemon thread in CLI (never actually clears)
- Fix `restore-capsule` (decrypts key then wipes — never creates session)
- Fix `[tui]` extra reference (no such extra in pyproject.toml)
- Remove `dist/` artifacts from repo
- Delete legacy v2 TUI screens (vault_browser.py, audit_screen.py, search_overlay.py)

**v3.1.0 security hardening (after v3.0.0 patches):**
- Persist KDF parameters in vault metadata
- Align SDK defaults with CLI defaults (critical — SDK can't open CLI vaults now)
- Atomic `change-password` (stage `.salt.new`, swap together)
- Persistent failed-attempt counter (cross-process lockout)
- Encrypted Linux session key fallback
- Real schema fingerprint over `sqlite_master` content
- Hash-chained audit log
- Updater fail-closed on checksum problems + detached signature

---

### 🔲 Stable #5 — v3.5.0 "Oracle"
**Target: Q1 2027 | Intelligence + automation**

- Password change history per entry (`nyx secret history <entry>`)
- FTS5 full-text search across all vault fields (sub-50ms on large vaults)
- `nyx daemon start` — background HIBP monitoring with notifications
- Pattern detection v2 — keyboard walks, date patterns, names, language-specific common words
- `nyx serve` — local-only REST API on Unix socket / localhost-only port
- `nyx secret bulk-update` — batch field updates by tag/filter
- `nyx vault namespace` — logical grouping without separate vault files
- `nyx config set webhook.breach_url` — POST trigger on breach detection
- Async SDK v2 (`await client.get("GitHub")`)
- Type stubs (`.pyi`) for full IDE autocompletion
- SDK documentation published to `docs/sdk.md`
- Patch versions: v3.5.1, v3.5.2 etc. for bug fixes

---

### 🔲 Stable #6 — v4.0.0 "Phantom"
**Target: Q3 2027 | Mobile + optional sync**

- iOS + Android read-only companion app
- Biometric unlock (Face ID / fingerprint) on mobile
- `nyx vault export-mobile` — encrypted, time-limited QR vault bundle (default 24h expiry)
- Self-hosted sync — S3-compatible storage (Minio, Backblaze B2, Cloudflare R2)
- Local LAN sync — zero-knowledge encrypted transfer between two machines
- `nyx vault merge` — deduplicate + resolve conflicts interactively
- `nyx vault diff <vault_a> <vault_b>` — compare two vault files
- `nyx vault snapshot` — named snapshots with rollback support
- Import v2 — KeePass XML, LastPass CSV, Chrome/Firefox password export
- **Optional Auspex GUI** — local FastAPI server with browser-based UI (not a TUI replacement)

---

### 🔲 Stable #7 — v4.5.0 "Spectre"
**Target: Q1 2028 | Teams + CI/CD integration**

- Team vaults — shared with per-user independently encrypted access
- Role-based access — admin (full + user management) / editor (add/update) / viewer (read-only)
- `nyx team create` and `nyx team invite <public-key>` — invite via public key, no account required
- Shared collections with granular permissions per collection
- GitHub Actions integration — `nyx secret inject` workflow step
- GitLab CI, Jenkins, CircleCI adapters
- SIEM-compatible audit log export (`nyx vault audit-export`)
- Webhook support for breach/rotation events
- `nyx vault namespace` — logical sub-vaults shared with specific team members

---

### 🔲 Stable #8 — v5.0.0 "Sovereign"
**Target: Q4 2028 | Post-quantum + open protocol + LTS**

- CRYSTALS-Kyber — NIST-selected post-quantum key encapsulation (replaces RSA/ECC)
- CRYSTALS-Dilithium — post-quantum digital signatures for vault integrity proofs
- Hybrid mode — PQC + classical (Argon2id + XChaCha20 still present, both layers active)
- `nyx vault upgrade-pqc` migration tool for existing vaults
- Apple Secure Enclave integration (Apple Silicon)
- TPM 2.0 v2 — vault master key sealed to TPM chip
- Nyxora Vault Format v2 (NVF2) — open, documented, auditable specification
- Third-party formal security audit — published report committed to repo
- Bug bounty program via HackerOne or similar
- LTS designation — v5.0.0 receives security patches for 3 years
- CVE assignment capability — registered CNA for Nyxora-specific vulnerabilities

---

### Patch Version Policy

Every bug fix follows this sequence before reinstalling:
```
1. Fix the bug in source
2. Bump PATCH version in __init__.py + pyproject.toml + test_sdk.py
3. Prepend CHANGELOG.md entry
4. pytest tests/ -x -q --timeout=60  (must pass)
5. git commit -m "fix(...): description"
6. git tag -a vX.Y.Z -m "Nyxora vX.Y.Z — description"
7. git push origin main && git push origin vX.Y.Z
8. GitHub Release triggers PyPI publish via OIDC
9. pipx install nyxora==X.Y.Z --force to verify
```

---

## 16. Full Codebase Audit Report

*Conducted via deep analysis of all source files. Findings reproduced verbatim.*

### Architecture Quality: 7/10

Clean layering genuinely enforced — `core/` never imports `cli/`. Data flow: master password → Argon2id → 256-bit root key → HKDF per-entry keys → XChaCha20-Poly1305 field encryption → SQLite blobs with 3-layer HMAC. Marred by the dual-session-system contradiction (documented `SessionManager` vs actual keyring-based `helpers.py`) and a dead config layer.

### Code Quality: 6/10

**Good**: Consistent naming, module docstrings, real exception hierarchy with `user_message`/`exit_code`, dataclasses, type hints throughout, mypy strict + ruff in CI, layering rule holds.

**Problems**:
1. **Coverage gaming** — 572 `# pragma: no cover` annotations exclude entire functional command bodies (backup restore/verify, recovery setup, vault creation). File names like `test_massive_coverage.py` say the quiet part out loud.
2. **Exception swallowing** — `except Exception: pass` dozens of times; `except BaseException` catches `KeyboardInterrupt`; `except (IndexError, Exception)` is a tautology.
3. **Duplication** — `_resolve_entry` copy-pasted 3×; `os.O_WRONLY | O_CREAT | O_TRUNC` secure-file-open block repeated 9+ times; `_strength_label` in manage.py reimplements `IntelEngine.score_entropy`.
4. **Dead code** — `SessionManager.terminal_hash` computed and never used; legacy TUI screens; inert config keys (`crypto.argon2_*`, `vault.auto_lock`, `backup.*`).
5. **Pseudo-security** — `secret = "\x00" * len(secret)` rebinds the name; the original immutable string is untouched. Theater next to otherwise careful `bytearray` hygiene.

### Security: 5/10

**Excellent**: Argon2id at strong parameters, XChaCha20-Poly1305 with per-entry HKDF isolation, parameterized SQL, hardened SQLite pragmas, careful key wiping.

**Non-functional claims**:
- Brute-force lockout — per-process `SessionManager`, zeroed on every `nyx vault unlock` call. SECURITY.md claims "3 failures → 5s, up to 24h".
- Session expiry — root key in keyring indefinitely. No TTL.
- Audit log integrity — `audit_ok = True` hardcoded.
- Schema tamper detection — checks hardcoded strings, not actual DB.
- 2FA — TOTP secret stored plaintext, never checked at unlock.
- Linux encrypted session — plaintext in `session.key`.
- "Quantum-Resilient" in marketing — AES-256 is quantum-tolerant at best, not quantum-resistant.

### Maintainability: 6/10

Good module boundaries. `vault_store.py` (987 lines) and `vault.py` too large. Copy-paste idioms throughout. Needs `secure_write()` helper, single `_resolve_entry`, `VaultSession` context manager.

### Test Coverage (Honest): 4/10

Real coverage well below the badge due to pragma exclusions. Critical untested paths: `change-password` migration, backup restore/verify, capsule restore end-to-end, recovery setup, TUI interaction (only instantiation smoke tests — Textual's Pilot harness unused). TUI excluded from coverage entirely (`omit = ["*/tui/*"]`).

### Performance: 8/10 (for intended scale)

- `_update_vault_hmac` re-reads all entry HMACs on every mutation → O(n) per write; import is O(n²).
- `intel.audit_all` issues one HIBP request per entry even for duplicates; dedupe by hash first.
- Locker/backup read whole files into memory — multi-GB files would OOM.
- `_build_gf256_inv_table` brute-forces 256×256 multiplications at import time (~50ms tax).

### Documentation: mixed

README and docs are polished and unusually complete. Several documented claims are false in code (lockout, expiry, integrity layers, 2FA, `[tui]` extra, "Quantum-Resilient"). Core module docstrings are honest and good — `memory_guard.py` explicitly disclaims CPython limitations.

---

## 17. GUI vs TUI Decision

**Recommendation: Keep TUI. Do not switch to GUI.**

### Why not GUI now

1. The TUI is 90% complete and working. Switching means throwing away ~3 months of Textual work — 11 screens, Obsidian Tactical design system, all session management wiring.
2. GUI framework options all have problems: Tkinter (ugly), PyQt/PySide6 (GPL or commercial license), Dear PyGui (niche), wx (dated), Toga (immature).
3. Rebuilding from scratch = minimum 4-6 weeks of work.
4. Nyxora's identity is a "tactical secrets vault for developers" — terminal-native is appropriate for the target user.
5. PyInstaller packaging is significantly harder for GUI apps (Qt requires bundling platform plugins, etc.).
6. The existing PyInstaller build would need complete rework.

### What TUI gives you that GUI cannot

- **SSH-friendly** — works over any terminal connection, headless servers, remote development
- **No display server** — works on Linux without X11/Wayland
- **Smaller binary** — no Qt/GTK dependency chain
- **Consistent rendering** — Textual renders identically on Windows Terminal, iTerm2, GNOME Terminal, Alacritty
- **Developer-appropriate** — your target users live in terminals
- **Already 90% done**

### The right path to GUI

If you want a browser-rendered GUI in the future, the correct approach is **Auspex** — a local FastAPI server that serves a web interface. This gives you:
- Full browser-rendered GUI with no framework lock-in
- Works alongside the TUI (both use the same core)
- No packaging complexity change to the existing `nyx` CLI/TUI
- Already in the roadmap for v4.0.0

**Verdict: Ship v3.0.0 TUI, then build Auspex as the GUI layer in v4.0.0.**

---

*End of HANDOFF.md — Nyxora v3.0.0 "Nexus"*
*Generated: 2026-05-22 | Chat limit reached at 100 uploaded files | Continue in new chat with this document*
