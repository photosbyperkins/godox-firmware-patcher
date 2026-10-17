# Godox Firmware Patcher

Reverse-engineering notes and deterministic patchers that build custom firmware for five Godox flashes from the official Godox images. The patches change the fan behaviour and the firmware's heat counter (the "shot limit"); every other part of the image stays byte-for-byte stock.

> [!WARNING]
> **Experimental. Use at your own risk.** "Verified" in these docs means *read from the disassembly*, not *endurance-tested on hardware*. Tiers R, X, R+ and X+ loosen the firmware heat counter, which exists to protect the IGBT from millisecond-scale die heating that the thermistors are too slow to catch. See [Safety](docs/tiers.md#safety) before flashing anything other than Tier S.

## Supported models

| Model | Type | OEM base image | Tiers | Hardware-confirmed | Docs |
|---|---|---|---|---|---|
| AD600Pro II | 600 Ws strobe, internal fan | `AD600PROII_v1.08.bin` | S · R · X · R+ · X+ | `1.08.04` flashed; version and Level 2 fan confirmed (2026-10-10) | [models/AD600ProII](models/AD600ProII/README.md) |
| AD200Pro II | 200 Ws modular strobe | `AD200ProII_V1.05.bin` | S · R · X | `V1.05.01`/`.02` flashed; version and H200 II head fan confirmed (2026-10-14) | [models/AD200ProII](models/AD200ProII/README.md) |
| AD100Pro II | 100 Ws round-head strobe, internal fan | `AD100ProII_RF433V1_07.bin` | S · R · X | `1.07.02` flashed; version and fan confirmed (2026-10-11) | [models/AD100ProII](models/AD100ProII/README.md) |
| V100N | 100 Ws round-head speedlite (Nikon), fanless | `V100N_V1.04.bin` | R · X | Flashed; version confirmed (2026-10-10) | [models/V100N](models/V100N/README.md) |
| iT30Pro (Nikon) | Mini speedlite, fanless | `iT30ProN_V1.02.bin` | R · X | `V1.02.03` flashed; version and MD5 footer accepted (2026-10-10) | [models/iT30ProN](models/iT30ProN/README.md) |

No build has been endurance-tested. Restoring OEM firmware with Godox G3 is confirmed working (2026-10-09).

## Tiers

| Code | Tier | Change | Single-burst limit | Recovery between bursts |
|---|---|---|---|---|
| `.01` | **S** Studio | Fan forced on (AD600, AD100, AD200 with H200 II head) | Stock | Stock (extra cooling) |
| `.02` | **R** Recovery | S + 2× heat-counter drain | Stock | 2× faster |
| `.03` | **X** Super | R + HSS cost table lowered ~20% | +24–26 % HSS shots | 2× faster |
| `.04` | **R+** Recovery+ | R + 2× drain on the secondary burst counter (AD600 only) | Stock | 2× faster (both counters) |
| `.05` | **X+** Super+ | R+ + X + secondary burst throttle removed (AD600 only) | 80 full-power shots without the 38-shot stutter | 2× faster (both counters) |

Fanless models have no Tier S; their Tier R/X still carry the drain and table changes. Definitions, per-model numbers and risk: [docs/tiers.md](docs/tiers.md).

### Version scheme

A custom build shows `<Godox version>.<tier code>` on the strobe, e.g. `1.08.02` = AD600Pro II v1.08, Tier R. Godox only uses two parts, so a three-part version always means a custom build. A patcher fix that keeps the tier keeps the version too; such revisions are told apart by SHA-256 in the [changelog](CHANGELOG.md). The scheme is implemented once, in [`tools/fwversion.py`](tools/fwversion.py).

## Usage

### 1. Get the official firmware

This repository does not host or download Godox firmware or tools. Download the image from [Godox firmware downloads](https://www.godox.com/firmware-flash/) and check its hash:

| Model | File | Size (bytes) | SHA-256 |
|---|---|---|---|
| AD600Pro II | `AD600PROII_v1.08.bin` | 407,384 | `33e327457bef0023af5254153a990a572c6a3afeb792fdb84e5bf137613bf910` |
| AD200Pro II | `AD200ProII_V1.05.bin` | 387,248 | `30783860ede87b4bd30678cf820a8f2f6e0d8bc505344d42de1d3561c69f400b` |
| AD100Pro II | `AD100ProII_RF433V1_07.bin` ¹ | 357,004 | `5dd2dd434e0ca531a57fd5ad397a9de1cf4e8acf2374aa6bfc5d7fed17c135dc` |
| V100N | `V100N_V1.04.bin` | 1,001,676 | `18e3581c601cc7c15e81bbbe951b8b336e133de822f99450f57f116ffab37ee6` |
| iT30Pro (Nikon) | `iT30ProN_V1.02.bin` | 688,172 | `a6920833d267834e7ff41f537ce8b897bab47234013731ae79b4affcbf41847e` |

¹ Not on the public download page; request it from Godox support.

### 2. Build

**Desktop app.** Run `GodoxFirmwarePatcher` (Windows `.exe` / macOS `.app`, attached to GitHub Releases or built with `python tools/build_executable.py`). Drop the OEM `.bin` on the window, pick a tier, click **Patch**. The app identifies the model by SHA-256, refuses unknown or already-patched files, and checks every output against its expected hash.

**Command line** (Python 3, standard library only):

```bash
python tools/patcher_gui.py path/to/AD600PROII_v1.08.bin --tier R      # one tier (S, R, X, R+, X+)
python tools/patcher_gui.py path/to/AD600PROII_v1.08.bin --tier all    # every tier; -o DIR to choose output folder
python models/AD600ProII/patch.py [path/to/AD600PROII_v1.08.bin]       # per-model script, writes all tiers to its folder
```

A per-model script looks for the OEM file in its own folder, then in `_local_godox_assets/<Model>/`, then in the repository root. Output hashes are listed in each model's README.

### 3. Flash

Requires Windows 10/11, [Godox G3](https://www.godox.com/firmware-flash/) (`Godox_G3_v1.1.exe`), a direct USB-C connection, and a battery above 50 % (or AC power).

1. Power the strobe off and connect it by USB-C.
2. Start Godox G3; the strobe is detected automatically.
3. **Select File** → the custom `.bin` → **Upgrade**, and wait for 100 %.
4. Disconnect, power on, and check the version in Device Info (e.g. `1.08.02` on the AD600Pro II, `V1.05.02` on the AD200Pro II).

**Restore:** flash the OEM image the same way. The strobe shows its two-part version again (`v1.08`, `V1.05`, `V1.07`, `V1.04`, `V1.02`).

> [!TIP]
> The USB bootloader lives in flash below the application (`0x08000000` up to the load address) and is not touched by an update. Flashing the wrong model's image leaves the strobe blinking with a blank screen; re-flashing the correct image with G3 recovers it (confirmed on an AD200Pro II, 2026-10-14).

## Repository layout

```
├── README.md                  this file
├── CHANGELOG.md               build revisions and superseded hashes
├── docs/
│   ├── tiers.md               tier definitions, per-model effect, safety
│   └── architecture.md        cross-model reverse-engineering reference
├── models/<Model>/
│   ├── README.md              addresses, byte diffs, build hashes for that model
│   ├── patch.py               builds every tier for that model
│   └── disasm/                .asm listing, functions.csv, strings.txt
├── tools/
│   ├── README.md              tool usage, disassembly and porting notes
│   ├── fwversion.py           shared version scheme and safe string patching
│   ├── patcher_core.py        model detection and verified builds (GUI/CLI backend)
│   ├── patcher_gui.py         drag-and-drop app and headless CLI
│   ├── build_executable.py    PyInstaller build of the app
│   ├── disasm.py              Thumb-2 disassembler with load-address detection
│   └── compare_features.py    block/string diff of two images
└── .github/workflows/         builds the Windows/macOS app on v* tags
```

Proprietary files are git-ignored: OEM `.bin` images and Godox PDF manuals kept next to each `patch.py`, the G3 flasher, `_local_godox_assets/`, and `dist/`.

## Documentation

- [docs/tiers.md](docs/tiers.md) — what each tier changes, shot counts per model, safety rationale.
- [docs/architecture.md](docs/architecture.md) — load addresses, MCUs and timers, the shared heat-counter design, HSS detection, thermal sensors, image format, open questions.
- `models/<Model>/README.md` — per-model routines, tables, byte diffs and build hashes.
- [tools/README.md](tools/README.md) — patcher, disassembler, Ghidra/IDA import, porting to a new Godox release.
- [CHANGELOG.md](CHANGELOG.md) — build history.

## Legal

Godox is a trademark of Shenzhen GODOX Photo Equipment Co., Ltd. This is an independent, clean-room research project, not affiliated with or endorsed by Godox. No Godox firmware, updater or manual is distributed here; the patchers transform OEM files that the user obtains. Code and documentation are released under the [MIT License](LICENSE). You are responsible for any damage, injury, voided warranty or malfunction that results from building or flashing these images.
