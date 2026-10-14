#!/usr/bin/env python3
"""
Godox AD200Pro II - Custom Firmware Multi-Profile Patcher
=========================================================
Builds custom firmwares conforming to the Godox Custom Firmware
Classification System (TIERED_RATINGS.md).

Version scheme: <Godox version>.<tier code>, e.g. 1.05.02 (see tools/fwversion.py).

Profiles (base V1.05):
----------------------
- Tier R (Recovery - 1.05.02):
  2x Accelerated Leaky Bucket Recovery (Bare bulb: 250, Speedlite: 200).
  Single-burst protection: Stock. Repeated-burst protection: Reduced.
- Tier X (Super - 1.05.03):
  2x Accelerated Drain + Lowered HSS Tables C & D (~20% reduction).
  Expands continuous HSS burst headroom (+24% to +26%: 33 -> 41 on Table C, 50 -> 63 on Table D).
  Single-burst protection: Reduced. Repeated-burst protection: Reduced.
"""

import sys
import os
import hashlib
import struct

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import fwversion  # noqa: E402

EXPECTED_SHA256 = "30783860ede87b4bd30678cf820a8f2f6e0d8bc505344d42de1d3561c69f400b"
EXPECTED_SIZE = 387248
GODOX_VERSION = (1, 5)
OUT_PREFIX = "AD200ProII"

BASE_ADDR = 0x0800C000

# Offsets
DECAY_BARE_CMP = 0x63CA   # 0x080123CA
DECAY_BARE_SUB = 0x63CE   # 0x080123CE
DECAY_SPD_CMP  = 0x63D4   # 0x080123D4
DECAY_SPD_SUB  = 0x63D8   # 0x080123D8

# Version readouts: printf formats fed with hardcoded digits (1, 0, 5).
# They are rewritten to fixed text; the digit immediates stay stock.
VER_FORMATS = [
    (0x2EDCC, "Version: V%d.%d%d"),           # 0x0803ADCC, device info (EN), ADR 0x0803ACD8
    (0x2EE14, "\u7248\u672c: V%d.%d%d"),      # 0x0803AE14, device info (CN), ADR 0x0803AD98
    (0x2C4F8, "V%d.%d%d"),                    # 0x080384F8, settings menu,    ADR 0x080383E8
]

TABLE_C_OFFSET = 0x354FE  # 0x080414FE: HSS Table C (25 halfwords)
TABLE_D_OFFSET = 0x35530  # 0x08041530: HSS Table D (25 halfwords)

ORIGINAL_TABLE_C = [32]*12 + [40]*3 + [60]*3 + [80]*3 + [100]*3 + [185]
SUPER_TABLE_C    = [25]*12 + [32]*3 + [48]*3 + [64]*3 + [80]*3  + [148]

ORIGINAL_TABLE_D = [24]*12 + [30]*3 + [44]*3 + [60]*3 + [75]*3 + [120]
SUPER_TABLE_D    = [19]*12 + [24]*3 + [35]*3 + [48]*3 + [60]*3 + [96]

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
    if data[DECAY_BARE_CMP] != 0x7D or data[DECAY_BARE_SUB] != 0x7D:
        raise ValueError("Unexpected bytes at bare bulb decay offsets")
    if data[DECAY_SPD_CMP] != 0x64 or data[DECAY_SPD_SUB] != 0x64:
        raise ValueError("Unexpected bytes at speedlite decay offsets")
    data[DECAY_BARE_CMP] = 250
    data[DECAY_BARE_SUB] = 250
    data[DECAY_SPD_CMP] = 200
    data[DECAY_SPD_SUB] = 200

def apply_hss_tables(data):
    curr_c = list(struct.unpack_from('<25H', data, TABLE_C_OFFSET))
    curr_d = list(struct.unpack_from('<25H', data, TABLE_D_OFFSET))
    if curr_c != ORIGINAL_TABLE_C:
        raise ValueError("Table C template mismatch")
    if curr_d != ORIGINAL_TABLE_D:
        raise ValueError("Table D template mismatch")
    for i, val in enumerate(SUPER_TABLE_C):
        struct.pack_into("<H", data, TABLE_C_OFFSET + i * 2, val)
    for i, val in enumerate(SUPER_TABLE_D):
        struct.pack_into("<H", data, TABLE_D_OFFSET + i * 2, val)

def build_profile(base_data, profile, output_dir):
    data = bytearray(base_data)
    apply_decay(data)

    if profile == "X":
        apply_hss_tables(data)
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
        os.path.join(script_dir, "..", "_local_godox_assets", "AD200ProII", filename),
        os.path.join(script_dir, "..", filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    print(f"[-] Error: Official base firmware '{filename}' not found.")
    print("    To build custom firmwares, please obtain the official firmware:")
    print("    1. Download official V1.05 from https://www.godox.com/firmware-flash/")
    print(f"    2. Place '{filename}' in this directory, or run:")
    print(f"       python patch.py <path_to_{filename}>")
    sys.exit(1)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_file = find_base_file(script_dir, "AD200ProII_V1.05.bin")
    base_data = load_base(base_file)
    if not base_data:
        sys.exit(1)

    print(f"[*] Building Godox AD200Pro II Custom Firmwares from: {base_file}")
    for profile in ("R", "X"):
        build_profile(base_data, profile, script_dir)
    print("[+] All profiles built successfully.")

if __name__ == "__main__":
    main()

