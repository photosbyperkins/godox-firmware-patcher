# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Reverse-engineering notes plus deterministic byte patchers that turn official Godox flash firmware images (AD600Pro II, AD200Pro II, AD100Pro II, V100N, iT30ProN) into custom builds. Patches only touch fan behaviour, the heat counter ("shot limit") and the on-screen version string; everything else stays byte-for-byte stock. Pure Python 3, standard library only, apart from the optional tools below. There is no test suite and no linter config. **Correctness is checked by SHA-256 of every output image.**

OEM `.bin` images are proprietary and git-ignored (`*.bin`, `*.exe`, `*.pdf`, `_local_godox_assets/`, `dist/`). Never commit them. Locally they live next to each `models/<Model>/patch.py` or under `_local_godox_assets/<Model>/` in the main checkout (not in worktrees).

## Commands

Run from the repository root.

```bash
python models/AD600ProII/patch.py [path/to/AD600PROII_v1.08.bin]      # build every tier for one model, prints hashes
python tools/patcher_gui.py path/to/OEM.bin --tier R                  # headless build of one tier (S, R, X, R+, X+), hash-verified
python tools/patcher_gui.py path/to/OEM.bin --tier all -o out         # all tiers into out/
python tools/patcher_gui.py                                           # drag-and-drop GUI (tkinter; optional tkinterdnd2)
python tools/disasm.py [Model]                                        # regenerate models/<Model>/disasm/ (needs capstone>=5)
python tools/disasm.py --file X.bin --detect                          # rank candidate load addresses for a new image
python tools/compare_features.py A.bin B.bin                          # shared blocks / unique strings between two images
pip install pyinstaller tkinterdnd2 && python tools/build_executable.py   # dist/GodoxFirmwarePatcher(.exe|.app)
```

The closest thing to a test is running `tools/patcher_gui.py <OEM.bin> --tier all`. `patcher_core` raises if any output hash differs from `MODEL_SPECS`. The standalone `patch.py` only *warns* on a base-hash mismatch, so prefer the `patcher_gui.py` path to verify a change.

## Architecture

**Three layers, with hashes duplicated on purpose:**

1. `tools/fwversion.py` is the single home of the version scheme (`<Godox version>.<tier code>`, e.g. `1.08.02`), the tier table `TIERS` (S=1, R=2, X=3, R+=4, X+=5), output filenames, and bounds-checked string patching (`replace_cstring` writes into the string's existing 4-byte-aligned slot and rejects `%`; `fixed_version_format` turns a `V%d.%d%d` printf format into fixed text so code immediates stay stock).
2. `models/<Model>/patch.py` holds one script per model with offsets, original/patched byte templates and `apply_*` functions. Each `apply_*` checks the original bytes before writing and raises on mismatch. `build_profile(base_data, tier, output_dir)` is the entry point that `patcher_core` calls; it writes the file and returns its SHA-256. Each script inserts `tools/` into `sys.path` to import `fwversion`.
3. `tools/patcher_core.py` holds `MODEL_SPECS`, the registry of OEM size/SHA-256 and every tier's expected output hash. `identify_firmware()` classifies a dropped file (OEM match, already patched, reference-only, size match with wrong hash, unknown). `build_selected_tiers()` loads `models/<id>/patch.py` dynamically via `importlib` (from `sys._MEIPASS` when frozen by PyInstaller) and fails hard on any hash mismatch. `patcher_gui.py` is just the tkinter UI and CLI on top of it.

**Any change to a patch's output bytes** has to be propagated in four places: `MODEL_SPECS` in `patcher_core.py`, the build-hash table in `models/<Model>/README.md`, a new row in `CHANGELOG.md` (with the superseded hashes), and possibly `docs/tiers.md`. The on-screen version does *not* change for a patcher fix within the same tier, so builds are told apart only by SHA-256.

**Adding a model** also requires adding it to `MODEL_DIRS` in `tools/build_executable.py` (hard-coded list; it is bundled via `--add-data`) and to `MODELS` in `tools/disasm.py` (with its load address). Porting to a new Godox release is described step by step in `tools/README.md`.

**Model quirks worth knowing:**
- Images load behind a bootloader, not at `0x08000000`. File offset = runtime address − load address (`0x0800C000` for all except V100N at `0x08008000`). Code comments and docs use runtime addresses (`fn_XXXXXXXX` names from `disasm.py`), while patch scripts use file offsets. Keep both in comments, as existing scripts do.
- iT30ProN has a 44-byte integrity footer at `0xA8000` (MD5 of `file[0:0xA8000]`); its `patch.py` must recompute it after every patch.
- Fanless models (V100N, iT30ProN) have no Tier S. R+/X+ exist only on AD600Pro II.

## Disassembly and docs

- `models/<Model>/disasm/*.asm` are generated, multi-megabyte listings (5–11 MB). Grep them, and use `*.functions.csv` / `*.strings.txt` to locate things; never read them whole. Don't hand-edit them; regenerate with `tools/disasm.py`.
- `docs/architecture.md` is the cross-model reference (platform/MCU, load addresses, update path, heat-counter design, HSS detection, thermal). Per-model routines, tables and byte-diff tables are in `models/<Model>/README.md`. `docs/tiers.md` covers tier definitions and safety.
- Docs convention: every claim is "verified in the disassembly" unless marked 🔶 partial or ⚠️ unverified. "Verified" never means hardware-tested; hardware results are stated with an explicit date. Keep to this when adding findings.

## Release

`.github/workflows/build_patcher.yml` builds the Windows `.exe` and macOS `.app` with PyInstaller on Python 3.12. On a `v*` tag push it attaches both to a GitHub Release. It can also be run manually via `workflow_dispatch`.
