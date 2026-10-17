# Tools

| File | Purpose | Dependencies |
|---|---|---|
| [`patcher_gui.py`](patcher_gui.py) | Drag-and-drop desktop app and headless CLI | Python 3 + tkinter; optional `tkinterdnd2` |
| [`patcher_core.py`](patcher_core.py) | Model detection by SHA-256, tier metadata, verified builds (backend of the app) | — |
| [`fwversion.py`](fwversion.py) | Version scheme and bounds-checked string patching, shared by every `patch.py` | — |
| [`build_executable.py`](build_executable.py) | Builds `dist/GodoxFirmwarePatcher.exe` (Windows) or `.app` (macOS) | `pyinstaller` |
| [`disasm.py`](disasm.py) | Thumb-2 disassembler with load-address detection | `capstone >= 5` |
| [`compare_features.py`](compare_features.py) | Shared 256-byte blocks and unique strings between two images | — |

Commands below run from the repository root.

## Patching

```powershell
python tools\patcher_gui.py                                              # open the app
python tools\patcher_gui.py models\AD600ProII\AD600PROII_v1.08.bin       # open with a file loaded
python tools\patcher_gui.py models\AD600ProII\AD600PROII_v1.08.bin --tier R          # headless, one tier
python tools\patcher_gui.py models\AD600ProII\AD600PROII_v1.08.bin --tier all -o out # headless, all tiers
python models\AD600ProII\patch.py [path\to\AD600PROII_v1.08.bin]         # per-model script, all tiers
```

- `patcher_core.identify_firmware()` classifies a file as a supported OEM base, an already-patched build, a known reference-only image (AD600BM II v1.02), a size match with the wrong hash, or unknown.
- `patcher_core.build_selected_tiers()` requires the exact OEM size and SHA-256, loads `models/<model_id>/patch.py`, builds each tier and raises if an output hash differs from `MODEL_SPECS`.
- Each `models/<Model>/patch.py` checks every original byte before writing and raises on mismatch. Run standalone it only *warns* on a base-hash mismatch, then writes all tiers next to itself and prints their hashes.

## Building the app

```powershell
pip install pyinstaller tkinterdnd2
python tools\build_executable.py
```

PyInstaller bundles each `models/<Model>/patch.py` at the same relative path inside the executable, where `patcher_core` loads it. On macOS the script also registers `.bin` as a document type so files can be dropped on the `.app` icon. [`.github/workflows/build_patcher.yml`](../.github/workflows/build_patcher.yml) runs the same build on Windows and macOS and attaches both to a GitHub Release for every `v*` tag.

## `fwversion.py`

| Function | Example |
|---|---|
| `TIERS` | `"R": (2, "Recovery", "recovery")` — code, display name, file slug |
| `build_version(1, 8, "R")` | `"1.08.02"` |
| `output_name("AD600PROII", "v", 1, 8, "R")` | `"AD600PROII_v1.08.02_recovery.bin"` |
| `tier_label(1, 8, "R")` | `"Tier R: Recovery (1.08.02)"` |
| `replace_cstring(data, off, old, new)` | Overwrites a NUL-terminated string in its 4-byte-aligned slot. Checks the original bytes and zero padding; raises if `new` doesn't fit or contains `%`. |
| `fixed_version_format(data, off, "Version: V%d.%d%d", "1.05.02")` | Rewrites a printf version format as fixed text, so the code's digit immediates stay stock. |

## Disassembly (`disasm.py`)

```powershell
pip install capstone
python tools\disasm.py                     # all models -> models\<Model>\disasm\
python tools\disasm.py V100N               # one model
python tools\disasm.py --file X.bin --detect                       # rank candidate load addresses
python tools\disasm.py --file X.bin --base 0x0800C000 --out DIR    # arbitrary image
```

| Output | Contents |
|---|---|
| `*.asm` | Recursive-descent listing seeded from the vector table: `fn_`/`loc_` labels, literal-pool values, string previews, ADR targets, caller lists. Literal pools, jump tables and strings are emitted as data. |
| `*.functions.csv` | Address, file offset, name and caller count of every function found |
| `*.strings.txt` | Strings with address, file offset and the instructions that reference them (literal or ADR) |

**Load address.** The images sit behind a bootloader and are not loaded at `0x08000000`; a wrong base breaks every absolute address and cross-reference. `--detect` scores each candidate base by how many embedded pointers land on `push {…, lr}` prologues or string starts; the right base wins by a wide margin. Known bases are in [architecture.md §1](../docs/architecture.md#1-platform).

**Limits.** Code reached only through indirect calls is found by a heuristic prologue scan, so a few prologue-less leaf functions stay undecoded. Code coverage ranges from ~20 % (V100N, large GUI asset area) to ~50 % (AD600Pro II); the rest is mostly font and bitmap data.

## Ghidra / IDA

Import the `.bin` as a raw binary:

- Language `ARM:LE:32:Cortex` (Ghidra) or ARM little-endian with Thumb as default (IDA).
- Base address from [architecture.md §1](../docs/architecture.md#1-platform).
- Add RAM at `0x20000000` (and `0x10000000` for the AD200Pro II, whose stack is in CCM RAM) and a peripheral block at `0x40000000`.
- In Ghidra, set `TMode` = 1 across the image and disassemble from the reset vector at `base + 4`.
- An SVD loader (e.g. `SVD-Loader-Ghidra` with `STM32F4xx.svd`) names the peripheral registers.

## Porting to a new Godox release

1. Confirm the load address with `disasm.py --file new.bin --detect` and regenerate the listing.
2. Re-locate every patch site from the model README's byte-diff table and check the original bytes and table templates.
3. In `models/<Model>/patch.py`, update `GODOX_VERSION`, `EXPECTED_SHA256`, `EXPECTED_SIZE`, the offsets and the original/patched templates.
4. Add the new base and output hashes to `MODEL_SPECS` in `patcher_core.py`.
5. Update the model README and add a row to [CHANGELOG.md](../CHANGELOG.md).
