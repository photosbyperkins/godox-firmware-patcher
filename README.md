# Godox Custom Firmware & Reverse-Engineering Project

Open-source reverse-engineering analysis, technical documentation, and experimental firmware patches for modern Godox strobes.

Primary development focus: **Godox AD600Pro II**  
Secondary supported models: **Godox AD200Pro II**, **Godox AD100Pro II**, **Godox V100N**, **Godox iT30Pro (Nikon)** *(flashing & LCD version confirmed on hardware across all models)*

---

> [!WARNING]
> **Experimental Firmware — Use at Your Own Risk:**
> * None of the modified images have undergone long-term hardware endurance testing. "Verified" in these documents means the code logic was verified in ARM Cortex-M Thumb-2 disassembly against official firmware binaries.
> * Modifying the algorithmic heat accumulator reduces thermal safety margins designed to prevent transient IGBT die destruction during rapid firing. Physical Error E2 thermistors react over seconds and **cannot** protect against millisecond die overheating. See [FINDINGS.md §4](FINDINGS.md#4-why-the-heat-counter-matters-for-safety).

---

## 1. Firmware Profiles & Version Scheme

Custom builds use a three-part version: **`<Godox version>.<tier code>`**.

```
1.08.02
└─┬┘ └┬┘
  │   └── tier code: 01 S · 02 R · 03 X · 04 R+ · 05 X+
  └────── official Godox firmware the build is based on (unchanged)
```

* Godox only ever uses two parts (`1.08`), so a three-part version on the strobe's screen always means a custom build.
* The base version stays readable. When Godox releases new firmware (say `1.09`), builds based on it become `1.09.02`, and so on.
* A tier keeps its code on every model and every base version.
* Patcher fixes that don't change a tier (e.g. the 2026-10-10 iT30 MD5 fix) keep the same on-screen version. They are tracked by SHA-256 in the [build changelog](#8-build-changelog).
* The scheme lives in [`tools/fwversion.py`](tools/fwversion.py), which all patchers share. The AD600Pro II stores its version as an 8-byte text slot, so its builds show `1.08.02` without the leading `v`.

| Tier code | Profile | Core Modification | Single-Burst Limit | Inter-Burst Recovery | Recommended Use Case |
|---|---|---|---|---|---|
| *(none)* | **Factory** | Official Godox OEM firmware (e.g. `1.08`) | Factory stock | Factory stock | Standard field / battery shooting |
| **`.01`** | **Tier S (Studio)** | Continuous Fan Level 2 (100% PWM) | Factory stock | Factory stock *(enhanced cooling)* | AC adapter studio work / modeling lamp |
| **`.02`** | **Tier R (Recovery)** | 2× faster drain (+ Fan on AD600 / AD100) | Factory stock | 2× primary recovery | Fast turnaround (portraits, events) |
| **`.03`** | **Tier X (Super)** | 2× drain + ~20% lower HSS cost | **+23% to +25% burst** | 2× primary recovery | Action / HSS bursts |
| **`.04`** | **Tier R+ (Recovery+)** | Continuous Fan + 2× drain on **both** accumulators | Factory stock | **2× on all pauses** | Synchronized inter-burst recovery |
| **`.05`** | **Tier X+ (Super+)** | Continuous Fan + 2× drain (both) + Lowered HSS + **Throttle bypassed** | **80 shots clean (no stutter)** | **2× on all pauses** | Maximum performance / continuous bursts |

---

## 2. Model Matrix & Binary Specifications

All binary images match factory file sizes byte-for-byte. In accordance with clean-room open distribution practices, this repository **does not host or distribute copyrighted Godox firmware binaries or proprietary flashing executables**. Users are solely responsible for obtaining genuine OEM firmware directly from the official manufacturer channels. This project does not provide, host, or automatically download official firmware images. Users generate verified custom binaries locally by supplying official firmware files downloaded directly from Godox.

Detailed reverse-engineering specifications are documented in [**TIERED_RATINGS.md**](TIERED_RATINGS.md).

### 2.1 Godox AD600Pro II (Focus Model)
*Base: `AD600PROII_v1.08.bin` (407,384 bytes, Base `0x0800C000`)*

| Build | Output Filename | Target SHA-256 Checksum | Modifications |
|---|---|---|---|
| **OEM Stock** | `AD600PROII_v1.08.bin` | `33e327457bef0023af5254153a990a572c6a3afeb792fdb84e5bf137613bf910` | Factory baseline |
| **Tier S (Studio)** | `AD600PROII_v1.08.01_studio.bin` | `d85d22f05b84e5d259250da3c618f776e340f75d4f98dce922cc91f6c56c62ab` | Fan Level 2 continuous |
| **Tier R (Recovery)** | `AD600PROII_v1.08.02_recovery.bin` | `d51033cc1dd911764b9995ef81dee7e449ab8db6ef3c2886c7c414c386ee63de` | Fan Level 2 + 2× pause drain (40 → 80 pts) |
| **Tier X (Super)** | `AD600PROII_v1.08.03_super.bin` | `a9b4b0f5fc18a44d1e0af5a1e03db9da199fabfdcc4737c6a7f8f734cd780d27` | Fan Level 2 + 2× drain + HSS table patched |
| **Tier R+ (Recovery+)** | `AD600PROII_v1.08.04_recovery_plus.bin` | `69b27c2789c9604db6aa6bab507e02303f3fb3f07c308076b1c17eb11a849114` | Fan Level 2 + 2× drain on primary & secondary burst accumulators |
| **Tier X+ (Super+)** | `AD600PROII_v1.08.05_super_plus.bin` | `c62e16a60bee7cf534469e19dfc6acf21f821b7c3ecc570063099c58e2e0109e` | Fan Level 2 + 2× drain (both) + HSS table + Secondary burst throttle bypassed |

### 2.2 Godox AD200Pro II
*Base: `AD200ProII_V1.05.bin` (387,248 bytes, Base `0x0800C000`)*

| Build | Output Filename | Target SHA-256 Checksum | Modifications |
|---|---|---|---|
| **OEM Stock** | `AD200ProII_V1.05.bin` | `30783860ede87b4bd30678cf820a8f2f6e0d8bc505344d42de1d3561c69f400b` | Factory baseline |
| **Tier R (Recovery)** | `AD200ProII_V1.05.02_recovery.bin` | `c1cb659d626d054e74943d1cf2513e503f31a11c8d97db697336caff16937bf0` | 2× drain: bare bulb (125→250), speedlite (100→200) |
| **Tier X (Super)** | `AD200ProII_V1.05.03_super.bin` | `8da2612a2f2ea0f201f4d33f444ff708d259cfcd736ffcf1899dc4fa06ee450f` | 2× drain + HSS tables C & D lowered ~20% |

### 2.3 Godox AD100Pro II
*Base: `AD100ProII_RF433V1_07.bin` (357,004 bytes, Base `0x0800C000`)*

| Build | Output Filename | Target SHA-256 Checksum | Modifications |
|---|---|---|---|
| **OEM Stock** | `AD100ProII_RF433V1_07.bin` | `5dd2dd434e0ca531a57fd5ad397a9de1cf4e8acf2374aa6bfc5d7fed17c135dc` | Factory baseline |
| **Tier S (Studio)** | `AD100ProII_V1.07.01_studio.bin` | `8995f2b85fe0380282913d4d0697b7d3709d457b68257f6df2d57aec6eb55cc2` | Fan forced on (`0x080143A2`: `29 78` → `24 E0`) |
| **Tier R (Recovery)** | `AD100ProII_V1.07.02_recovery.bin` | `86386df6319f9e4ba3719e514525f565968d7a456c424008d26ba7eb892006bc` | Continuous Fan + 2× drain on primary (`25`→`50`) & secondary (`30`→`60`) |
| **Tier X (Super)** | `AD100ProII_V1.07.03_super.bin` | `71ad25e7f833f655fa129a6e37f048ed0baba09e1ce34e21f325834765d6b381` | Continuous Fan + 2× drain + Table Set 2 (HSS `0x26F48`) lowered ~20% |

### 2.4 Godox V100N
*Base: `V100N_V1.04.bin` (1,001,676 bytes, Base `0x08008000`)*

| Build | Output Filename | Target SHA-256 Checksum | Modifications |
|---|---|---|---|
| **OEM Stock** | `V100N_V1.04.bin` | `18e3581c601cc7c15e81bbbe951b8b336e133de822f99450f57f116ffab37ee6` | Factory baseline |
| **Tier R (Recovery)** | `V100N_V1.04.02_recovery.bin` | `f3855ac2132eade59df334b4d1d406c38689d72ab4d91be9ba6c8cbb8ebba80d` | 2× drain (50 → 100 on both accumulators) |
| **Tier X (Super)** | `V100N_V1.04.03_super.bin` | `af32bb854c4a7551029874151a930210ef0cb1cb3a9ecc3acd4df72bdbba383c` | 2× drain + ALT (HSS) table lowered 20% across all 11 rows |

### 2.5 Godox iT30Pro (Nikon, iT30ProN)
*Base: `iT30ProN_V1.02.bin` (688,172 bytes, Base `0x0800C000`). The image ends in an MD5 footer, which the patcher recomputes. See [`it30ProN/README.md`](it30ProN/README.md).*

| Build | Output Filename | Target SHA-256 Checksum | Modifications |
|---|---|---|---|
| **OEM Stock** | `iT30ProN_V1.02.bin` | `a6920833d267834e7ff41f537ce8b897bab47234013731ae79b4affcbf41847e` | Factory baseline |
| **Tier R (Recovery)** | `iT30ProN_V1.02.02_recovery.bin` | `13357697a6aa2c56afd15727f9f32148f5c11e6954e205337fa7031b0d317c27` | 2× drain (80 → 160 on both accumulators) |
| **Tier X (Super)** | `iT30ProN_V1.02.03_super.bin` | `eebbc0210a912dff953cff3a89a0cbba722ef847bc1b2400480676bb6f9afaac` | 2× drain + multi-pulse table lowered ~20% across all 11 rows |

### 2.6 Verified Power Mapping, Zoom Rows & Hardware Timing

Disassembly analysis of GUI rendering routines (`tbb` branch tables), SRAM state variables, and algorithmic lookup tables confirms how strobe settings and hardware timers link directly to the thermal accumulator:

* **Internal Power Variable ($P$):** Stored in SRAM as 1/10-stop decrements below full power ($P = 0$ is **1/1 full power**, $P = 10$ is **1/2**, $P = 20$ is **1/4**, etc.).
* **UI Disassembly Verification:**
  * **AD600Pro II (`fn_08016aac`):** Renders fraction mode (1/1 to 1/512) and decimal mode (10.0 to 1.0). When $P = 0$, table branch `0x08016ad4` routes to `'1'` (1/1) or `'10.0'`. Table `0x0803985C` maps $P = 0$ to top index **27** (80 pts $\rightarrow$ exactly **80 shots** to the 6400 limit).
  * **AD200Pro II (`0x080148be` / `0x08014914`):** Renders 1/1 to 1/256 (or 1/512 for heads 1, 2, 3; capped at 1/128 in special modes). When $P = 0$, branch `0x08014938` loads denominator 1 (1/1). Table `0x0804143E` maps $P = 0$ to top index **24** (150 pts for heads {0, 1} [standard fresnel H200] $\rightarrow$ **40 shots**; 100 pts for heads {2, 3, 4} [H200R / H200J / R200] $\rightarrow$ **60 shots** to the 6000 limit).
  * **AD100Pro II (`fn_08010fec`):** Byte table `0x08032CD0` maps $P = 0$ to top column **24** (1/1). Table Set 1 (`0x08032D22`) row 0 costs 100 pts at 1/1 (**60 shots** to the 6000 limit); rows 4–7 cost 60 pts (**100 shots**). What the row (`[0x20000001] & 7`) means is untraced ⚠️. Internal cooling fan on GPIOC Pin 4 is driven via `fn_080100a2` and controlled by `fn_08014370` (in stock firmware: on while the accumulator is above 1200 points or the thermistor reads below 271 raw counts).
  * **V100N (`fn_08011670` / `fn_0800ec4c`):** Renders 1/1 to 1/256 (capped at 80). `fn_0800ec4c` maps $P < 3$ ($P = 0$) to top column **21** (86 to 60 pts across zoom rows $\rightarrow$ **70 to 100 shots** to the 6000 limit).
* **V100N Zoom Row Mapping:** Row = index + 1 from table `0x08051694` (11 entries). Row 0 is the special `0x200004DE == 1` flag (wide panel / bounce); Rows 1–10 map to focal lengths `20, 24, 28, 35, 50, 70, 80, 105, 135, 200` mm. Table `0x080516A0` is a charge-control table, not motor steps.
* **Step Timing (0.100 s / step):** All models utilize a synchronized 2-stage prescaler timer architecture yielding **0.100 s (100 ms)** nominal per step (derived from internal RC oscillators ±1% on AD600/AD200/AD100; GD32F4 IRC16M at 240 MHz with TIMERSEL set on V100N), gated by active run-state flags. Leaky-bucket drain intervals (50 timer steps) execute every **5.000 s** nominal.
* **Physical Thermal Sensors & Protections:**
  * **AD600Pro II:** Dual NTC thermistors compare directly against raw ADC counts (no temperature conversion to °C exists in firmware; lower ADC count = hotter). NTC B dropping below 49.69 raw ADC triggers Error E2; either NTC dropping below 132 raw ADC triggers a 9.0 s forced cooldown (`fn_080103B4`); raw ADC below 271.06 and 356.03 engage fan levels 2 and 1. Which physical sensor is flash tube vs IGBT heatsink is not determinable from code.
  * **AD200Pro II:** ADC1 IN2 raw float threshold (< 541.42 for 101 calls sets `0x20000124`; after 12,000 ticks sets `0x2000005E`). Sensor type is unknown (no temperature conversion in code).
  * **AD100Pro II:** One NTC, raw ADC at `0x20000010` (`fn_08014234`; no °C conversion, lower = hotter). > 950 / < 20 = sensor fault (self-test `NTC:E1` / `NTC:E2`); < 114.59 forces the 300 s throttled cooldown (`fn_0800e178`), recovering at ≥ 204.14; < 271.06 / < 356.03 set fan states 2 / 1.
  * **V100N:** Real NTC thermistor path via ADC0 DMA average (`0x200004B6`) forces cooldown trip when < 98.98 raw count (`fn_0800D544`, recovers at ≥ 176.3). In software, secondary thermal accumulator (`[+0x10]`, threshold 3000) drives a per-flash hard charge inhibit of 0–1.5 s via `fn_0800E52C` (charger-off GPIO pin) under heavy bursts until 120 s without flashes.
* **Exact Integer Thresholds:** All models evaluate accumulator trip points with `cmp` + `blo` ($\ge \text{threshold}$), confirming continuous burst limits from empty are exact mathematical boundaries.

---

## 3. Building Custom Firmwares

All modified binaries are generated deterministically using lightweight Python 3 patcher scripts (zero external dependencies).

### Step 1: Obtain Official Base Firmware
Users are solely responsible for obtaining genuine OEM firmware directly from the official manufacturer channels. This project does not provide, host, or automatically download official firmware images.

Download official firmware images directly from [Godox Firmware Downloads](https://www.godox.com/firmware-flash/):
* **AD600Pro II**: `AD600PROII_v1.08.bin`
* **AD200Pro II**: `AD200ProII_V1.05.bin`
* **AD100Pro II**: `AD100ProII_RF433V1_07.bin` *(not on Godox's public download page; obtain it from Godox support)*
* **V100N**: `V100N_V1.04.bin`
* **iT30Pro (Nikon)**: `iT30ProN_V1.02.bin`

Place the downloaded `.bin` file in the respective model directory (or pass its path as an argument to the patcher).

### Step 2: Run the Patcher Script
Execute the patcher for your strobe model:

```bash
# AD600Pro II: 1.08.01 - 1.08.05
python AD600ProII/patch.py

# AD200Pro II: V1.05.02, V1.05.03
python AD200ProII/patch.py

# AD100Pro II: V1.07.01, V1.07.02, V1.07.03
python AD100ProII/patch.py

# V100N: V1.04.02, V1.04.03
python V100N/patch.py

# iT30ProN: V1.02.02, V1.02.03 (also refreshes the MD5 footer)
python it30ProN/patch.py
```

The script verifies the SHA-256 hash of your official baseline file, applies the exact modifications, and outputs the patched `.bin` images while displaying their verified cryptographic hashes. Compare them with §2 and the [build changelog](#8-build-changelog).

---

## 4. How to Flash & Restore

Flashing is performed using Godox's official firmware update tool (**Godox G3 Firmware Flasher**).

### Requirements
* Windows 10 or 11 PC.
* [Godox G3 Firmware Flasher](https://www.godox.com/firmware-flash/) (downloaded from Godox).
* Quality USB-C cable connected directly to the computer.
* Strobe battery charged above 50% (or connected to AC power).

### Flashing Procedure
1. Ensure the strobe is **powered off**.
2. Connect the strobe to your computer via USB-C.
3. Launch the official Godox G3 utility (`Godox_G3_v1.1.exe`). The strobe should be detected automatically.
4. Click **Select File** and choose the desired locally generated `.bin` image (e.g. `AD600PROII_v1.08.01_studio.bin`).
5. Click **Upgrade**. Wait until the progress bar reaches 100% and confirms completion.
6. Disconnect the USB cable and power the strobe on. Check the Device Info screen to confirm the new three-part version number (e.g. `1.08.02` on the AD600Pro II, `V1.05.03` on the AD200Pro II).

### Restoring Official OEM Factory Firmware
To revert to factory firmware at any time:
1. Repeat the steps above, selecting your official OEM baseline file (e.g. `AD600PROII_v1.08.bin`, `AD200ProII_V1.05.bin`, `AD100ProII_RF433V1_07.bin`, `V100N_V1.04.bin`, or `iT30ProN_V1.02.bin`).
2. Click **Upgrade**. The strobe will be restored to 100% factory behavior and display its original two-part version number (`v1.08`, `V1.05`, `V1.07`, `V1.04`, or `V1.02`).

---

## 5. Technical Documentation

* [**`FINDINGS.md`**](FINDINGS.md) — Authoritative reverse-engineering report: memory maps, disassembly proofs, thermistor ADC math, fan driver logic, and safety architecture.
* [**`TIERED_RATINGS.md`**](TIERED_RATINGS.md) — Detailed technical breakdown of Tier S, Tier R, and Tier X profiles, thermal mechanisms, and shot count comparisons.
* [**`firmware_comparison_analysis.md`**](firmware_comparison_analysis.md) — Architectural comparison across all analyzed Godox flash models.
* Model-specific guides:
  * [`AD600ProII/SUPER_MODE.md`](AD600ProII/SUPER_MODE.md) — AD600Pro II byte diffs and reverse-engineering details.
  * [`AD200ProII/README.md`](AD200ProII/README.md) — AD200Pro II per-shot tables, 6000 threshold, and head-selection logic.
  * [`AD100ProII/README.md`](AD100ProII/README.md) — AD100Pro II per-shot tables, 6000 threshold, active fan driver, and HSS tables.
  * [`V100N/README.md`](V100N/README.md) — V100N dual-accumulator architecture and 11×22 matrix details.
  * [`it30ProN/README.md`](it30ProN/README.md) — iT30ProN dual-accumulator analysis, MD5 footer format, and verification notes.

---

## 6. Repository Layout

```
├── AD600ProII/                   # Flagship 600Ws strobe
│   ├── patch.py                  # Multi-tier patcher (1.08.01 - 1.08.05)
│   ├── SUPER_MODE.md             # Technical reference & byte diff
│   ├── README.md
│   └── disasm/                   # Disassembly listings & symbol tables
├── AD200ProII/                   # 200Ws modular pocket strobe
│   ├── patch.py                  # Multi-tier patcher (V1.05.02, V1.05.03)
│   ├── README.md
│   └── disasm/
├── AD100ProII/                   # 100Ws compact round-head pocket strobe
│   ├── patch.py                  # Multi-tier patcher (V1.07.01, V1.07.02, V1.07.03)
│   ├── README.md
│   └── disasm/
├── V100N/                        # 100Ws on-camera round head
│   ├── patch.py                  # Multi-tier patcher (V1.04.02, V1.04.03)
│   ├── README.md
│   └── disasm/
├── it30ProN/                     # iT30Pro mini speedlite (Nikon)
│   ├── patch.py                  # Multi-tier patcher (V1.02.02, V1.02.03) + MD5 footer
│   ├── README.md
│   └── disasm/
├── tools/                        # Reverse-engineering utilities
│   └── fwversion.py              # Shared version scheme & safe string patching
├── FINDINGS.md                   # Comprehensive technical audit
├── TIERED_RATINGS.md             # Formal classification specification
├── LICENSE                       # MIT open-source license
└── README.md                     # Project overview and instructions
```

*(Note: Official Godox `.bin` images, PDF manuals, and the `Godox_G3_v1.1.exe` flasher are proprietary assets and are excluded from Git tracking via `.gitignore`.)*

---

## 7. Legal Disclaimer & Distribution Policy

* Godox is a registered trademark of Shenzhen GODOX Photo Equipment Co., Ltd.
* This repository is an independent research and educational project conducted via clean-room reverse engineering. It is not affiliated with, sponsored by, or endorsed by Godox.
* No proprietary Godox binary code, copyrighted updater utilities, or instruction manuals are redistributed within this repository. All patcher scripts perform non-destructive, deterministic byte transformations on legitimately acquired OEM firmware files.
* All original patcher code, reverse-engineering documentation, and analysis tooling in this repository are released under the [MIT License](LICENSE).
* All trademarks, product names, and brand logos remain the property of their respective owners.
* By building or using these custom firmware images, you assume all responsibility for any hardware damage, personal injury, voided warranties, or malfunction resulting from their use.

---

## 8. Build Changelog

The on-screen version only tells you the base firmware and the tier. A patcher fix that keeps the tier the same also keeps the version, so use the SHA-256 to tell revisions apart. Add a row here whenever an output hash changes. The current hashes are listed in §2.

| Date | Model | Builds | Change | Superseded SHA-256 |
|---|---|---|---|---|
| 2026-10-11 | AD100Pro II | S, R, X | **Initial release.** Clean-room disassembly and reverse engineering of AD100Pro II v1.07 (`AD100ProII_RF433V1_07.bin`). Built Tier S (`1.07.01` continuous active fan on GPIOC Pin 4), Tier R (`1.07.02` fan + 2× drain on primary and secondary accumulators), and Tier X (`1.07.03` fan + 2× drain + 20% reduced HSS table expanding full-power burst to 75 shots). | — |
| 2026-10-10 | All | All tiers | **Version scheme standardization.** Adopted unified `<Godox version>.<tier code>` string format across all models, and standardized patchers to `patch.py`. The version is patched as fixed text, and digit immediates stay stock. The AD200Pro II and V100N settings-menu version readout is now patched as well. Thermal patches are unchanged. | Early experimental images |
| 2026-10-10 | iT30ProN | R, X | **MD5 footer fix.** The first iT30ProN images kept the stock MD5 at `0xA8000`, so G3 or the bootloader would most likely have rejected them (which of the two checks it is still unconfirmed). The patcher now recomputes it. | R `b9454658f204a4bf3a3cce4abb1b5f715132564b4925b7f638bc432e57ad5e78`, X `cee4c7bd45f6e30d44efc1f43b4eec0cd19443ecdefbbba08580f602125e8093` |
