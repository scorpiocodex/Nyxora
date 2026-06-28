# Contributing to Nyxora

Thank you for your interest in Nyxora.

Nyxora is a solo-led project (ScorpioCodeX). External contributions are
welcome but subject to strict security and style review.

## Repository Structure

    src/nyxora/
    ├── cli/commands/     # Typer command modules (one per group)
    ├── cli/ui.py         # All Rich terminal output — no print() elsewhere
    ├── core/             # Cryptographic business logic
    ├── data/             # Static data files (EFF wordlist)
    └── utils/            # Config, exceptions

    tests/
    ├── unit/             # Mocked unit tests
    └── integration/      # Real on-disk vault tests (no mocks)

## Code Guidelines

- Follow the 6-layer dependency model — no layer imports from above itself
- All sensitive `bytearray` values must be wiped with `wipe_memory()` in a
  `finally` block before the function returns
- All terminal output must go through `nyxora.cli.ui` — no raw `print()`
- Never write unencrypted key material to disk or logs
- New UI output must use existing components from `ui.py` or add a new
  reusable function there — no inline Rich markup in command files
- New commands must have at least one integration test in `tests/integration/`
- Maintain the neon cyberpunk aesthetic in all Rich panels and messages

## Running Tests

    pip install -e ".[dev]"
    pytest tests/ -v --timeout=60

Coverage must remain above 80% (currently ~81%; the interactive TUI is
excluded from coverage and validated by manual real-terminal checks).

## Submitting Changes

Open an Issue before any large PR.
Contact: scorpiocodex0@gmail.com
