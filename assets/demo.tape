# assets/demo.tape — Nyxora TUI walkthrough: unlock -> tour of every section.
#
# PRE-REQ: seed the throwaway demo vault first (3 dummy entries, left locked):
#     NYXORA_HOME=/tmp/nyx_demo bash assets/demo_seed.sh
# Then regenerate the GIF with:
#     vhs assets/demo.tape
Output assets/demo.gif

Set Shell "bash"
Set FontFamily "JetBrains Mono"
Set FontSize 18
Set Width 1280
Set Height 820
Set Padding 24
Set TypingSpeed 55ms
Set Theme "Catppuccin Mocha"

# Environment set in-shell (exported so the `nyx` child process inherits it
# reliably). nyx lives in a local venv; NYXORA_HOME points at the seeded vault.
Hide
Type "export PATH=/home/san/.nyx-demo/bin:$PATH"
Enter
Type "export NYXORA_HOME=/tmp/nyx_demo"
Enter
Type "export PYTHON_KEYRING_BACKEND=keyrings.alt.file.PlaintextKeyring"
Enter
Type "clear"
Enter
Sleep 300ms
Show

# ---- unlock ----
Type "nyx tui"
Enter
Sleep 3500ms
Type "DemoPass123!"
Sleep 700ms
Enter
Sleep 2500ms

# ---- tour every section ----
# Unlock lands on Manage (Section 2); browse the seeded entries.
Down
Sleep 700ms
Down
Sleep 1500ms
# Backup (3). Digit-nav works here because the entry list (a ListView) is
# focused.
Type "3"
Sleep 2200ms
# Move focus to the sidebar nav-list (also a ListView). Section screens focus a
# Button/Input on entry, which blocks the App's 1-7 navigate bindings; parking
# focus on the sidebar keeps digit-nav working for the rest of the tour.
Shift+Tab
Sleep 800ms
# Recovery (4), Updates (5), Generate (6), Security (7), back to Vault (1).
Type "4"
Sleep 2200ms
Type "5"
Sleep 2000ms
Type "6"
Sleep 2200ms
Type "7"
Sleep 2200ms
Type "1"
Sleep 1800ms
Type "q"
Sleep 1000ms
