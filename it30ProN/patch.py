#!/usr/bin/env python3
"""
Godox iT30ProN - Custom Firmware Multi-Profile Patcher
======================================================
Builds custom firmwares conforming to the Godox Custom Firmware
Classification System (TIERED_RATINGS.md).

Target Model: Godox iT30Pro for Nikon (iT30ProN)
OEM Base: iT30ProN_V1.02.bin (688,172 bytes)

Version scheme: <Godox version>.<tier code>, e.g. 1.02.02 (see tools/fwversion.py).

Profiles (base V1.02):
----------------------
- Tier R (Recovery - 1.02.02):
  2x drain on both primary & secondary accumulators (80 -> 160 pts per 6.0 s).
  Single-burst protection: Stock. Repeated-burst protection: Reduced.

- Tier X (Super - 1.02.03):
  Tier R + multi-pulse (likely HSS) table lowered ~20% on all 11 rows (60/80/150 -> 48/64/120).
  Top-column multi-pulse burst: 40 -> 50 shots to primary cooldown, 14 -> 17 to secondary throttle.
  Single-burst protection: Reduced. Repeated-burst protection: Reduced.
  Caution: The iT30Pro is a small, fanless unit with low thermal mass.
"""

import sys
import os
import hashlib
import struct

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import fwversion  # noqa: E402

EXPECTED_SHA256 = "a6920833d267834e7ff41f537ce8b897bab47234013731ae79b4affcbf41847e"
EXPECTED_SIZE = 688172
GODOX_VERSION = (1, 2)
OUT_PREFIX = "iT30ProN"

BASE_ADDR = 0x0800C000

# Offsets (file offset = memory address - BASE_ADDR)
# fn_0801412c leaky-bucket decay routine
DECAY1_CMP_OFF = 0x080141CC - BASE_ADDR  # 0x81CC: cmp r0, #0x50
DECAY1_SUB_OFF = 0x080141D0 - BASE_ADDR  # 0x81D0: subs r0, #0x50
DECAY2_CMP_OFF = 0x080141E2 - BASE_ADDR  # 0x81E2: cmp r0, #0x50
DECAY2_SUB_OFF = 0x080141E6 - BASE_ADDR  # 0x81E6: subs r0, #0x50

# Version readouts: printf formats fed with hardcoded digits (1, 0, 2) by fn_0803B02A.
# They are rewritten to fixed text; the digit immediates stay stock.
VER_FORMATS = [
    (0x0804A1C4 - BASE_ADDR, "Version: V%d.%d%d"),                    # device info (EN), ADR 0x0804A09A
    (0x0804A214 - BASE_ADDR, "\u56fa\u4ef6\u7248\u672c: V%d.%d%d"),   # device info (CN), ADR 0x0804A17C
]

# Multi-pulse table at 0x0804FFAC: 11 rows x 22 halfwords (484 bytes)
HSS_TABLE_OFFSET = 0x0804FFAC - BASE_ADDR  # 0x43FAC
NUM_ROWS = 11
ROW_COLS = 22

ORIGINAL_HSS_ROW = [60]*16 + [80]*3 + [150]*3
SUPER_HSS_ROW    = [48]*16 + [64]*3 + [120]*3

# Integrity footer (unique to this model among the ones in this repo).
# Layout at file offset 0xA8000 (= 0x080B4000):
#   +0x00  16 bytes  MD5 over file[0x00000 : 0xA8000]
#   +0x10  18 bytes  original filename "iT30ProN_V1.02.bin" (not NUL-terminated)
#   +0x22   u16 LE   filename length (0x0012)
#   +0x24   8 bytes  magic AA 55 66 99 77 88 22 33
# The application contains no MD5 code, so the check is done by the G3 updater
# and/or the bootloader. Any patch inside [0, 0xA8000) must refresh the MD5.
FOOTER_OFF   = 0xA8000
FOOTER_MAGIC = bytes.fromhex("aa55669977882233")

def check_footer(data):
    if len(data) != FOOTER_OFF + 0x2C or data[-8:] != FOOTER_MAGIC:
        raise ValueError("Integrity footer not found where expected")
    name_len = struct.unpack_from("<H", data, FOOTER_OFF + 0x22)[0]
    if name_len != 0x12:
        raise ValueError(f"Unexpected footer filename length {name_len}")
    if hashlib.md5(data[:FOOTER_OFF]).digest() != bytes(data[FOOTER_OFF:FOOTER_OFF + 16]):
        raise ValueError("Footer MD5 does not match base image payload")

def apply_footer(data):
    # Filename field is deliberately left unchanged; whether the updater
    # compares it against anything is unknown (see README, open questions).
    data[FOOTER_OFF:FOOTER_OFF + 16] = hashlib.md5(data[:FOOTER_OFF]).digest()

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
    # Check original instructions: cmp r0, #0x50 (50 28) and subs r0, #0x50 (50 38)
    if data[DECAY1_CMP_OFF] != 0x50 or data[DECAY1_SUB_OFF] != 0x50:
        raise ValueError("Unexpected bytes at primary decay offsets")
    if data[DECAY2_CMP_OFF] != 0x50 or data[DECAY2_SUB_OFF] != 0x50:
        raise ValueError("Unexpected bytes at secondary decay offsets")

    # 2x drain: 80 -> 160 (0xA0)
    data[DECAY1_CMP_OFF] = 0xA0
    data[DECAY1_SUB_OFF] = 0xA0
    data[DECAY2_CMP_OFF] = 0xA0
    data[DECAY2_SUB_OFF] = 0xA0

def apply_hss_table(data):
    for r in range(NUM_ROWS):
        row_off = HSS_TABLE_OFFSET + r * ROW_COLS * 2
        curr_row = list(struct.unpack_from('<22H', data, row_off))
        if curr_row != ORIGINAL_HSS_ROW:
            raise ValueError(f"HSS table row {r} does not match expected template: {curr_row}")
        for c, val in enumerate(SUPER_HSS_ROW):
            struct.pack_into("<H", data, row_off + c * 2, val)

def build_profile(base_data, profile, output_dir):
    data = bytearray(base_data)
    check_footer(data)
    apply_decay(data)

    if profile == "X":
        apply_hss_table(data)
    apply_version(data, profile)

    apply_footer(data)
    check_footer(data)

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
        os.path.join(script_dir, "..", "_local_godox_assets", "it30ProN", filename),
        os.path.join(script_dir, "..", filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    print(f"[-] Error: Official base firmware '{filename}' not found.")
    print("    To build custom firmwares, please obtain the official firmware:")
    print("    1. Download official V1.02 from https://www.godox.com/firmware-flash/")
    print(f"    2. Place '{filename}' in this directory, or run:")
    print(f"       python patch.py <path_to_{filename}>")
    sys.exit(1)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_file = find_base_file(script_dir, "iT30ProN_V1.02.bin")
    base_data = load_base(base_file)
    if not base_data:
        sys.exit(1)

    print(f"[*] Building Godox iT30ProN Custom Firmwares from: {base_file}")
    for profile in ("R", "X"):
        build_profile(base_data, profile, script_dir)
    print("[+] All profiles built successfully.")

if __name__ == "__main__":
    main()
