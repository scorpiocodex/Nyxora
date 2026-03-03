# Nyxora CLI Help Output Report

## nyx --help (✅ PASS)
```console
$ nyx --help
Usage: nyx [OPTIONS] COMMAND [ARGS]...                                       
                                                                              
 NYXORA — Next-Generation Password Intelligence Vault.                        
                                                                              
 Offline • Zero-Knowledge • Terminal-Native • Quantum-Resilient               
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --version             -v        Show version and exit.                     │
│ --install-completion            Install completion for the current shell.  │
│ --show-completion               Show completion for the current shell, to  │
│                                 copy it or customize the installation.     │
│ --help                          Show this message and exit.                │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ 🔑 Core Operations ───────────────────────────────────────────────────────╮
│ vault     Vault lifecycle: unlock, lock, health-check.                     │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ 🔒 Secrets Management ────────────────────────────────────────────────────╮
│ secret    Manage vault entries: add, list, get, update, delete.            │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ ⚡ Generators & Tools ────────────────────────────────────────────────────╮
│ generate  Generate credentials: passwords, passphrases, API keys, SSH      │
│           keys.                                                            │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ 🛡️ Security & Intelligence ───────────────────────────────────────────────╮
│ security  Audit and forensics: breach scan, logs, integrity.               │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ 💾 Data Portability ──────────────────────────────────────────────────────╮
│ backup    Manage backups: restore, export, verify.                         │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ 🚑 Emergency Access ──────────────────────────────────────────────────────╮
│ recovery  Emergency recovery: TOTP setup, capsules, secret splitting.      │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ 📁 File Locker ───────────────────────────────────────────────────────────╮
│ locker    File encryption: encrypt/decrypt arbitrary files.                │
╰────────────────────────────────────────────────────────────────────────────╯
                                                                              
 Execute nyx <command> --help for encrypted module instructions.
```

