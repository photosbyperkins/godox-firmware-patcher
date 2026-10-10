#!/usr/bin/env python3
"""
Godox V100N - Custom Firmware Multi-Profile Patcher
===================================================
Builds custom firmwares conforming to the Godox Custom Firmware
Classification System (TIERED_RATINGS.md).

Version scheme: <Godox version>.<tier code>, e.g. 1.04.02 (see tools/fwversion.py).

Profiles (base V1.04):
----------------------
- Tier R (Recovery - 1.04.02):
  2x Accelerated Leaky Bucket Recovery (Both accumulators: 50 -> 100).
  Single-burst protection: Stock. Repeated-burst protection: Reduced.
- Tier X (Super - 1.04.03):
  2x Accelerated Drain + Lowered ALT (HSS) Table across all 11 rows (20% reduction).
  Expands continuous HSS burst headroom from 60 to 75 shots (+25%).
  Single-burst protection: Reduced. Repeated-burst protection: Reduced.
  Caution: Unit is fanless; monitor head temperature during intense burst loops.
"""

import sys
import os
import hashlib
import struct

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import fwversion  # noqa: E402

EXPECTED_SHA256 = "18e3581c601cc7c15e81bbbe951b8b336e133de822f99450f57f116ffab37ee6"
EXPECTED_SIZE = 1001676
GODOX_VERSION = (1, 4)
OUT_PREFIX = "V100N"

BASE_ADDR = 0x08008000

# Offsets
DECAY1_CMP_OFF = 0x7498   # 0x0800F498
DECAY1_SUB_OFF = 0x749C   # 0x0800F49C
DECAY2_CMP_OFF = 0x74AE   # 0x0800F4AE
DECAY2_SUB_OFF = 0x74B2   # 0x0800F4B2

# Version readouts: printf formats fed with hardcoded digits (1, 0, 4).
# They are rewritten to fixed text; the digit immediates stay stock.
VER_FORMATS = [
    (0x416E8, "Version: V%d.%d%d"),                       # 0x080496E8, device info (EN), ADR 0x080495DC
    (0x4172C, "\u56fa\u4ef6\u7248\u672c: V%d.%d%d"),      # 0x0804972C, device info (CN), ADR 0x080496B2
    (0x3CD34, "V%d.%d%d"),                                # 0x08044D34, settings menu,    ADR 0x08044BA4
]

ALT_TABLE_OFFSET = 0x49930  # 0x08051930: 11 rows x 22 halfwords (484 bytes)
NUM_ROWS = 11
ROW_COLS = 22

ORIGINAL_ROW = [60]*16 + [80]*3 + [100]*3
SUPER_ROW    = [48]*16 + [64]*3 + [80]*3

def load_base(input_path):
    if not os.path.exists(input_path):
        print(f"Error: Base firmware not found: {input_path}")
        return None
    with open(input_path, "rb") as f:
        data = bytearray(f.read())
    if len(data) != EXPECTED_SIZE:
        print(f"Warning: File size is {len(data)}, expected {EXPECTED_SIZE}")
    file_hash = hashlib.sha256(data).hexdigest()
    if file_hash != EXPECTED_SHA256:
        print(f"Warning: SHA256 mismatch (got {file_hash})")
    return data

def apply_version(data, tier):
    ver = fwversion.build_version(*GODOX_VERSION, tier)
    for off, fmt in VER_FORMATS:
        fwversion.fixed_version_format(data, off, fmt, ver)

def apply_decay(data):
    if data[DECAY1_CMP_OFF] != 0x32 or data[DECAY1_SUB_OFF] != 0x32:
        raise ValueError("Unexpected bytes at primary decay offsets")
    if data[DECAY2_CMP_OFF] != 0x32 or data[DECAY2_SUB_OFF] != 0x32:
        raise ValueError("Unexpected bytes at secondary decay offsets")
    data[DECAY1_CMP_OFF] = 100
    data[DECAY1_SUB_OFF] = 100
    data[DECAY2_CMP_OFF] = 100
    data[DECAY2_SUB_OFF] = 100

def apply_hss_table(data):
    for r in range(NUM_ROWS):
        row_off = ALT_TABLE_OFFSET + r * ROW_COLS * 2
        curr_row = list(struct.unpack_from('<22H', data, row_off))
        if curr_row != ORIGINAL_ROW:
            raise ValueError(f"ALT table row {r} does not match expected template")
        for c, val in enumerate(SUPER_ROW):
            struct.pack_into("<H", data, row_off + c * 2, val)

def build_profile(base_data, profile, output_dir):
    data = bytearray(base_data)
    apply_decay(data)

    if profile == "X":
        apply_hss_table(data)
    apply_version(data, profile)

    output_path = os.path.join(output_dir, fwversion.output_name(OUT_PREFIX, "V", *GODOX_VERSION, profile))
    with open(output_path, "wb") as f:
        f.write(data)
    out_hash = hashlib.sha256(data).hexdigest()
    print(f"[+] Built {fwversion.tier_label(*GODOX_VERSION, profile)}: {os.path.basename(output_path)} (SHA256: {out_hash})")
    return out_hash

def find_base_file(script_dir, filename):
    if len(sys.argv) > 1:
        if sys.argv[1] in ("-h", "--help"):
            print(f"Usage: python patch.py [path_to_{filename}]")
            print(f"Builds custom firmware profiles from official OEM {filename}.")
            sys.exit(0)
        candidate = sys.argv[1]
        if os.path.exists(candidate):
            return candidate
        print(f"[-] Error: Specified file not found: {candidate}")
        sys.exit(1)

    candidates = [
        os.path.join(script_dir, filename),
        os.path.join(script_dir, filename.lower()),
        os.path.join(script_dir, "..", "_local_godox_assets", "V100N", filename),
        os.path.join(script_dir, "..", filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    print(f"[-] Error: Official base firmware '{filename}' not found.")
    print("    To build custom firmwares, please obtain the official firmware:")
    print("    1. Download official V1.04 from https://www.godox.com/firmware-flash/")
    print(f"    2. Place '{filename}' in this directory, or run:")
    print(f"       python patch.py <path_to_{filename}>")
    sys.exit(1)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_file = find_base_file(script_dir, "V100N_V1.04.bin")
    base_data = load_base(base_file)
    if not base_data:
        sys.exit(1)

    print(f"[*] Building Godox V100N Custom Firmwares from: {base_file}")
    for profile in ("R", "X"):
        build_profile(base_data, profile, script_dir)
    print("[+] All profiles built successfully.")

if __name__ == "__main__":
    main()
