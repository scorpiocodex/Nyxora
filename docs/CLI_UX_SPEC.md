# NYXORA Command-Line UX Specification

## Mission Statement
NYXORA delivers a premier, Cyberpunk-inspired terminal experience, integrating bleeding-edge UX workflows over a highly complex zero-knowledge cryptographic backend. Interaction must be beautiful, deterministic, and aggressively fast.

## 1. Interface Aesthetics & Styling

### 1.1 Color Matrix
- **ELEC_PURPLE**: `color(217, 0, 255)` / `bold magenta` -> Used for critical structural borders, panel outlines, and high-level section separators.
- **NEON_CYAN**: `color(0, 255, 255)` / `bold cyan` -> Used for interactive prompts, highlights, and primary key-values.
- **SUCCESS_GREEN**: `color(0, 255, 65)` / `bold green` -> Used for affirmative state bounds (creation, unlocking).
- **CRITICAL_RED**: `color(255, 0, 85)` / `bold red` -> Used exclusively for errors, panic modes, and lethal warnings.

### 1.2 Interactive Prompts
NYXORA depends on `questionary` for context-rich injections:
- Avoid standard Python `input()`.
- Obscure password prompts natively using `questionary.password()`.
- Inject boolean constraints with `questionary.confirm()`.

### 1.3 `Rich` Components
All text dumps bypass standard stdout targeting `nyxora.cli.ui` singletons:
- Tables use Cyberpunk gradient alignments.
- Panels encompass all block data forms.
- Spinners lock state streams during HIBP calls or mass-cryptography executions.

## 2. Command Architecture

All CLI execution bindings orbit the `Typer` wrapper group setup inside `main.py` overriding default `--help` implementations.

### 2.1 The Help Renderer
Standard Typer lists are forcefully disabled. `nyxora` constructs custom ASCII titles over a 2-column Rich table array mapping logical operations:
- Groups command contexts into readable domains (Vault, Secrets, Security, Backup). 
- Injects UTF-8 Icons for immediate visual indexing.

## 3. Workflow Ergonomics

### 3.1 Lock / Unlock Sessions
Sessions are established by `vault unlock` injecting a DPAPI payload into the OS keychain. Subsequent commands instantly boot context via `load_session()`, stripping away redundant password inputs to achieve < 50ms command completion rates.

After unlock, `nyx vault status` now renders a full session dashboard showing the cipher suite, inactivity timeout, session token prefix, entry count, and failed attempt counter in a single Rich panel.

### 3.2 Secure Clipboard (Pyperclip)
Passwords never touch the console organically. Upon fetching, the buffer streams directly into the OS clipboard and triggers a timed flush routine (default: 30 seconds) blocking memory scrapers.

### 3.3 Idempotency
Destructive interactions (shredding, mass-deletions, purging backups) aggressively prompt the user to continue via robust boolean triggers unless explicitly overridden via `--yes`.

---

## 4. UI Component Library

All terminal output is produced through functions in `nyxora.cli.ui`.
Direct `print()` calls are forbidden outside this module.

### 4.1 Visual Components

| Function | Output |
|---|---|
| `entropy_bar(score)` | █████████░░░░░░░░░░░ — 20-cell block bar, 4 colour thresholds |
| `strength_badge(strength)` | `WEAK` / `FAIR` / `STRONG` / `EXCELLENT` in threshold colours |
| `checklist_panel(title, items)` | ✓ green / ✗ red per item in a bordered panel |
| `danger_panel(message)` | Full red border + content for destructive warnings |
| `session_dashboard(...)` | 7-row key-value table: STATUS, PATH, ENTRIES, SESSION, TIMEOUT, ATTEMPTS, CIPHER |
| `audit_summary_panel(...)` | Inline colour-coded summary: N scanned · X BREACHED · Y WEAK · Z REUSED |

### 4.2 Entropy Colour Scale

| Range | Colour | Label |
|---|---|---|
| 0–29 bits | `#FF3131` red | WEAK |
| 30–49 bits | `#FFB000` amber | FAIR |
| 50–69 bits | `#00FFFF` cyan | STRONG |
| 70+ bits | `#00FF41` green | EXCELLENT |

### 4.3 Clipboard Handling

After any `--copy` operation, `clipboard_countdown(30)` launches a daemon
thread that clears the clipboard after 30 seconds and prints a dim
confirmation. The main thread is never blocked.

---

## 5. Exit Code Standard

| Code | Trigger | Meaning |
|---|---|---|
| 0 | Success | Command completed normally |
| 1 | `NyxoraError` | General error — see panel message |
| 2 | `VaultLockedError` | Vault is locked — run `nyx vault unlock` |
| 3 | `BruteForceLockedError` | Too many failures — lockout active |
| 4 | `nyx vault panic` | Emergency wipe — all session data destroyed |

---

## 6. New Commands (v2.0.0)

### nyx vault import
Bulk-import from CSV, Bitwarden JSON, 1Password CSV, or Nyxora JSON.
- `--format auto|csv|json|bitwarden|1password` — format override
- `--dry-run` — preview without writing
- `--yes` — skip confirmation prompt

### nyx generate password --min-strength
Regenerates up to 10 times until the entropy threshold is met.
- Values: `weak` / `fair` / `strong` / `excellent`

### nyx generate passphrase --count / -n
Generate multiple passphrases in one call.
Wordlist: full EFF large wordlist (7,776 words, ~64.6 bits / 5 words).

### nyx secret update --tags / --custom
- `--tags` — replace the full tag list
- `--custom key=value,...` — set custom fields
