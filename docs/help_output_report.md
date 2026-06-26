# Nyxora CLI Help Output Report
## v3.0.1 — regenerated 2026-06-26

## nyx --help (✅ PASS)
```console
$ nyx --help

 Usage: nyx [OPTIONS] COMMAND [ARGS]...

 ███╗   ██╗██╗   ██╗██╗  ██╗ ██████╗ ██████╗  █████╗ ████╗  ██║╚██╗
 ██╔╝╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗ ██╔██╗ ██║ ╚████╔╝  ╚███╔╝ ██║
 ██║██████╔╝███████║ ██║╚██╗██║  ╚██╔╝   ██╔██╗ ██║   ██║██╔══██╗██╔══██║ ██║
 ╚████║   ██║   ██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║ ╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝

 NYXORA — Next-Generation Password Intelligence Vault.

 Offline • Zero-Knowledge • Terminal-Native

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --version             -v        Show version and exit.                      │
│ --json                          Output results as JSON (for scripting).     │
│ --install-completion            Install completion for the current shell.   │
│ --show-completion               Show completion for the current shell, to   │
│                                 copy it or customize the installation.      │
│ --help                          Show this message and exit.                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 🔑 Core Operations ────────────────────────────────────────────────────────┐
│ vault     Vault lifecycle: unlock, lock, health-check.                      │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 🔒 Secrets Management ─────────────────────────────────────────────────────┐
│ secret    Manage vault entries: add, list, get, update, delete.             │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ ⚡ Generators & Tools ─────────────────────────────────────────────────────┐
│ generate  Generate credentials: passwords, passphrases, API keys, SSH keys. │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 🛡️ Security & Intelligence ────────────────────────────────────────────────┐
│ security  Audit and forensics: breach scan, logs, integrity.                │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 💾 Data Portability ───────────────────────────────────────────────────────┐
│ backup    Manage backups: restore, export, verify.                          │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 🚑 Emergency Access ───────────────────────────────────────────────────────┐
│ recovery  Emergency recovery: TOTP setup, capsules, secret splitting.       │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 📁 File Locker ────────────────────────────────────────────────────────────┐
│ locker    File encryption: encrypt/decrypt arbitrary files.                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 🔄 Updates ────────────────────────────────────────────────────────────────┐
│ update    Manage updates: check, install, rollback.                         │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ ⚙️  Scripting & Integration ───────────────────────────────────────────────┐
│ script    Scripting tools: pipe, run, fzf integration.                      │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ 🖥️  Interactive ───────────────────────────────────────────────────────────┐
│ tui       Interactive vault browser — Obsidian Tactical TUI.                │
└─────────────────────────────────────────────────────────────────────────────┘

 Execute nyx <command> --help for encrypted module instructions.
```

---

## nyx vault --help (✅ PASS)
```console
$ nyx vault --help

 Usage: nyx vault [OPTIONS] COMMAND [ARGS]...

 Vault lifecycle: unlock, lock, health-check.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ unlock           Unlock the vault with master password.                     │
│ init             Initialize a new vault.                                    │
│ change-password  Change the master password for the current vault.          │
│ lock             Lock the vault and wipe the session key.                   │
│ panic            PANIC — immediately wipe session and exit.                 │
│ status           Show vault lock state and entry count.                     │
│ health-check     Run a full integrity verification of the vault.            │
│ profiles         List all vault profiles.                                   │
│ use              Switch to a named vault profile.                           │
│ add-profile      Register a new vault profile.                              │
│ remove-profile   Remove a vault profile (does not delete the vault file).   │
│ import           Import entries from CSV, JSON, Bitwarden, or 1Password     │
│                  export.                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx vault import --help (✅ PASS)
```console
$ nyx vault import --help

 Usage: nyx vault import [OPTIONS] FILE

 Import entries from CSV, JSON, Bitwarden, or 1Password export.

┌─ Arguments ─────────────────────────────────────────────────────────────────┐
│ *    file      PATH  File to import [required]                              │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --format   -f      TEXT  Format: auto, csv, json, bitwarden, 1password      │
│                          [default: auto]                                    │
│ --dry-run                Preview import without writing to vault            │
│ --yes      -y            Skip confirmation                                  │
│ --help                   Show this message and exit.                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx secret --help (✅ PASS)
```console
$ nyx secret --help

 Usage: nyx secret [OPTIONS] COMMAND [ARGS]...

 Manage vault entries: add, list, get, update, delete.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ add     Add a new secret entry to the vault.                                │
│ list    List all vault entries.                                             │
│ get     Get and display a vault entry.                                      │
│ update  Update fields on an existing entry.                                 │
│ delete  Delete (soft) an entry from the vault.                              │
│ search  Search entries by title, username, URL, or tags.                    │
│ totp    Show the live TOTP code for an entry.                               │
│ clone   Clone an entry with a new title and ID.                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx secret update --help (✅ PASS)
```console
$ nyx secret update --help

 Usage: nyx secret update [OPTIONS] ENTRY_ID

 Update fields on an existing entry.

