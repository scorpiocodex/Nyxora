# Contributing to Nyxora

Thank you for your interest in Nyxora.

Currently, Nyxora (led exclusively by ScorpioCodeX) is an independent password intelligence vault. The complete architecture, core engine, and security parameters belong entirely to a single developer structure. 

## Code Guidelines
- Any external PRs will be strictly audited.
- Keep the neon cyberpunk aesthetic across all textual CLI UI components (via Rich).
- DO NOT introduce any unencrypted I/O inside the core logic modules (`crypto_engine`, `vault_store`).
- Always use `nyxora.core.memory_guard.wipe_memory()` on bytearrays that store plaintext keys!

If you wish to submit bug reports or propose radical overhauls, please open an Issue first or contact `scorpiocodex0@gmail.com`.
