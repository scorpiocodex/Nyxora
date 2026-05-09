"""Build script for Nyxora Windows standalone executable."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"
BUILD = ROOT / "build"
ICON_PNG = ASSETS / "nyxora_icon.png"
ICON_ICO = ASSETS / "nyxora_icon.ico"
SPEC_FILE = ROOT / "nyxora_windows.spec"


def convert_icon() -> None:
    """Convert PNG to multi-resolution .ico using Pillow."""
    print("Converting icon PNG → ICO…")
    try:
        from PIL import Image
        img = Image.open(ICON_PNG).convert("RGBA")
        sizes = [(16, 16), (32, 32), (48, 48), (64, 64),
                 (128, 128), (256, 256)]
        resized = [img.resize(s, Image.LANCZOS) for s in sizes]
        resized[0].save(
            ICON_ICO,
            format="ICO",
            sizes=sizes,
            append_images=resized[1:],
        )
        print(f"  Icon saved: {ICON_ICO}")
    except ImportError:
        print("  Pillow not found — install with: pip install Pillow")
        sys.exit(1)
    except Exception as e:
        print(f"  Icon conversion failed: {e}")
        sys.exit(1)


def run_pyinstaller() -> None:
    """Run PyInstaller with the spec file."""
    print("Running PyInstaller…")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller",
         str(SPEC_FILE), "--clean", "--noconfirm"],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("PyInstaller failed.")
        sys.exit(result.returncode)


def verify_output() -> None:
    """Check the .exe exists and print its size."""
    exe = DIST / "nyx" / "nyx.exe"
    if not exe.exists():
        # One-file mode
        exe = DIST / "nyx.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / (1024 * 1024)
        print(f"\nBuild complete: {exe}")
        print(f"Size: {size_mb:.1f} MB")
    else:
        print("WARNING: nyx.exe not found in dist/")


if __name__ == "__main__":
    convert_icon()
    run_pyinstaller()
    verify_output()
