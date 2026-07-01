#!/usr/bin/env bash
# Seed an isolated, throwaway demo vault for the VHS recording (assets/demo.tape).
#
# Run this ONCE before `vhs assets/demo.tape`:
#     NYXORA_HOME=/tmp/nyx_demo bash assets/demo_seed.sh
#
# It creates three dummy entries (NO real secrets) and leaves the vault LOCKED,
# so the recording opens on the unlock screen. Requires `nyx` on PATH.
#
# Why seed here and not inside the tape: `nyx` prompts via prompt_toolkit, which
# reads from /dev/tty (not stdin) when a TTY is present, so piped answers are
# ignored inside VHS's PTY. Seeding out-of-band avoids that entirely.
set -euo pipefail

export NYXORA_HOME="${NYXORA_HOME:-/tmp/nyx_demo}"
# File-based keyring so the unlock session persists across the CLI calls below
# in a headless environment with no gnome-keyring / D-Bus.
export PYTHON_KEYRING_BACKEND="${PYTHON_KEYRING_BACKEND:-keyrings.alt.file.PlaintextKeyring}"

rm -rf "$NYXORA_HOME"
mkdir -p "$NYXORA_HOME"

# init prompts twice (Master / Confirm) and leaves a persistent session.
printf 'DemoPass123!\nDemoPass123!\n' | nyx vault init

# `secret add` also prompts for URL + Notes (both optional); the two blank
# lines from `printf '\n\n'` accept the defaults. Session covers auth.
while IFS='|' read -r title user; do
  [ -n "$title" ] || continue
  printf '\n\n' | nyx secret add -t "$title" -u "$user" --generate
done <<'ENTRIES'
GitHub|octocat
AWS Console|admin@demo.io
Gmail|demo@nyxora.dev
ENTRIES

nyx vault lock
echo "Seeded ${NYXORA_HOME} (locked, 3 entries)."
