#!/usr/bin/env python3
"""
Godox AD600Pro II - Custom Firmware Multi-Tier Patcher
======================================================
Builds custom firmwares conforming to the Godox Custom Firmware
Classification System (TIERED_RATINGS.md).

Version scheme: <Godox version>.<tier code>, e.g. 1.08.02 (see tools/fwversion.py).

Profiles (base v1.08):
----------------------
- Tier S (Studio - 1.08.01):
  Continuous Level 2 Fan (high speed via PC14+PA4+PA7). Single-burst & repeated-burst protection: Stock.
- Tier R (Recovery - 1.08.02):
  Continuous Level 2 Fan + 2x Inter-burst Drain (80 pts).
  Single-burst protection: Stock. Repeated-burst protection: Reduced (fan-assisted).
- Tier X (Super - 1.08.03):
  Continuous Level 2 Fan + 2x Inter-burst Drain + Lowered table at 0x080398F0.
  Single-burst protection: Reduced. Repeated-burst protection: Reduced.
- Tier R+ (Recovery+ - 1.08.04):
  Tier R + 2x pre-latch drain on the secondary burst accumulator.
- Tier X+ (Super+ - 1.08.05):
  Tier R+ + lowered table + secondary burst throttle bypassed.
"""

import sys
import os
import hashlib
import struct

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import fwversion  # noqa: E402

EXPECTED_SHA256 = "33e327457bef0023af5254153a990a572c6a3afeb792fdb84e5bf137613bf910"
EXPECTED_SIZE = 407384
GODOX_VERSION = (1, 8)
OUT_PREFIX = "AD600PROII"

BASE_ADDR = 0x0800C000

# Offsets
FAN_BRANCH_OFFSET          = 0xB4BC     # 0x080174BC: beq 0x080174FA -> b 0x080174FA
DECAY_CMP_OFFSET           = 0x76CC     # 0x080136CC: cmp r1, #40 -> cmp r1, #80
DECAY_SUB_OFFSET           = 0x76D0     # 0x080136D0: subs r1, #40 -> subs r1, #80
SEC_DECAY_CMP_OFFSET       = 0x7744     # 0x08013744: cmp r0, #40 -> cmp r0, #80
SEC_DECAY_SUB_OFFSET       = 0x7748     # 0x08013748: subs r0, #40 -> subs r0, #80
BURST_THROTTLE_BRANCH_OFF  = 0x761C     # 0x0801361C: blo 0x08013632 -> b 0x08013632
HSS_TABLE_OFFSET           = 0x2D8F0    # 0x080398F0: 28 halfwords
# Version is stored as literal text "v1.08" in two 8-byte slots (ADR at 0x0801B666/0x0801B68C
# and 0x0801E25C/0x0801E49C). "1.08.02" is 7 chars + NUL, so the leading "v" is dropped to fit.
VER_STRINGS = [0xF738, 0x123FC]         # 0x0801B738 (device info popup), 0x0801E3FC (settings menu row 15)

ORIGINAL_HSS_TABLE = [
    25, 25, 25, 25, 25, 25,
    27, 27, 27,
    30, 30, 30, 30,
    35, 35,
    45, 45, 45,
    55, 55, 55,
    70, 70, 70,
    90, 90, 90,
    100
]

SUPER_HSS_TABLE = [
    20, 20, 20, 20, 20, 20,
    20, 20, 20,
    25, 25, 25, 25,
    25, 25,
    32, 32, 32,
    40, 40, 40,
    50, 50, 50,
    64, 64, 64,
    80
]

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
    if data[FAN_BRANCH_OFFSET] != 0x1D or data[FAN_BRANCH_OFFSET + 1] != 0xD0:
        raise ValueError(f"Unexpected bytes at fan branch offset 0x{FAN_BRANCH_OFFSET:X}")
    data[FAN_BRANCH_OFFSET + 1] = 0xE0

