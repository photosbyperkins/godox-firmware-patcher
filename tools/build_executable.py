#!/usr/bin/env python3
"""
Build standalone Godox Firmware Patcher executables for Windows (.exe) and macOS (.app).

Usage:
    python tools/build_executable.py

Outputs:
    Windows: dist/GodoxFirmwarePatcher.exe
    macOS:   dist/GodoxFirmwarePatcher.app (configured to accept .bin drag-and-drop)
"""

import os
import plistlib
import shutil
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TOOLS_DIR, ".."))
APP_NAME = "GodoxFirmwarePatcher"

MODEL_DIRS = [
    "AD600ProII",
    "AD200ProII",
    "AD100ProII",
    "V100N",
    "it30ProN",
]


def patch_macos_info_plist(app_bundle_path: str) -> None:
    """Configure macOS Info.plist so Finder allows dragging .bin files onto GodoxFirmwarePatcher.app."""
    plist_path = os.path.join(app_bundle_path, "Contents", "Info.plist")
    if not os.path.isfile(plist_path):
        return

    with open(plist_path, "rb") as f:
        info = plistlib.load(f)

    info["CFBundleDisplayName"] = "Godox Firmware Patcher"
    info["CFBundleShortVersionString"] = "1.0.0"
    info["NSHighResolutionCapable"] = True
    info["CFBundleDocumentTypes"] = [
        {
            "CFBundleTypeName": "Godox Firmware Binary",
            "CFBundleTypeExtensions": ["bin", "BIN"],
            "CFBundleTypeRole": "Viewer",
            "LSHandlerRank": "Alternate",
        }
    ]

    with open(plist_path, "wb") as f:
        plistlib.dump(info, f)
    print(f"[+] Updated macOS Info.plist for .bin drag-and-drop: {plist_path}")


def main() -> int:
    entry_script = os.path.join(TOOLS_DIR, "patcher_gui.py")
    dist_dir = os.path.join(REPO_ROOT, "dist")
    build_dir = os.path.join(REPO_ROOT, "build")

    # PyInstaller path separator inside --add-data (';' on Windows, ':' on POSIX)
    sep = ";" if os.name == "nt" else ":"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--distpath",
        dist_dir,
        "--workpath",
        build_dir,
        "--specpath",
        build_dir,
        "--paths",
        TOOLS_DIR,
        "--hidden-import",
        "fwversion",
        "--hidden-import",
        "patcher_core",
    ]

    # Bundle each model's patch.py into <model_dir>/patch.py inside the executable
    for model_dir in MODEL_DIRS:
        patch_py = os.path.join(REPO_ROOT, model_dir, "patch.py")
        if not os.path.isfile(patch_py):
            print(f"[-] Missing model patcher: {patch_py}")
            return 1
        cmd.extend(["--add-data", f"{patch_py}{sep}{model_dir}"])

    # On Windows/Linux, build a single self-contained file (--onefile).
    # On macOS, --windowed --onedir produces a faster-launching .app bundle (or --onefile also creates .app).
    cmd.append("--onefile")

    # Bundle tkinterdnd2 if installed in the environment (optional, improves macOS inside-window drag & drop)
    try:
        import tkinterdnd2  # type: ignore  # noqa: F401
        cmd.extend(["--collect-all", "tkinterdnd2"])
        print("[*] Detected tkinterdnd2; bundling native DnD extensions.")
    except ImportError:
        pass

    cmd.append(entry_script)

    print("[*] Running PyInstaller:", " ".join(cmd))
    res = subprocess.run(cmd, cwd=REPO_ROOT)
    if res.returncode != 0:
        print("[-] PyInstaller build failed.")
        return res.returncode

    if sys.platform == "darwin":
        app_path = os.path.join(dist_dir, f"{APP_NAME}.app")
        if os.path.isdir(app_path):
            patch_macos_info_plist(app_path)
            print(f"[+] Built macOS application bundle: {app_path}")
    elif sys.platform == "win32":
        exe_path = os.path.join(dist_dir, f"{APP_NAME}.exe")
        if os.path.isfile(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"[+] Built Windows executable: {exe_path} ({size_mb:.2f} MB)")

    # Clean temporary build directory while keeping dist/
    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
