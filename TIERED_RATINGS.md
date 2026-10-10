# Godox Custom Firmware Classification & Profiles

**Scope:** Godox AD600Pro II (primary focus), AD200Pro II, AD100Pro II, V100N, iT30ProN  
**Last updated:** 2026-10-11  
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
   * **Reduced:** Points drain faster (e.g. 80 points per 50 idle steps). Shortens the required rest pause between bursts. On models with a continuous fan (AD600Pro II), active airflow actively cools the heatsink during pauses to support this faster drain.

---

## 2. Firmware Profiles & Version Scheme

Each build shows a three-part version on the strobe's screen: the official Godox version it is based on, followed by the tier code (e.g. `1.08.02` = AD600Pro II v1.08, Tier R). A tier keeps its code on every model and every base version. See the [root README §1](README.md#1-firmware-profiles--version-scheme).

| Profile | Code | Tier Code | Changes | Single-Burst Protection | Repeated-Burst Protection |
|---|---|---|---|---|---|
| **Studio** | **S** | `.01` | Continuous fan level 2 | ✅ Stock | ✅ Stock (extra cooling) |
| **Recovery** | **R** | `.02` | + 2× faster primary drain (16.0 pts/s vs 8.0) | ✅ Stock | ⚠️ Reduced (fan-assisted on AD600) |
| **Super** | **X** | `.03` | + lower per-shot HSS table cost | ⚠️ Reduced | ⚠️ Reduced |
| **Recovery+** | **R+** | `.04` | + 2× drain on **both** primary and secondary burst counters | ✅ Stock | ⚠️ Reduced (synchronized 2× pauses) |
| **Super+** | **X+** | `.05` | + 2× drain (both) + lower HSS + **burst throttle bypassed** | ⚠️ Reduced (80 clean) | ⚠️ Reduced (synchronized 2× pauses) |

---

## 3. Model Support Matrix

### 3.1 Godox AD600Pro II
*Chassis: Cast aluminum heatsink, internal chassis fan (`fn_08010E74` — continuous Level 2 operation confirmed on hardware 2026-10-10), dual raw ADC NTC thermistors (NTC B < 49.69 trips E2, NTC A/B < 132 trips 9 s forced cooldown, fan stages at < 271 / < 356; sensor assignments unverified ⚠️), AC adapter support.*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | `AD600PROII_v1.08.01_studio.bin` | `1.08.01` | Fan branch (`0x080174BC`: `1D D0` → `1D E0`) | ✅ Code verified |
| **Tier R (Recovery)** | `AD600PROII_v1.08.02_recovery.bin` | `1.08.02` | Fan branch + 2× primary drain (`40` → `80` at `0x080136CC`/`D0`) | ✅ Code verified |
| **Tier X (Super)** | `AD600PROII_v1.08.03_super.bin` | `1.08.03` | Fan branch + 2× primary drain + second heat table lowered at `0x080398F0` | 🔶 Code verified (HSS 105-pulse table; optical train unverified) |
| **Tier R+ (Recovery+)** | `AD600PROII_v1.08.04_recovery_plus.bin` | `1.08.04` | Fan branch + 2× primary drain + **2× secondary burst drain** (`40` → `80` at `0x08013744`/`48`) | ✅ Flashed & Level 2 fan mod confirmed on hardware (2026-10-10) |
| **Tier X+ (Super+)** | `AD600PROII_v1.08.05_super_plus.bin` | `1.08.05` | Fan branch + 2× drain (both) + lowered HSS table + **burst throttle bypassed** (`0x0801361C`: `09 D3` → `09 E0`) | 🔶 Code verified (HSS table; optical train unverified) |

*The AD600Pro II stores its version as an 8-byte text slot (`v1.08`), so the 7-character build version is shown without the leading `v`.*

#### Burst Table & Throttle Details for Tier X / X+ (AD600Pro II):
* In table `0x080398F0` (indexed when `0x200000DD = 1`), 28 halfwords are patched.
* The highest cost entry drops from 100 to 80 points. At a 6400-point threshold, continuous HSS burst limit increases from 64 to 80 shots (+25%).
* Across all other entries, points are reduced by 20% to 41%.
* **Burst Throttle (Tier X+):** In stock firmware and Tiers S/R/X/R+, a secondary accumulator (`[+0x16]`) triggers a charge delay lock (`0x2000004A = 5`) after 3000 points (~38 full-power shots in standard mode, ~30 in HSS). In **Tier X+ (`.05`)**, this branch is converted to an unconditional skip (`blo` → `b`), completely eliminating the 38-shot mid-burst throttle and permitting clean, continuous firing up to the 80-shot main threshold.

---

### 3.2 Godox AD200Pro II
*Chassis: Modular pocket strobe. Passive main body with internal heatsink; the `H200 II` fresnel head has a built-in cooling fan (confirmed on hardware 2026-10-10). No fan control routine has been identified in the body firmware yet (⚠️), so it's unknown whether the body or the head drives the fan. Flashing via Godox G3 and LCD version display confirmed on hardware (2026-10-10); functional endurance testing pending.*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | *Not available* | — | The fan lives in the `H200 II` head; no body-side control has been found to force. Possible later if one is identified. | — |
| **Tier R (Recovery)** | `AD200ProII_V1.05.02_recovery.bin` | `V1.05.02` | 2× drain: Heads {0, 1} [H200] `125` → `250`, Heads {2, 3, 4} [H200R / H200J / R200] `100` → `200` (`0x080123CA`–`D8`) | ✅ Code verified (passive body heatsink) |
| **Tier X (Super)** | `AD200ProII_V1.05.03_super.bin` | `V1.05.03` | 2× drain + HSS tables C & D lowered ~20% (33 → 40 shots at 185, 50 → 62 shots at 120) | 🔶 Code verified (HSS 100-pulse tables; optical train unverified) |

