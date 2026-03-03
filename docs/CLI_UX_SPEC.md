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

### 3.2 Secure Clipboard (Pyperclip)
Passwords never touch the console organically. Upon fetching, the buffer streams directly into the OS clipboard and triggers a timed flush routine (default: 30 seconds) blocking memory scrapers.

### 3.3 Idempotency
Destructive interactions (shredding, mass-deletions, purging backups) aggressively prompt the user to continue via robust boolean triggers unless explicitly overridden via `--yes`.
