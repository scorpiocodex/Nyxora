# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Nyxora Windows standalone executable.

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
SRC  = ROOT / "src"
DATA = ROOT / "src" / "nyxora" / "data"
ASSETS = ROOT / "assets"

block_cipher = None

a = Analysis(
    [str(SRC / "nyxora" / "cli" / "main.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=[
        (str(DATA / "eff_large_wordlist.txt"), "nyxora/data"),
        (str(ROOT / "src" / "nyxora" / "tui" / "theme.tcss"),
         "nyxora/tui"),
    ],
    hiddenimports=[
        "nyxora",
        "nyxora.cli",
        "nyxora.cli.commands.vault",
        "nyxora.cli.commands.secret",
        "nyxora.cli.commands.generate",
        "nyxora.cli.commands.security",
        "nyxora.cli.commands.backup",
        "nyxora.cli.commands.recovery",
        "nyxora.cli.commands.locker",
        "nyxora.cli.commands.update",
        "nyxora.cli.commands.scripting",
        "nyxora.cli.commands.tui_cmd",
        "nyxora.cli.commands.import_",
        "nyxora.core.crypto_engine",
        "nyxora.core.vault_store",
        "nyxora.core.session_core",
        "nyxora.core.intel_engine",
        "nyxora.core.memory_guard",
        "nyxora.core.recovery_core",
        "nyxora.core.update_engine",
        "nyxora.tui.app",
        "nyxora.tui.screens.vault_browser",
        "nyxora.tui.screens.search_overlay",
        "nyxora.tui.screens.audit_screen",
        "nyxora.sdk",
        "nacl",
        "nacl.bindings",
        "argon2",
        "cryptography",
        "textual",
        "pyotp",
        "keyring",
        "keyring.backends.Windows",
        "pyperclip",
        "questionary",
        "orjson",
        "packaging",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="nyx",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(Path(SPECPATH) / "assets" / "nyxora_icon.ico"),
    version_file=None,
)
