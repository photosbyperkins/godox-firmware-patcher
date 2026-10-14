#!/usr/bin/env python3
"""
Godox AD100Pro II - Custom Firmware Multi-Tier Patcher
======================================================
Builds custom firmwares conforming to the Godox Custom Firmware
Classification System (TIERED_RATINGS.md).

Version scheme: <Godox version>.<tier code>, e.g. 1.07.02 (see tools/fwversion.py).

Profiles (base V1.07):
----------------------
- Tier S (Studio - 1.07.01):
  Continuous Active Cooling Fan (GPIOC Pin 4 forced on by fn_08014370, except when
  the 0x2000007A low-battery cutoff flag is set).
  Single-burst & repeated-burst protection: Stock.
- Tier R (Recovery - 1.07.02):
  Continuous Active Cooling Fan + 2x Inter-burst Drain on both accumulators
  (Primary: 25 -> 50 pts, Pre-latch Secondary: 30 -> 60 pts per 5.0 s).
  Single-burst protection: Stock. Repeated-burst protection: Reduced (fan-assisted).
- Tier X (Super - 1.07.03):
  Continuous Active Cooling Fan + 2x Inter-burst Drain + Lowered Table Set 2
  (verified HSS table at 0x08032F48; flag [0x20000028,#0xD] set after 100/105-pulse
  HSS trains in fn_08012334 and fn_08017A8C) (~20% reduction across all 11 rows, max 100 -> 80 pts).
  Single-burst protection: Reduced (+25% burst headroom, 60 -> 75 shots at 1/1).
  Repeated-burst protection: Reduced (fan-assisted).
"""

import sys
import os
import hashlib
import struct

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import fwversion  # noqa: E402

EXPECTED_SHA256 = "5dd2dd434e0ca531a57fd5ad397a9de1cf4e8acf2374aa6bfc5d7fed17c135dc"
EXPECTED_SIZE = 357004
GODOX_VERSION = (1, 7)
OUT_PREFIX = "AD100ProII"

BASE_ADDR = 0x0800C000

# Offsets (file offset = memory address - BASE_ADDR)
# Fan control routine (fn_08014370):
# 0x080143A2: ldrb r1, [r5] (0x29 0x78) -> b #0x80143ee (0x24 0xE0)
FAN_BRANCH_OFFSET = 0x080143A2 - BASE_ADDR   # 0x83A2

# Drain routine (fn_080111f4):
# Primary accumulator (0x20000048 / [r5, #0x20]): 25 -> 50 pts
DECAY_PRI_CMP_OFF = 0x08011224 - BASE_ADDR   # 0x5224: cmp r0, #0x19
DECAY_PRI_SUB_OFF = 0x08011228 - BASE_ADDR   # 0x5228: subs r0, #0x19
# Secondary accumulator ([r5, #0x28]): 30 -> 60 pts
DECAY_SEC_CMP_OFF = 0x08011278 - BASE_ADDR   # 0x5278: cmp r0, #0x1e
DECAY_SEC_SUB_OFF = 0x0801127C - BASE_ADDR   # 0x527C: subs r0, #0x1e

# HSS / Multi-pulse Table Set 2 (11 modes x 25 halfwords = 550 bytes at 0x08032F48)
HSS_TABLE_OFFSET = 0x08032F48 - BASE_ADDR    # 0x26F48
NUM_MODES = 11
ENTRIES_PER_MODE = 25

ORIGINAL_HSS_ROW_STD = [22]*6 + [36]*3 + [46]*3 + [60]*4 + [70]*3 + [86]*3 + [100]*3
SUPER_HSS_ROW_STD    = [18]*6 + [29]*3 + [37]*3 + [48]*4 + [56]*3 + [69]*3 + [80]*3

ORIGINAL_HSS_ROW_M10 = [22]*6 + [36]*3 + [46]*3 + [60]*4 + [70, 60, 70] + [86]*3 + [100]*3
SUPER_HSS_ROW_M10    = [18]*6 + [29]*3 + [37]*3 + [48]*4 + [56, 48, 56] + [69]*3 + [80]*3