def apply_decay(data):
    if data[DECAY_CMP_OFFSET] != 0x28 or data[DECAY_CMP_OFFSET + 1] != 0x29:
        raise ValueError(f"Unexpected bytes at decay cmp offset 0x{DECAY_CMP_OFFSET:X}")
    if data[DECAY_SUB_OFFSET] != 0x28 or data[DECAY_SUB_OFFSET + 1] != 0x39:
        raise ValueError(f"Unexpected bytes at decay sub offset 0x{DECAY_SUB_OFFSET:X}")
    data[DECAY_CMP_OFFSET] = 0x50
    data[DECAY_SUB_OFFSET] = 0x50

def apply_secondary_decay(data):
    if data[SEC_DECAY_CMP_OFFSET] != 0x28 or data[SEC_DECAY_CMP_OFFSET + 1] != 0x28:
        raise ValueError(f"Unexpected bytes at secondary decay cmp offset 0x{SEC_DECAY_CMP_OFFSET:X}")
    if data[SEC_DECAY_SUB_OFFSET] != 0x28 or data[SEC_DECAY_SUB_OFFSET + 1] != 0x38:
        raise ValueError(f"Unexpected bytes at secondary decay sub offset 0x{SEC_DECAY_SUB_OFFSET:X}")
    data[SEC_DECAY_CMP_OFFSET] = 0x50
    data[SEC_DECAY_SUB_OFFSET] = 0x50

def apply_burst_throttle_bypass(data):
    # 0x0801361C: blo #0x8013632 (0x09 0xD3) -> b #0x8013632 (0x09 0xE0)
    if data[BURST_THROTTLE_BRANCH_OFF] != 0x09 or data[BURST_THROTTLE_BRANCH_OFF + 1] != 0xD3:
        raise ValueError(f"Unexpected bytes at burst throttle branch offset 0x{BURST_THROTTLE_BRANCH_OFF:X}")
    data[BURST_THROTTLE_BRANCH_OFF + 1] = 0xE0

def apply_hss(data):
    current = [data[HSS_TABLE_OFFSET + i] | (data[HSS_TABLE_OFFSET + i + 1] << 8) for i in range(0, 56, 2)]
    if current != ORIGINAL_HSS_TABLE:
        raise ValueError(f"HSS table at 0x{HSS_TABLE_OFFSET:X} does not match original template")
    for i, val in enumerate(SUPER_HSS_TABLE):
        struct.pack_into("<H", data, HSS_TABLE_OFFSET + i * 2, val)

def apply_version(data, tier):
    old = "v" + fwversion.godox_version(*GODOX_VERSION)       # "v1.08"
    new = fwversion.build_version(*GODOX_VERSION, tier)       # "1.08.02"
    for off in VER_STRINGS:
        fwversion.replace_cstring(data, off, old, new)

def build_profile(base_data, profile, output_dir):
    data = bytearray(base_data)
    # All profiles include continuous fan
    apply_fan(data)

    if profile == "R":
        apply_decay(data)
    elif profile == "X":
        apply_decay(data)
        apply_hss(data)
    elif profile == "R+":
        apply_decay(data)
        apply_secondary_decay(data)
    elif profile == "X+":
        apply_decay(data)
        apply_secondary_decay(data)
        apply_hss(data)
        apply_burst_throttle_bypass(data)
    apply_version(data, profile)

    output_path = os.path.join(output_dir, fwversion.output_name(OUT_PREFIX, "v", *GODOX_VERSION, profile))
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
        os.path.join(script_dir, "..", "_local_godox_assets", "AD600ProII", filename),
        os.path.join(script_dir, "..", filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    print(f"[-] Error: Official base firmware '{filename}' not found.")
    print("    To build custom firmwares, please obtain the official firmware:")
    print("    1. Download official v1.08 from https://www.godox.com/firmware-flash/")
    print(f"    2. Place '{filename}' in this directory, or run:")
    print(f"       python patch.py <path_to_{filename}>")
    sys.exit(1)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_file = find_base_file(script_dir, "AD600PROII_v1.08.bin")
    base_data = load_base(base_file)
    if not base_data:
        sys.exit(1)

    print(f"[*] Building Godox AD600Pro II Custom Firmwares from: {base_file}")
    for profile in ("S", "R", "X", "R+", "X+"):
        build_profile(base_data, profile, script_dir)
    print("[+] All profiles built successfully.")

if __name__ == "__main__":
    main()
