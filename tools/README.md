# Disassembly tooling

## Load addresses (must be right)

Each `.bin` is an **application image that sits behind a bootloader**. It is not loaded at `0x08000000`.

| Model | Image | Load address | Initial SP | Reset handler |
|---|---|---|---|---|
| AD600ProII | `AD600PROII_v1.08.bin` | `0x0800C000` | `0x20018570` | `0x0800C1A1` |
| AD200ProII | `AD200ProII_V1.05.bin` | `0x0800C000` | `0x1000F000` | `0x0800C269` |
| AD100ProII | `AD100ProII_RF433V1_07.bin` | `0x0800C000` | `0x2001BC00` | `0x0800C249` |
| V100N | `V100N_V1.04.bin` | `0x08008000` | `0x200AD678` | `0x0800829D` |
| iT30ProN | `iT30ProN_V1.02.bin` | `0x0800C000` | `0x2001F3F0` | `0x0800C279` |

All five are plaintext Cortex-M images: no encryption and no header. The AD600ProII, AD200ProII, AD100ProII and V100N images have no obvious trailing checksum. The iT30ProN image ends in a 44-byte MD5 footer at `0xA8000` (see [`it30ProN/README.md`](../it30ProN/README.md)). The peripheral addresses used (GPIO at `0x40020000`, `0x40020800`, ...) match the STM32F4 memory map or a clone of it.

For a new firmware version, check the load address before trusting any analysis:

```powershell
python tools\disasm.py --file path\to\new.bin --detect
```

The detector counts pointers in the image that land on function prologues or string starts for each candidate base. The correct base wins by a wide margin.

## `tools/fwversion.py`

The patchers share this module for the version scheme (`<Godox version>.<tier code>`, see the [root README §1](../README.md#1-firmware-profiles--version-scheme)):

- `TIERS` maps each tier to its code (S 01, R 02, X 03, R+ 04, X+ 05), display name and file slug.
- `build_version`, `output_name` and `tier_label` build the on-screen version, output filename and labels.
- `replace_cstring` overwrites a NUL-terminated string in place. It checks the original bytes and the 4-byte-aligned slot size, and raises if the new text doesn't fit.
- `fixed_version_format` turns a `V%d.%d%d` format string into fixed text such as `V1.05.02`.

When Godox ships a new base firmware, update `GODOX_VERSION`, the base SHA-256 and every patch offset in that model's `patch.py`. Re-verify each offset against the new image, then add a row to the [build changelog](../README.md#8-build-changelog).

## `tools/patcher_gui.py` & `tools/build_executable.py`

Cross-platform drag-and-drop desktop patcher (**Windows `.exe`** and **macOS `.app`**) backed by [`tools/patcher_core.py`](patcher_core.py):

```powershell
# Run GUI directly from Python:
python tools\patcher_gui.py

# Pre-load a firmware file (same as dropping a .bin onto the .exe / .app icon):
python tools\patcher_gui.py AD600ProII\AD600PROII_v1.08.bin

# Run headlessly from CLI (single tier or all tiers):
python tools\patcher_gui.py AD600ProII\AD600PROII_v1.08.bin --tier R
python tools\patcher_gui.py AD600ProII\AD600PROII_v1.08.bin --tier all

# Build standalone executable (dist/GodoxFirmwarePatcher.exe on Windows, .app on macOS):
python tools\build_executable.py
```

## `tools/disasm.py`

```powershell
pip install capstone          # once
python tools\disasm.py        # all models -> <Model>\disasm\
python tools\disasm.py V100N  # a single model
python tools\disasm.py --file X.bin --base 0x0800C000 --out somewhere
```

Outputs per model (in `<Model>/disasm/`):

| File | Contents |
|---|---|
| `*.asm` | Recursive-descent listing seeded from the vector table, with `fn_`/`loc_` labels, literal-pool values, string previews, ADR targets and caller lists. Literal pools, jump tables and strings are written as data. |
| `*.functions.csv` | Every function found, with its address, file offset and number of callers |
| `*.strings.txt` | Strings with their addresses, file offsets and the instructions that reference them through a literal or ADR |

Limits: code reached only through indirect calls (function-pointer tables, `blx rN`) is picked up by a heuristic scan for `push {..., lr}` prologues, so a few leaf functions with no prologue may stay undecoded. The rest of each image that isn't code is mostly font and bitmap data. Code coverage ranges from about 20% (V100N, which has a large GUI asset area) to ~50% (AD600Pro II).

## Ghidra / IDA

Import as a **raw binary**:

- Language: `ARM:LE:32:Cortex` (Ghidra) or ARM little-endian with Thumb as the default (IDA)
- Base address: taken from the table above
- Add RAM blocks at `0x20000000` (and at `0x10000000` for the AD200ProII, whose stack lives there), plus a peripheral block at `0x40000000`
- In Ghidra, set the `TMode` register to 1 across the image, then disassemble from the reset vector at `base + 4`

An SVD loader (for example the `SVD-Loader-Ghidra` script with `STM32F4xx.svd`) will name the peripheral registers.
