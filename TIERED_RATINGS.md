# Godox Custom Firmware Classification & Profiles

**Scope:** Godox AD600Pro II (primary focus), AD200Pro II, AD100Pro II, V100N, iT30ProN  
**Last updated:** 2026-10-13  
**Status legend:** ✅ verified in code · 🔶 partial · ⚠️ unverified ([FINDINGS.md](FINDINGS.md#status-legend))

---

## 1. Classification Framework

Rather than subjective letter grades, each custom build is evaluated directly on how it modifies the two firmware protection layers:

1. **Single-Burst Protection (Instantaneous Die Heating):**
   Governed by the points added per flash in the lookup tables (`fn_080134E4` on AD600Pro II).
   * **Stock:** Table values unchanged. The maximum continuous shot count before cooldown is locked to factory limits.
   * **Reduced:** Table values lowered. Allows more continuous shots in a single rapid burst before algorithmic cooldown triggers, increasing transient thermal load on the IGBT die.

2. **Repeated-Burst Protection (Inter-Burst Pause Recovery):**
   Governed by the background leaky bucket drain routine (`fn_08013694` on AD600Pro II).
   * **Stock:** Points drain at the factory rate (e.g. 40 points per 50 idle steps on AD600Pro II).
   * **Reduced:** Points drain faster (e.g. 80 points per 50 idle steps). Shortens the required rest pause between bursts. On models with a continuous fan (AD600Pro II, AD100Pro II), active airflow cools the heatsink during pauses to support this faster drain.

---

## 2. Firmware Profiles & Version Scheme

Each build shows a three-part version on the strobe's screen: the official Godox version it is based on, followed by the tier code (e.g. `1.08.02` = AD600Pro II v1.08, Tier R). A tier keeps its code on every model and every base version. See the [root README §1](README.md#1-firmware-profiles--version-scheme).

| Profile | Code | Tier Code | Changes | Single-Burst Protection | Repeated-Burst Protection |
|---|---|---|---|---|---|
| **Studio** | **S** | `.01` | Continuous fan (AD600 Level 2 / AD100 / AD200 H200 II) | ✅ Stock | ✅ Stock (extra cooling) |
| **Recovery** | **R** | `.02` | + 2× faster primary drain (16.0 pts/s vs 8.0) | ✅ Stock | ⚠️ Reduced (fan-assisted on AD600/AD200/AD100) |
| **Super** | **X** | `.03` | + lower per-shot HSS table cost | ⚠️ Reduced | ⚠️ Reduced |
| **Recovery+** | **R+** | `.04` | + 2× drain on primary and **pre-latch secondary** burst counters | ✅ Stock | ⚠️ Reduced (2× primary + 2× pre-latch secondary) |
| **Super+** | **X+** | `.05` | + 2× drain (both) + lower HSS + **burst throttle bypassed** | ⚠️ Reduced (80 clean) | ⚠️ Reduced (2× on all pauses) |

---

## 3. Model Support Matrix

### 3.1 Godox AD600Pro II
*Chassis: Cast aluminum heatsink, internal chassis fan (`fn_08010E74` — continuous Level 2 operation confirmed on hardware 2026-10-10), dual raw ADC NTC thermistors (NTC A at `0x2000002C` coupled to LED modeling lamp / head; NTC B at `0x2000002E` on main board / IGBT trips Error E2 < 49.69; either NTC < 132 trips 9 s forced cooldown, fan stages at < 271 / < 356 ✅), AC adapter support.*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | `AD600PROII_v1.08.01_studio.bin` | `1.08.01` | Fan branch (`0x080174BC`: `1D D0` → `1D E0`) | ✅ Code verified |
| **Tier R (Recovery)** | `AD600PROII_v1.08.02_recovery.bin` | `1.08.02` | Fan branch + 2× primary drain (`40` → `80` at `0x080136CC`/`D0`) | ✅ Code verified |
| **Tier X (Super)** | `AD600PROII_v1.08.03_super.bin` | `1.08.03` | Fan branch + 2× primary drain + HSS heat table lowered at `0x080398F0` | ✅ Code verified (HSS 105-pulse table; optical train 🔶) |
| **Tier R+ (Recovery+)** | `AD600PROII_v1.08.04_recovery_plus.bin` | `1.08.04` | Fan branch + 2× primary drain + **2× pre-latch secondary burst drain** (`40` → `80` at `0x08013744`/`48`) | ✅ Flashed & Level 2 fan mod confirmed on hardware (2026-10-10) |
| **Tier X+ (Super+)** | `AD600PROII_v1.08.05_super_plus.bin` | `1.08.05` | Fan branch + 2× drain (both) + lowered HSS table + **burst throttle bypassed** (`0x0801361C`: `09 D3` → `09 E0`) | ✅ Code verified (HSS table; optical train 🔶) |

*The AD600Pro II stores its version as an 8-byte text slot (`v1.08`), so the 7-character build version is shown without the leading `v`.*

#### Burst Table & Throttle Details for Tier R+ / X / X+ (AD600Pro II):
* In table `0x080398F0` (indexed when `0x200000DD = 1`), 28 halfwords are patched.
* The highest cost entry drops from 100 to 80 points. At a 6400-point threshold, continuous HSS burst limit increases from 64 to 80 shots (+25%).
* Across all other entries, points are reduced by **16.7% to 28.9%** (yielding **+20.0% to +40.6%** more continuous shots).
* **Burst Throttle (Tier R+ vs Tier X+):** In stock firmware and Tiers S/R/X/R+, a secondary accumulator (`[+0x16]`) triggers a 0.5 s charge delay lock (`0x2000004A = 5`) and sets a latch (`0x2000004C = 1`) after 3000 points (~38 full-power shots in standard mode, ~30 in stock HSS). In **Tier R+ (`.04`)**, the secondary drain is doubled from 40 to 80 points per 2.0 s (`20 → 40 pts/s`), which drains accumulated secondary points twice as fast during pauses **before** the 3000-point latch trips (once latched, `0x2000004C` only clears after 30.0 s with zero flashes at `0x0801373A`). In **Tier X+ (`.05`)**, the trip branch at `0x0801361C` is converted to an unconditional skip (`blo` → `b`), completely eliminating the 38-shot mid-burst throttle and permitting clean, continuous firing up to the 80-shot main threshold.

---

### 3.2 Godox AD200Pro II
*Chassis: Modular pocket strobe. Passive main body with internal heatsink; the `H200 II` fresnel head (`0x20000095 == 6`) has a built-in cooling fan (confirmed on hardware 2026-10-10) controlled by the body firmware via bit-banged I2C slave `0x5C` reg `0x01` in `fn_080237B0` (`✅`). Flashing via Godox G3, LCD version display, and continuous H200 II fan mod confirmed on hardware (2026-10-14); functional endurance testing pending.*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | `AD200ProII_V1.05.01_studio.bin` | `V1.05.01` | Continuous `H200 II` head fan via I2C slave `0x5C` reg `0x01` (`0x178BA`: `28 78` → `01 20`; `0x1791A`: `2c 70` → `2f 70`). Stock limits. | ✅ Flashed & continuous H200 II fan confirmed on hardware (2026-10-14) |
| **Tier R (Recovery)** | `AD200ProII_V1.05.02_recovery.bin` | `V1.05.02` | Continuous `H200 II` fan + 2× primary drain: Heads {0, 1} [H200] `125` → `250`, Heads {2, 3, 4} [H200R / H200J / R200] `100` → `200` (`0x080123CA`–`D8`) | ✅ Flashed & continuous H200 II fan confirmed on hardware (2026-10-14) |
| **Tier X (Super)** | `AD200ProII_V1.05.03_super.bin` | `V1.05.03` | Continuous `H200 II` fan + 2× drain + HSS tables C & D lowered ~20% (**33 → 41** shots at 185→148, **50 → 63** shots at 120→96) | ✅ Code verified (HSS 100-pulse tables; optical train 🔶; continuous fan confirmed) |

---

### 3.3 Godox V100N
*Chassis: On-camera round-head speedlite (⚠️ absence of evidence: no fan driver code in firmware). Flashing via Godox G3 and LCD version display confirmed on hardware (2026-10-10); functional endurance testing pending.*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | *Not available* | — | Fanless hardware. | — |
| **Tier R (Recovery)** | `V100N_V1.04.02_recovery.bin` | `V1.04.02` | 2× drain: `50` → `100` on primary and pre-latch secondary accumulators (`0x0800F498`–`B2`) | ✅ Code verified (fanless body) |
| **Tier X (Super)** | `V100N_V1.04.03_super.bin` | `V1.04.03` | 2× drain + ALT (HSS) table lowered 20% across all 11 zoom rows (60 → 75 shots at 100) | ✅ Code verified (HSS 80-pulse table; optical train 🔶) |

---

### 3.4 Godox iT30Pro (Nikon, iT30ProN)
*Chassis: Mini on-camera speedlite (⚠️ absence of evidence: no fan driver code in firmware). The image ends in an MD5 footer, which the patcher recomputes. Flashing via Godox G3 and LCD version display confirmed on hardware (2026-10-10); functional endurance testing pending. See [`it30ProN/README.md`](it30ProN/README.md).*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | *Not available* | — | Fanless hardware. | — |
| **Tier R (Recovery)** | `iT30ProN_V1.02.02_recovery.bin` | `V1.02.02` | 2× drain: `80` → `160` on primary and pre-latch secondary accumulators (`0x080141CC`–`E6`) | ✅ Code verified (fanless body) |
| **Tier X (Super)** | `iT30ProN_V1.02.03_super.bin` | `V1.02.03` | 2× drain + multi-pulse HSS table `0x0804FFAC` lowered 20% across all 11 rows (40 → 50 shots at column 21) | ✅ Code verified (80-pulse HSS table; optical train 🔶) |

---

### 3.5 Godox AD100Pro II
*Chassis: Ultra-compact round-head pocket strobe with built-in active cooling fan (GPIOC Pin 4 driven via `fn_080100a2`, controlled by `fn_08014370`; stock: on above 1200 points, below 271 raw NTC counts, or when modeling lamp ≥ 60%), single raw-ADC NTC (`fn_08014234`: < 114.59 forces cooldown). **Tier R (`1.07.02`) flashed via G3; continuous fan and version display (Device Info + settings menu) confirmed on hardware (2026-10-11)**; functional endurance testing pending. See [`AD100ProII/README.md`](AD100ProII/README.md).*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | `AD100ProII_V1.07.01_studio.bin` | `1.07.01` | Continuous Active Fan branch (`0x080143A2`: `29 78` → `24 E0`, `b #0x80143ee`) | ✅ Code verified |
| **Tier R (Recovery)** | `AD100ProII_V1.07.02_recovery.bin` | `1.07.02` | Continuous Fan + 2× drain: Primary `25` → `50` (`0x5224`/`28`), Pre-latch Secondary `30` → `60` (`0x5278`/`7C`) | ✅ Flashed & continuous fan confirmed on hardware (2026-10-11) |
| **Tier X (Super)** | `AD100ProII_V1.07.03_super.bin` | `1.07.03` | Continuous Fan + 2× drain + Table Set 2 (HSS `0x26F48`) lowered ~20% across all 11 rows (60 → 75 shots at 1/1) | ✅ Code verified (flag `[0x20000028,#0xD]` set in `fn_08012334` / `fn_08017A8C`; optical train 🔶) |

---

## 4. Summary of Verification & Limits

1. **Continuous Bursts on AD600Pro II:**
   Every flash pop resets the idle timer to 1200 (`0x0801357C`) outside cooldown. The drain only fires after 50 timer steps without a flash. In Tier S and Tier R, single-burst capacity is identical to stock OEM firmware.
2. **Exact Drain Timing (0.100 s / step):**
   Across all five models, timer steps execute at **0.100 s (100 ms)** nominal (derived from hardware timer ISRs with dual-stage prescalers, based on internal 16 MHz RC oscillators ±1% at 168 MHz with 84 MHz APB1 timer clocks on AD600/AD200/AD100/iT30ProN; GD32F4 IRC16M at 240 MHz with TIMERSEL set on V100N). The 50-step drain interval is **5.000 s** nominal (**6.000 s** / 60 steps on iT30ProN). Tier R doubles the points drained per interval.
3. **Repeated Bursts and Pauses:**
   Tier R cuts primary accumulator drain time in half (e.g. 16.0 pts/s vs 8.0 pts/s on AD600; with non-HSS extra idle drain ~1.865× faster). On models with patched secondary drain (AD600 Tier R+, AD100, V100N, iT30ProN), pre-latch secondary points also drain twice as fast between bursts before the secondary threshold trips; once latched, clearing the secondary throttle still requires the full flash-free window (30 s on AD600, 180 s on AD100, 120 s on V100N, 240 s on iT30ProN).
4. **Physical Protection (Error E2 & Sensors):**
   Physical hardware thermal protections remain active across all models and tiers:
   - **AD600Pro II:** Dual NTC thermistors compare against raw ADC counts: NTC B (`0x2000002E`, main board / IGBT) dropping below 49.69 raw ADC trips Error E2; either NTC A (`0x2000002C`, head / modeling lamp) or NTC B dropping below 132 raw ADC trips a 9.0 s forced cooldown; raw ADC < 271 / < 356 engage fan stages.
   - **AD200Pro II:** Analog head NTC on ADC `0x200000AE` (`fn_08015C78`: < 75 severe overheat, < 132 forced cooldown `fn_0800E1E4`) and `H200 II` digital NTC via I2C slave `0x5C` reg `0x06` (`[0x200001E6]` in `fn_080237B0`: < 260 severe overheat, < 396 forced cooldown).
   - **AD100Pro II:** Raw ADC NTC at `0x20000010` (`fn_08014234`: < 114.59 forces 300 s cooldown `fn_0800e178`, recovers ≥ 204.14).
   - **V100N:** Real NTC thermistor path on ADC0 DMA average (`0x200004B6`) trips forced cooldown below 98.98 raw ADC (`fn_0800D544`). In software, secondary accumulator latches a hard charge inhibit of 0–1.5 s via `fn_0800E52C` (charger-off GPIO pin) under heavy bursts until 120 s without flashes.
   - **iT30ProN:** Dual NTCs at `0x20000520` (`fn_08025B88`: raw 20–203) and `0x20000522` (`fn_0801797C`: raw < 183) force the 600 s cooldown via `fn_0800FA1C`.
   However, thermistors react over seconds, not milliseconds, so they do not replace the algorithmic protection during fast continuous bursts.
