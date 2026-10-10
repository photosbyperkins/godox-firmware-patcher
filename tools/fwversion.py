#!/usr/bin/env python3
"""
Shared versioning helpers for the custom firmware patchers.

Version scheme
--------------
    <Godox version>.<tier code>        e.g.  1.08.02

* The first two parts are the official Godox firmware the build is based on,
  shown exactly as Godox writes it (major.two-digit minor).
* The third part is the tier code (two digits). Godox only ever uses two
  parts, so a three-part version on screen always means a custom build.
* A tier keeps its code on every model and every Godox base version.

Patch revisions of the same tier and base (bug fixes in a patcher) do not
change the on-screen version. They are tracked by SHA-256 and the build
changelog in the top-level README.
"""
import hashlib

# key: (code, display name, file slug)
TIERS = {
    "S":  (1, "Studio",     "studio"),
    "R":  (2, "Recovery",   "recovery"),
    "X":  (3, "Super",      "super"),
    "R+": (4, "Recovery+",  "recovery_plus"),
    "X+": (5, "Super+",     "super_plus"),
}


def godox_version(major, minor):
    """(1, 8) -> '1.08'"""
    return f"{major}.{minor:02d}"


def build_version(major, minor, tier):
    """(1, 8, 'R') -> '1.08.02'"""
    return f"{godox_version(major, minor)}.{TIERS[tier][0]:02d}"


def tier_label(major, minor, tier):
    """(1, 8, 'R') -> 'Tier R: Recovery (1.08.02)'"""
    return f"Tier {tier}: {TIERS[tier][1]} ({build_version(major, minor, tier)})"


def output_name(prefix, v, major, minor, tier):
    """('AD600PROII', 'v', 1, 8, 'R') -> 'AD600PROII_v1.08.02_recovery.bin'"""
    return f"{prefix}_{v}{build_version(major, minor, tier)}_{TIERS[tier][2]}.bin"


def replace_cstring(data, offset, old, new):
    """Replace the NUL-terminated string `old` at file `offset` with `new`.

    The space available is the string's 4-byte-aligned slot (strings
    referenced by ADR are word-aligned, so the next item starts on the next
    word boundary). The slot's padding must be zero in the base image, the
    new string must fit with its terminator, and the rest of the slot is
    zero-filled.
    """
    old = old.encode("utf-8") if isinstance(old, str) else old
    new = new.encode("utf-8") if isinstance(new, str) else new
    if offset % 4:
        raise ValueError(f"String at 0x{offset:X} is not word-aligned")
    slot = (len(old) + 1 + 3) & ~3
    if bytes(data[offset:offset + len(old) + 1]) != old + b"\0":
        raise ValueError(f"Unexpected string at 0x{offset:X}: "
                         f"{bytes(data[offset:offset + len(old) + 1])!r}")
    if any(data[offset + len(old):offset + slot]):
        raise ValueError(f"Slot padding at 0x{offset:X} is not zero")
    if b"%" in new:
        raise ValueError("Replacement must not contain '%' (used as printf format)")
    if len(new) + 1 > slot:
        raise ValueError(f"{new!r} does not fit the {slot}-byte slot at 0x{offset:X}")
    data[offset:offset + slot] = new + b"\0" * (slot - len(new))


def fixed_version_format(data, offset, old_format, version):
    """Turn a printf version format like 'Version: V%d.%d%d' into fixed text
    'Version: V1.08.02'. The caller's integer arguments are then ignored, so
    the digit immediates in code stay stock."""
    old = old_format.encode("utf-8") if isinstance(old_format, str) else old_format
    if b"V%d.%d%d" not in old:
        raise ValueError(f"{old!r} is not a V%d.%d%d version format")
    replace_cstring(data, offset, old, old.replace(b"V%d.%d%d", b"V" + version.encode("ascii")))


def sha256(data):
    return hashlib.sha256(data).hexdigest()