┌─ Arguments ─────────────────────────────────────────────────────────────────┐
│ *    entry_id      TEXT  Entry ID [required]                                │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --title        -t      TEXT                                                 │
│ --username     -u      TEXT                                                 │
│ --url                  TEXT                                                 │
│ --notes                TEXT                                                 │
│ --tags                 TEXT  Comma-separated tags (replaces existing)       │
│ --totp-secret          TEXT  TOTP base32 secret to store with this entry    │
│                              ('' to clear)                                  │
│ --help                       Show this message and exit.                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx generate --help (✅ PASS)
```console
$ nyx generate --help

 Usage: nyx generate [OPTIONS] COMMAND [ARGS]...

 Generate credentials: passwords, passphrases, API keys, SSH keys.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ password    Generate a cryptographically secure random password.            │
│ passphrase  Generate a diceware-style passphrase.                           │
│ api-key     Generate a cryptographically secure API key.                    │
│ ssh-key     Generate an SSH key pair.                                       │
│ entropy     Analyze the entropy and patterns of a password.                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx generate password --help (✅ PASS)
```console
$ nyx generate password --help

 Usage: nyx generate password [OPTIONS]

 Generate a cryptographically secure random password.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --length        -l      INTEGER  Password length [default: 24]              │
│ --count         -n      INTEGER  Number of passwords to generate            │
│                                  [default: 1]                               │
│ --no-symbols                     Exclude symbols                            │
│ --no-digits                      Exclude digits                             │
│ --no-upper                       Exclude uppercase                          │
│ --min-strength          TEXT     Minimum strength: weak, fair, strong,      │
│                                  excellent                                  │
│ --help                           Show this message and exit.                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx generate passphrase --help (✅ PASS)
```console
$ nyx generate passphrase --help

 Usage: nyx generate passphrase [OPTIONS]

 Generate a diceware-style passphrase.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --words       -w      INTEGER  Number of words [default: 5]                 │
│ --separator   -s      TEXT     Word separator [default: -]                  │
│ --capitalize                   Capitalize first letter of each word         │
│ --copy        -c               Copy the generated passphrase to clipboard   │
│ --count       -n      INTEGER  Number of passphrases to generate            │
│                                [default: 1]                                 │
│ --help                         Show this message and exit.                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx security --help (✅ PASS)
```console
$ nyx security --help

 Usage: nyx security [OPTIONS] COMMAND [ARGS]...

 Audit and forensics: breach scan, logs, integrity.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ audit        Run a full security audit of all vault entries.                │
│ stats        Show vault statistics: entry count, age distribution, tag      │
│              counts.                                                        │
│ log          Display the audit log.                                         │
│ forensic     Run a full forensic integrity check and display detailed       │
│              results.                                                       │
│ breach-scan  Check all vault passwords against HaveIBeenPwned.              │
│ due          List entries whose password hasn't changed in N days.          │
│ health       Show vault security health score and breakdown.                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx backup --help (✅ PASS)
```console
$ nyx backup --help

 Usage: nyx backup [OPTIONS] COMMAND [ARGS]...

 Manage backups: restore, export, verify.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ create   Create an encrypted backup of the vault.                           │
│ list     List available backups.                                            │
│ restore  Restore a vault from a backup file.                                │
│ cleanup  Delete oldest backups, keeping the most recent N.                  │
│ verify   Verify the integrity of a backup file.                             │
│ export   Export vault entries to a file.                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx recovery --help (✅ PASS)
```console
$ nyx recovery --help

 Usage: nyx recovery [OPTIONS] COMMAND [ARGS]...

 Emergency recovery: TOTP setup, capsules, secret splitting.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ setup            Set up TOTP two-factor authentication.                     │
│ create-capsule   Create an emergency recovery capsule.                      │
│ restore-capsule  Restore vault access from a recovery capsule.              │
│ split-secret     Split the vault root key into N Shamir shares (K required  │
│                  to reconstruct).                                           │
│ status           Show recovery configuration status.                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx locker --help (✅ PASS)
```console
$ nyx locker --help

 Usage: nyx locker [OPTIONS] COMMAND [ARGS]...

 File encryption: encrypt/decrypt arbitrary files.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ encrypt  Encrypt a file with the vault key. Outputs a .nyx file.            │
│ decrypt  Decrypt a .nyx file with the vault key.                            │
│ list     List encrypted .nyx files in the locker directory.                 │
│ shred    Securely shred a file with 3-pass overwrite.                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx update --help (✅ PASS)
```console
$ nyx update --help

 Usage: nyx update [OPTIONS] COMMAND [ARGS]...

 Manage updates: check, install, rollback.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ check     Check for available Nyxora updates.                               │
│ install   Download and install the latest Nyxora release.                   │
│ rollback  Roll back to the previous Nyxora version.                         │
│ channel   Set the update channel (stable or pre-release).                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx script --help (✅ PASS)
```console
$ nyx script --help

 Usage: nyx script [OPTIONS] COMMAND [ARGS]...

 Scripting tools: pipe, run, fzf integration.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌─ Commands ──────────────────────────────────────────────────────────────────┐
│ pipe  Pipe a vault field into a command's stdin.                            │
│ run   Run a command with vault credentials injected as environment          │
│       variables.                                                            │
│ fzf   Open an fzf fuzzy-finder over vault entries.                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## nyx tui --help (✅ PASS)
```console
$ nyx tui --help

 Usage: nyx tui [OPTIONS] COMMAND [ARGS]...

 Interactive vault browser — Obsidian Tactical TUI.

┌─ Options ───────────────────────────────────────────────────────────────────┐
│ --help          Show this message and exit.                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```