# Version strings: two 8-byte slots ("V1.07\0\0\0") referenced via ADR
# 0x0802F9FC (file offset 0x239FC, settings menu, ADR 0x0802F91A)
# 0x08030484 (file offset 0x24484, device info,   ADR 0x080302D6)
VER_STRINGS = [0x239FC, 0x24484]


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


def apply_fan(data):
    if data[FAN_BRANCH_OFFSET] != 0x29 or data[FAN_BRANCH_OFFSET + 1] != 0x78:
        raise ValueError(f"Unexpected bytes at fan branch offset 0x{FAN_BRANCH_OFFSET:X}")
    data[FAN_BRANCH_OFFSET] = 0x24
    data[FAN_BRANCH_OFFSET + 1] = 0xE0


def apply_decay(data):
    # Primary accumulator decay: 25 -> 50 pts
    if data[DECAY_PRI_CMP_OFF] != 0x19 or data[DECAY_PRI_SUB_OFF] != 0x19:
        raise ValueError(f"Unexpected bytes at primary decay offsets (0x{DECAY_PRI_CMP_OFF:X})")
    data[DECAY_PRI_CMP_OFF] = 50
    data[DECAY_PRI_SUB_OFF] = 50

    # Secondary accumulator decay: 30 -> 60 pts
    if data[DECAY_SEC_CMP_OFF] != 0x1E or data[DECAY_SEC_SUB_OFF] != 0x1E:
        raise ValueError(f"Unexpected bytes at secondary decay offsets (0x{DECAY_SEC_CMP_OFF:X})")
    data[DECAY_SEC_CMP_OFF] = 60
    data[DECAY_SEC_SUB_OFF] = 60


def apply_hss(data):
    for mode in range(NUM_MODES):
        off = HSS_TABLE_OFFSET + mode * (ENTRIES_PER_MODE * 2)
        row = list(struct.unpack_from(f"<{ENTRIES_PER_MODE}H", data, off))
        expected_orig = ORIGINAL_HSS_ROW_M10 if mode == 10 else ORIGINAL_HSS_ROW_STD
        super_target = SUPER_HSS_ROW_M10 if mode == 10 else SUPER_HSS_ROW_STD

        if row != expected_orig:
            raise ValueError(f"HSS table mode {mode} at 0x{off:X} does not match expected template")

        for i, val in enumerate(super_target):
            struct.pack_into("<H", data, off + i * 2, val)


def apply_version(data, tier):
    old = "V" + fwversion.godox_version(*GODOX_VERSION)        # "V1.07"
    new = fwversion.build_version(*GODOX_VERSION, tier)        # "1.07.02"
    for off in VER_STRINGS:
        fwversion.replace_cstring(data, off, old, new)


def build_profile(base_data, profile, output_dir):
    data = bytearray(base_data)
    # All custom profiles enable continuous fan operation
    apply_fan(data)

    if profile in ("R", "X"):
        apply_decay(data)
    if profile == "X":
        apply_hss(data)

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
        os.path.join(script_dir, "AD100ProII_RF433V1_07.bin"),
        os.path.join(script_dir, "..", "_local_godox_assets", "AD100ProII", filename),
        os.path.join(script_dir, "..", "_local_godox_assets", "AD100ProII", "AD100ProII_RF433V1_07.bin"),
        os.path.join(script_dir, "..", filename),
        os.path.join(script_dir, "..", "AD100ProII_RF433V1_07.bin")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    print(f"[-] Error: Official base firmware '{filename}' not found.")
    print("    To build custom firmwares, please obtain the official firmware:")
    print("    1. Place 'AD100ProII_RF433V1_07.bin' in this directory, or run:")
    print(f"       python patch.py <path_to_{filename}>")
    sys.exit(1)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_file = find_base_file(script_dir, "AD100ProII_RF433V1_07.bin")
    base_data = load_base(base_file)
    if not base_data:
        sys.exit(1)

    print(f"[*] Building Godox AD100Pro II Custom Firmwares from: {base_file}")
    for profile in ("S", "R", "X"):
        build_profile(base_data, profile, script_dir)
    print("[+] All profiles built successfully.")


if __name__ == "__main__":
    main()