## nyx vault --help (✅ PASS)
```console
$ nyx vault --help
Usage: nyx vault [OPTIONS] COMMAND [ARGS]...                                 
                                                                              
 Vault lifecycle: unlock, lock, health-check.                                 
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ unlock           Unlock the vault with master password.                    │
│ init             Initialize a new vault.                                   │
│ change-password  Change the master password for the current vault.         │
│ lock             Lock the vault and wipe the session key.                  │
│ panic            PANIC — immediately wipe session and exit.                │
│ status           Show vault lock state and entry count.                    │
│ health-check     Run a full integrity verification of the vault.           │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx vault unlock --help (✅ PASS)
```console
$ nyx vault unlock --help
Usage: nyx vault unlock [OPTIONS]                                            
                                                                              
 Unlock the vault with master password.                                       
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --vault   -v      PATH  Path to vault file.                                │
│ --create                Create a new vault if it doesn't exist.            │
│ --help                  Show this message and exit.                        │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx vault init --help (✅ PASS)
```console
$ nyx vault init --help
Usage: nyx vault init [OPTIONS]                                              
                                                                              
 Initialize a new vault.                                                      
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --vault  -v      PATH  Path to vault file.                                 │
│ --help                 Show this message and exit.                         │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx vault lock --help (✅ PASS)
```console
$ nyx vault lock --help
Usage: nyx vault lock [OPTIONS]                                              
                                                                              
 Lock the vault and wipe the session key.                                     
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx vault panic --help (✅ PASS)
```console
$ nyx vault panic --help
Usage: nyx vault panic [OPTIONS]                                             
                                                                              
 PANIC — immediately wipe session and exit.                                   
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx vault status --help (✅ PASS)
```console
$ nyx vault status --help
Usage: nyx vault status [OPTIONS]                                            
                                                                              
 Show vault lock state and entry count.                                       
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx vault health-check --help (✅ PASS)
```console
$ nyx vault health-check --help
Usage: nyx vault health-check [OPTIONS]                                      
                                                                              
 Run a full integrity verification of the vault.                              
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx vault change-password --help (✅ PASS)
```console
$ nyx vault change-password --help
Usage: nyx vault change-password [OPTIONS]                                   
                                                                              
 Change the master password for the current vault.                            
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx secret --help (✅ PASS)
```console
$ nyx secret --help
Usage: nyx secret [OPTIONS] COMMAND [ARGS]...                                
                                                                              
 Manage vault entries: add, list, get, update, delete.                        
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ add     Add a new secret entry to the vault.                               │
│ list    List all vault entries.                                            │
│ get     Get and display a vault entry.                                     │
│ update  Update fields on an existing entry.                                │
│ delete  Delete (soft) an entry from the vault.                             │
│ search  Search entries by title, username, URL, or tags.                   │
│ clone   Clone an entry with a new title and ID.                            │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx secret add --help (✅ PASS)
```console
$ nyx secret add --help
Usage: nyx secret add [OPTIONS]                                              
                                                                              
 Add a new secret entry to the vault.                                         
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --title     -t      TEXT                                                   │
│ --username  -u      TEXT                                                   │
│ --url               TEXT                                                   │
│ --tags              TEXT  Comma-separated tags                             │
│ --generate  -g            Auto-generate password                           │
│ --help                    Show this message and exit.                      │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx secret list --help (✅ PASS)
```console
$ nyx secret list --help
Usage: nyx secret list [OPTIONS]                                             
                                                                              
 List all vault entries.                                                      
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --tag                   TEXT  Filter by tag                                │
│ --show-passwords              Show passwords in table                      │
│ --help                        Show this message and exit.                  │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx secret get --help (✅ PASS)
```console
$ nyx secret get --help
Usage: nyx secret get [OPTIONS] ENTRY_ID                                     
                                                                              
 Get and display a vault entry.                                               
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    entry_id      TEXT  Entry ID (or prefix) [required]                   │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --copy  -c        Copy password to clipboard                               │
│ --help            Show this message and exit.                              │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx secret update --help (✅ PASS)
```console
$ nyx secret update --help
Usage: nyx secret update [OPTIONS] ENTRY_ID                                  
                                                                              
 Update fields on an existing entry.                                          
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    entry_id      TEXT  Entry ID [required]                               │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --title     -t      TEXT                                                   │
│ --username  -u      TEXT                                                   │
│ --password  -p      TEXT                                                   │
│ --url               TEXT                                                   │
│ --notes             TEXT                                                   │
│ --help                    Show this message and exit.                      │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx secret delete --help (✅ PASS)
```console
$ nyx secret delete --help
Usage: nyx secret delete [OPTIONS] ENTRY_ID                                  
                                                                              
 Delete (soft) an entry from the vault.                                       
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    entry_id      TEXT  Entry ID [required]                               │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --yes   -y        Skip confirmation                                        │
│ --help            Show this message and exit.                              │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx secret search --help (✅ PASS)
```console
$ nyx secret search --help
Usage: nyx secret search [OPTIONS] QUERY                                     
                                                                              
 Search entries by title, username, URL, or tags.                             
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    query      TEXT  Search query [required]                              │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx secret clone --help (✅ PASS)
```console
$ nyx secret clone --help
Usage: nyx secret clone [OPTIONS] ENTRY_ID                                   
                                                                              
 Clone an entry with a new title and ID.                                      
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    entry_id      TEXT  Entry ID to clone [required]                      │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --title  -t      TEXT  Title for the clone                                 │
│ --help                 Show this message and exit.                         │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx generate --help (✅ PASS)
```console
$ nyx generate --help
Usage: nyx generate [OPTIONS] COMMAND [ARGS]...                              
                                                                              
 Generate credentials: passwords, passphrases, API keys, SSH keys.            
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ password    Generate a cryptographically secure random password.           │
│ passphrase  Generate a diceware-style passphrase.                          │
│ api-key     Generate a cryptographically secure API key.                   │
│ ssh-key     Generate an SSH key pair.                                      │
│ entropy     Analyze the entropy and patterns of a password.                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx generate password --help (✅ PASS)
```console
$ nyx generate password --help
Usage: nyx generate password [OPTIONS]                                       
                                                                              
 Generate a cryptographically secure random password.                         
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --length      -l      INTEGER  Password length [default: 24]               │
│ --count       -n      INTEGER  Number of passwords to generate             │
│                                [default: 1]                                │
│ --no-symbols                   Exclude symbols                             │
│ --no-digits                    Exclude digits                              │
│ --no-upper                     Exclude uppercase                           │
│ --help                         Show this message and exit.                 │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx generate passphrase --help (✅ PASS)
```console
$ nyx generate passphrase --help
Usage: nyx generate passphrase [OPTIONS]                                     
                                                                              
 Generate a diceware-style passphrase.                                        
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --words       -w      INTEGER  Number of words [default: 5]                │
│ --separator   -s      TEXT     Word separator [default: -]                 │
│ --capitalize                   Capitalize first letter of each word        │
│ --copy        -c               Copy the generated passphrase to clipboard  │
│ --help                         Show this message and exit.                 │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx generate api-key --help (✅ PASS)
```console
$ nyx generate api-key --help
Usage: nyx generate api-key [OPTIONS]                                        
                                                                              
 Generate a cryptographically secure API key.                                 
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --length  -l      INTEGER  Key length in bytes [default: 32]               │
│ --prefix  -p      TEXT     Key prefix                                      │
│ --copy    -c               Copy the generated key to clipboard             │
│ --help                     Show this message and exit.                     │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx generate ssh-key --help (✅ PASS)
```console
$ nyx generate ssh-key --help
Usage: nyx generate ssh-key [OPTIONS]                                        
                                                                              
 Generate an SSH key pair.                                                    
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --output      -o      TEXT  Output file prefix                             │
│ --algorithm   -a      TEXT  ed25519 or rsa [default: ed25519]              │
│ --passphrase  -p            Encrypt the private key with a passphrase      │
│ --help                      Show this message and exit.                    │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx generate entropy --help (✅ PASS)
```console
$ nyx generate entropy --help
Usage: nyx generate entropy [OPTIONS] PASSWORD                               
                                                                              
 Analyze the entropy and patterns of a password.                              
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    password      TEXT  Password to analyze [required]                    │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx security --help (✅ PASS)
```console
$ nyx security --help
Usage: nyx security [OPTIONS] COMMAND [ARGS]...                              
                                                                              
 Audit and forensics: breach scan, logs, integrity.                           
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ audit        Run a full security audit of all vault entries.               │
│ stats        Show vault statistics: entry count, age distribution, tag     │
│              counts.                                                       │
│ log          Display the audit log.                                        │
│ forensic     Run a full forensic integrity check and display detailed      │
│              results.                                                      │
│ breach-scan  Check all vault passwords against HaveIBeenPwned.             │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx security audit --help (✅ PASS)
```console
$ nyx security audit --help
Usage: nyx security audit [OPTIONS]                                          
                                                                              
 Run a full security audit of all vault entries.                              
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --no-hibp          Skip HIBP breach check                                  │
│ --help             Show this message and exit.                             │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx security stats --help (✅ PASS)
```console
$ nyx security stats --help
Usage: nyx security stats [OPTIONS]                                          
                                                                              
 Show vault statistics: entry count, age distribution, tag counts.            
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx security log --help (✅ PASS)
```console
$ nyx security log --help
Usage: nyx security log [OPTIONS]                                            
                                                                              
 Display the audit log.                                                       
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --limit    -n      INTEGER  Number of events to show [default: 20]         │
│ --type     -t      TEXT     Filter by event type                           │
│ --reverse  -r               Show newest events first                       │
│ --help                      Show this message and exit.                    │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx security forensic --help (✅ PASS)
```console
$ nyx security forensic --help
Usage: nyx security forensic [OPTIONS]                                       
                                                                              
 Run a full forensic integrity check and display detailed results.            
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx security breach-scan --help (✅ PASS)
```console
$ nyx security breach-scan --help
Usage: nyx security breach-scan [OPTIONS]                                    
                                                                              
 Check all vault passwords against HaveIBeenPwned.                            
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx backup --help (✅ PASS)
```console
$ nyx backup --help
Usage: nyx backup [OPTIONS] COMMAND [ARGS]...                                
                                                                              
 Manage backups: restore, export, verify.                                     
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ create   Create an encrypted backup of the vault.                          │
│ list     List available backups.                                           │
│ restore  Restore a vault from a backup file.                               │
│ cleanup  Delete oldest backups, keeping the most recent N.                 │
│ verify   Verify the integrity of a backup file.                            │
│ export   Export vault entries to a file.                                   │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx backup create --help (✅ PASS)
```console
$ nyx backup create --help
Usage: nyx backup create [OPTIONS]                                           
                                                                              
 Create an encrypted backup of the vault.                                     
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --dir   -d      PATH  Backup directory                                     │
│ --note  -n      TEXT  Backup note                                          │
│ --help                Show this message and exit.                          │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx backup list --help (✅ PASS)
```console
$ nyx backup list --help
Usage: nyx backup list [OPTIONS]                                             
                                                                              
 List available backups.                                                      
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --dir   -d      PATH                                                       │
│ --help                Show this message and exit.                          │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx backup restore --help (✅ PASS)
```console
$ nyx backup restore --help
Usage: nyx backup restore [OPTIONS] BACKUP_FILE                              
                                                                              
 Restore a vault from a backup file.                                          
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    backup_file      PATH  Backup file to restore [required]              │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx backup cleanup --help (✅ PASS)
```console
$ nyx backup cleanup --help
Usage: nyx backup cleanup [OPTIONS]                                          
                                                                              
 Delete oldest backups, keeping the most recent N.                            
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --keep  -k      INTEGER  Number of backups to keep [default: 10]           │
│ --dir   -d      PATH                                                       │
│ --help                   Show this message and exit.                       │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx backup verify --help (✅ PASS)
```console
$ nyx backup verify --help
Usage: nyx backup verify [OPTIONS] BACKUP_FILE                               
                                                                              
 Verify the integrity of a backup file.                                       
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    backup_file      PATH  Backup file to verify [required]               │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx backup export --help (✅ PASS)
```console
$ nyx backup export --help
Usage: nyx backup export [OPTIONS] OUTPUT                                    
                                                                              
 Export vault entries to a file.                                              
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    output      PATH  Output file path [required]                         │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --plaintext          Export as plain CSV (INSECURE)                        │
│ --help               Show this message and exit.                           │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx recovery --help (✅ PASS)
```console
$ nyx recovery --help
Usage: nyx recovery [OPTIONS] COMMAND [ARGS]...                              
                                                                              
 Emergency recovery: TOTP setup, capsules, secret splitting.                  
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ setup            Set up TOTP two-factor authentication.                    │
│ create-capsule   Create an emergency recovery capsule.                     │
│ restore-capsule  Restore vault access from a recovery capsule.             │
│ split-secret     Split the vault root key into N Shamir shares (K required │
│                  to reconstruct).                                          │
│ status           Show recovery configuration status.                       │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx recovery setup --help (✅ PASS)
```console
$ nyx recovery setup --help
Usage: nyx recovery setup [OPTIONS]                                          
                                                                              
 Set up TOTP two-factor authentication.                                       
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx recovery create-capsule --help (✅ PASS)
```console
$ nyx recovery create-capsule --help
Usage: nyx recovery create-capsule [OPTIONS] OUTPUT                          
                                                                              
 Create an emergency recovery capsule.                                        
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    output      PATH  Output path for recovery capsule [required]         │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --hint        TEXT  Password hint (stored in capsule)                      │
│ --help              Show this message and exit.                            │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx recovery restore-capsule --help (✅ PASS)
```console
$ nyx recovery restore-capsule --help
Usage: nyx recovery restore-capsule [OPTIONS] CAPSULE                        
                                                                              
 Restore vault access from a recovery capsule.                                
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    capsule      PATH  Recovery capsule file [required]                   │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx recovery split-secret --help (✅ PASS)
```console
$ nyx recovery split-secret --help
Usage: nyx recovery split-secret [OPTIONS]                                   
                                                                              
 Split the vault root key into N Shamir shares (K required to reconstruct).   
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --shares      -n      INTEGER  Total number of shares [default: 5]         │
│ --threshold   -k      INTEGER  Shares required to reconstruct [default: 3] │
│ --output-dir  -o      PATH     [default: .]                                │
│ --help                         Show this message and exit.                 │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx recovery status --help (✅ PASS)
```console
$ nyx recovery status --help
Usage: nyx recovery status [OPTIONS]                                         
                                                                              
 Show recovery configuration status.                                          
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx locker --help (✅ PASS)
```console
$ nyx locker --help
Usage: nyx locker [OPTIONS] COMMAND [ARGS]...                                
                                                                              
 File encryption: encrypt/decrypt arbitrary files.                            
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────╮
│ encrypt  Encrypt a file with the vault key. Outputs a .nyx file.           │
│ decrypt  Decrypt a .nyx file with the vault key.                           │
│ list     List encrypted .nyx files in the locker directory.                │
│ shred    Securely shred a file with 3-pass overwrite.                      │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx locker encrypt --help (✅ PASS)
```console
$ nyx locker encrypt --help
Usage: nyx locker encrypt [OPTIONS] FILE                                     
                                                                              
 Encrypt a file with the vault key. Outputs a .nyx file.                      
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    file      PATH  File to encrypt [required]                            │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --output  -o      PATH  Output path                                        │
│ --delete                Shred original after encryption                    │
│ --help                  Show this message and exit.                        │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx locker decrypt --help (✅ PASS)
```console
$ nyx locker decrypt --help
Usage: nyx locker decrypt [OPTIONS] FILE                                     
                                                                              
 Decrypt a .nyx file with the vault key.                                      
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    file      PATH  .nyx file to decrypt [required]                       │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --output  -o      PATH  Output path                                        │
│ --help                  Show this message and exit.                        │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx locker list --help (✅ PASS)
```console
$ nyx locker list --help
Usage: nyx locker list [OPTIONS]                                             
                                                                              
 List encrypted .nyx files in the locker directory.                           
                                                                              
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --dir   -d      PATH                                                       │
│ --help                Show this message and exit.                          │
╰────────────────────────────────────────────────────────────────────────────╯
```

## nyx locker shred --help (✅ PASS)
```console
$ nyx locker shred --help
Usage: nyx locker shred [OPTIONS] FILE                                       
                                                                              
 Securely shred a file with 3-pass overwrite.                                 
                                                                              
╭─ Arguments ────────────────────────────────────────────────────────────────╮
│ *    file      PATH  File to securely delete [required]                    │
╰────────────────────────────────────────────────────────────────────────────╯
╭─ Options ──────────────────────────────────────────────────────────────────╮
│ --yes   -y        Skip confirmation                                        │
│ --help            Show this message and exit.                              │
╰────────────────────────────────────────────────────────────────────────────╯
```