---

### 3.3 Godox V100N
*Chassis: On-camera round-head speedlite (⚠️ absence of evidence: no fan driver code in firmware). Flashing via Godox G3 and LCD version display confirmed on hardware (2026-10-10); functional endurance testing pending.*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | *Not available* | — | Fanless hardware. | — |
| **Tier R (Recovery)** | `V100N_V1.04.02_recovery.bin` | `V1.04.02` | 2× drain: `50` → `100` on both accumulators (`0x0800F498`–`B2`) | ✅ Code verified (fanless body) |
| **Tier X (Super)** | `V100N_V1.04.03_super.bin` | `V1.04.03` | 2× drain + ALT (HSS) table lowered 20% across all 11 zoom rows (60 → 75 shots at 100) | 🔶 Code verified (HSS 80-pulse table; optical train unverified) |

---

### 3.4 Godox iT30Pro (Nikon, iT30ProN)
*Chassis: Mini on-camera speedlite (⚠️ absence of evidence: no fan driver code in firmware). The image ends in an MD5 footer, which the patcher recomputes. Flashing via Godox G3 and LCD version display confirmed on hardware (2026-10-10); functional endurance testing pending. See [`it30ProN/README.md`](it30ProN/README.md).*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | *Not available* | — | Fanless hardware. | — |
| **Tier R (Recovery)** | `iT30ProN_V1.02.02_recovery.bin` | `V1.02.02` | 2× drain: `80` → `160` on both accumulators (`0x080141CC`–`E6`) | ✅ Code verified (fanless body) |
| **Tier X (Super)** | `iT30ProN_V1.02.03_super.bin` | `V1.02.03` | 2× drain + multi-pulse table `0x0804FFAC` lowered 20% across all 11 rows (40 → 50 shots at column 21) | 🔶 Code verified (80-pulse table; optical train unverified) |

---

### 3.5 Godox AD100Pro II
*Chassis: Ultra-compact round-head pocket strobe with built-in active cooling fan (GPIOC Pin 4 driven via `fn_080100a2`, controlled by `fn_08014370`; stock: on above 1200 points or below 271 raw NTC counts), single raw-ADC NTC (`fn_08014234`: < 114.59 forces cooldown). **Tier R (`1.07.02`) flashed via G3; continuous fan and version display (Device Info + settings menu) confirmed on hardware (2026-10-11)**; functional endurance testing pending. See [`AD100ProII/README.md`](AD100ProII/README.md).*

| Profile | Build File | Version Display | Modifications | Status |
|---|---|---|---|---|
| **Tier S (Studio)** | `AD100ProII_V1.07.01_studio.bin` | `1.07.01` | Continuous Active Fan branch (`0x080143A2`: `29 78` → `24 E0`, `b #0x80143ee`) | ✅ Code verified |
| **Tier R (Recovery)** | `AD100ProII_V1.07.02_recovery.bin` | `1.07.02` | Continuous Fan + 2× drain: Primary `25` → `50` (`0x5224`/`28`), Secondary `30` → `60` (`0x5278`/`7C`) | ✅ Flashed & continuous fan confirmed on hardware (2026-10-11) |
| **Tier X (Super)** | `AD100ProII_V1.07.03_super.bin` | `1.07.03` | Continuous Fan + 2× drain + Table Set 2 (HSS `0x26F48`) lowered ~20% across all 11 rows (60 → 75 shots at 1/1) | 🔶 Code verified (table-2 flag `0x20000035` setter not located; HSS meaning unconfirmed) |

---

## 4. Summary of Verification & Limits

1. **Continuous Bursts on AD600Pro II:**
   Every flash pop resets the idle timer to 1200 (`0x0801357C`) outside cooldown. The drain only fires after 50 timer steps without a flash. In Tier S and Tier R, single-burst capacity is identical to stock OEM firmware.
2. **Exact Drain Timing (0.100 s / step):**
   Across all three models, timer steps execute at **0.100 s (100 ms)** nominal (derived from hardware timer ISRs with dual-stage prescalers, based on internal RC oscillators ±1%; GD32F4 IRC16M at 240 MHz with TIMERSEL set on V100N). The 50-step drain interval is **5.000 s** nominal. Tier R doubles the points drained per 5.0 s interval.
3. **Repeated Bursts and Pauses:**
   Tier R cuts accumulator drain time in half (e.g. 16.0 pts/s vs 8.0 pts/s on AD600; with idle drain ~1.86× faster). On the AD600Pro II, continuous Level 2 fan operation helps cool the heatsink while the strobe is paused. On the AD200Pro II (except for the fan in the `H200 II` fresnel head) and the V100N, passive cooling means operators should allow adequate physical pause time between extended bursts.
4. **Physical Protection (Error E2 & Sensors):**
   Physical hardware thermal protections remain active across all models and tiers:
   - **AD600Pro II:** Dual NTC thermistors compare against raw ADC counts: NTC B dropping below 49.69 raw ADC trips Error E2; either NTC dropping below 132 raw ADC trips a 9.0 s forced cooldown; raw ADC < 271 / < 356 engage fan stages.
   - **AD200Pro II:** ADC1 IN2 raw float threshold (< 541.42 for 101 calls sets `0x20000124`; counter sets `0x2000005E`).
   - **V100N:** Real NTC thermistor path on ADC0 DMA average (`0x200004B6`) trips forced cooldown below 98.98 raw ADC (`fn_0800D544`). In software, secondary accumulator drives hard charge inhibit of 0–1.5 s via `fn_0800E52C` (charger-off GPIO pin) under heavy bursts until 120 s without flashes.
   However, thermistors react over seconds, not milliseconds, so they do not replace the algorithmic protection during fast continuous bursts.
