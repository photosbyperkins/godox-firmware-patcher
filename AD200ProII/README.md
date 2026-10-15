# Godox AD200Pro II (Tier 2)

| Item | Value |
|---|---|
| OEM image | `AD200ProII_V1.05.bin` (387,248 bytes), SHA-256 `30783860ede87b4bd30678cf820a8f2f6e0d8bc505344d42de1d3561c69f400b` |
| Custom builds | `AD200ProII_V1.05.01_studio.bin` (Tier S), `AD200ProII_V1.05.02_recovery.bin` (Tier R), `AD200ProII_V1.05.03_super.bin` (Tier X) — **flashing, version display & continuous H200 II fan confirmed on hardware** (2026-10-14) |
| Patcher | [`patch.py`](patch.py) (version scheme: [root README §1](../README.md#1-firmware-profiles--version-scheme)) |
| Technical classification | [`../TIERED_RATINGS.md`](../TIERED_RATINGS.md) |

Status marks: ✅ verified in code · 🔶 partial · ⚠️ unverified ([legend](../FINDINGS.md#status-legend)). File offset = address − `0x0800C000`.

## Heat counter: adding points (`fn_08012018`)

Base `r5 = 0x2000015C`. Accumulator = halfword `[r5,#0xC]`. The design matches the AD600Pro II's `fn_080134E4`.

| Claim | Status | Evidence |
|---|---|---|
| Table index = `map[power]`, map at `0x0804143E` (92 bytes, values 24 → 0). Power is `0x20000010` when the mode bits of `0x20000004` = 1, else `0x20000011`. When the mode bits = 0, the index comes from a byte at `0x2000015C` via thresholds 40/50/…/100 → 3, 6, … 24. | ✅ | `0x0801201C`–`0x080120D4` |
| Highest index is 24 (AD600Pro II: 27). `map[0]` = 24 represents 1/1 full power. UI formatter at `0x080148be`/`0x08014914` computes $(90 - P)/10$ and branches to denominator 1 (1/1) when $P = 0$. Power ranges 1/1 to 1/256 (standard), 1/512 (heads 1, 2, 3), or 1/128 (special modes). | ✅ | `0x080148be`–`0x08014938`, `0x080120d2` |
| When not in cooldown (`0x2000004A` = 0): idle timer `[r5,#0xA]` = **3000** on every flash, then points are added (flashes during cooldown do NOT reset the idle timer) | ✅ | `0x080120F0` |
| Accumulator clamped at 65000 | ✅ | `0x08012124`–`0x0801212C` |
| **Cooldown threshold: 6000** (`0x1770`). It's **7500** (`0x1D4C`) **only when `0x20000095 == 6` (`H200 II` fresnel head)** (`cmp r4, #6` at `0x08012146`). `H200J II` (`7`) uses the standard **6000** threshold. | ✅ | `0x08012146`–`0x08012154`, `0x080121C0` (bytes at `0x080121A8`–`0x080121BF` are code decoded by hand) |
| At the threshold: cooldown counter `[r5,#0xE]` = `[r5,#0x14]` (10, or 12 when `0x20000095 == 6` [`H200 II`]), `0x20000049` = 1, `[r5,#0x10]` = 3000, `0x2000004A` = 1 | ✅ | `0x080120D6`–`0x080120DA`, `0x08012106`, `0x08012158`–`0x0801216A` |
| Flashing during cooldown adds 3 to the counter (capped at 100). It's then capped per index: 5/10/20/30/40 when the HSS flag = 0, 50/60/70/80/90 when it = 1. | ✅ | `0x0801205A`–`0x0801206C`, `0x080121C6`–`0x08012240` |
| A warning bit (bit 0 of `[0x200001F8+3]`) is set when index ≥ 19 and accumulator ≥ 3000 (≥ 1500 when `0x20000093` = 1) | ✅ | `0x0801212E`–`0x08012144`, `0x0801217E`–`0x0801218A` |
| **Only when `0x20000095 == 6` (`H200 II` head, `cmp r4, #6` at `0x08012242`):** a secondary accumulator `[r5,#0x18]` is enabled (threshold **6000**, timer `[r5,#0x16]` = 1800 steps [180 s], drained **165 per 50 steps [5.0 s] = 33.0 pts/s** at `0x0801242E`–`0x08012432`, left stock in `patch.py`). Because `[r5,#0x18]` trips at 6000 (`0x08012288`) before the `H200 II` primary threshold of 7500, shots 41–50 (Normal) or 34–41 (stock HSS) incur a **0.5–1.7 s recycle delay** (`[r5,#2]`, cap 17) until 180 s without flashes. | ✅ | `0x08012242`–`0x08012304`, `0x08012412`–`0x0801243A` |

### Table selection

Two selectors pick one of four 25-entry halfword tables:

| | `0x20000093` ∉ {2, 3, 4} (Heads {0, 1}: H200 / H200 II fresnel) | `0x20000093` ∈ {2, 3, 4} (Heads {2, 3, 4}: H200R / H200J / H200J II / R200) |
|---|---|---|
| **HSS flag `0x2000004B` = 0** | **A** `0x0804149A` (file `0x3549A`) | **B** `0x080414CC` (file `0x354CC`) |
| **HSS flag `0x2000004B` = 1** | **C** `0x080414FE` (file `0x354FE`) | **D** `0x08041530` (file `0x35530`) |

✅ Selection logic: `0x080120DC`–`0x0801211A`, `0x08012174`–`0x0801217C`.
✅ `0x20000093` / `0x95` identify the attached flash head (sampled from ADC1 IN15 by `fn_0800F064`):
- Display routine `fn_08039E2C` maps raw codes: 1 = H200, 2 = H200R, 3 = H200J, 4 = R200/AD-S200, 5 = AD-L, 6 = H200 II, 7 = H200J II (6 remapped to 1 and 7 remapped to 3 into `0x93`, while `0x96 = 1` for {6, 7}).
- Power limit: 1/512 (`0x5A`) for heads {1, 2, 3}; 1/256 (`0x50`) for heads {4, 5}.
- Drain split: Heads {2, 3, 4} drain 100 points / 5.0 s (20.0 pts/s); other heads {0, 1} drain 125 points / 5.0 s (25.0 pts/s).

### What sets the HSS flag `0x2000004B`

| Writer | Value | Context | Status |
|---|---|---|---|
| `0x08013F2E` (`fn_08013C80`) | 1 | Right after a 100-pass pulse loop (`cmp r4,#0x64` at `0x08013F1C`). Sets timeout `[0x2000015C,#0x12]` = 3 (decremented every 5 ms ISR call ~15 ms). Gated by `0x2000001A == 0` (`0x2000001A = 1` is the single-pulse TEST/S1/S2 override at `0x0800DD2C`/`0x0800E0E0`/`0x0800EA70`) and bit 4 (`0x10`) of `0x20000004` (which renders the UI HSS icon `\xee\x98\xbc` at `0x08036754`). | ✅ Code verified end-to-end (🔶 physical optical train unverified on hardware) |
| `0x08019E92` (`fn_08019CDC`) | 1 | Wireless/remote 105-pulse HSS loop (`cmp r4,#0x69` at `0x08019E80`, when mode `0x20000020 == 0x1A`); sets `#0x12` timeout = 3 before calling `fn_08012018` | ✅ Code verified |
| `0x0801405E`, `0x080151AA`, `0x08015306`, `0x0801A002` | 0 | Single-pulse flash paths, right before calling `fn_08012018` | ✅ |
| `0x0801245C` (drain routine) | 0 | When the `#0x12` timeout reaches 0 | ✅ |

This is the same signature as the AD600Pro II's HSS path: a multi-pulse train sets the flag, and single flashes clear it. The longer cooldown caps when the flag = 1 also fit HSS. 🔶 Physical optical train unverified on hardware.

### Table values (points per flash, index 0 → 24)

| Table | Values | Top entry | Shots from empty to 6000 at top index |
|---|---|---|---|
| A (normal, heads {0, 1}) | `2,2,2, 3,3,3, 6,6,6, 12,12,12, 20,20,20, 30,30,30, 60,60,60, 80, 100, 120, 150` | 150 | **40** (or **50** on `H200 II` at 7500, throttled from shot 41) |
| B (normal, heads {2, 3, 4}) | `1,1,1, 2,2,2, 4,4,4, 8,8,8, 15,15,15, 23,23,23, 40,40,40, 50, 60, 75, 100` | 100 | **60** |
| C (HSS, heads {0, 1}) | `32×12, 40×3, 60×3, 80×3, 100×3, 185` | 185 | **33** (or **41** on `H200 II` at 7500, throttled from shot 34) |
| D (HSS, heads {2, 3, 4}) | `24×12, 30×3, 44×3, 60×3, 75×3, 120` | 120 | **50** |

Shot counts assume a continuous burst (no drain, see below) and the 6000 threshold. With the 7500 threshold (`0x20000095 == 6`, `H200 II` only, which uses Tables A and C): **A 50** (secondary throttle `[r5,#0x18]` active on shots 41–50) and **C 41** (secondary throttle active on shots 34–41). (`H200J II` [`0x20000095 == 7`] uses the 6000 threshold with Tables B and D: **B 60, D 50**). ✅ Verified: the top index 24 corresponds to 1/1 power via `0x0804143E[0]`, and the threshold check (`0x08012154`) uses `cmp` + `blo` ($\ge 6000$ or $\ge 7500$), confirming exact integer shot counts.

The table at `0x08041562` (values 23500 → 13440) is **not** a heat table. It sits next to these tables but isn't referenced by `fn_08012018`.

## Drain (`fn_08012370`)

| Claim | Status | Evidence |
|---|---|---|
| SysTick task timer base: 1.0 ms SysTick ISR (`fn_080193B8`) / 5 = 5.0 ms task tick | ✅ | LOAD computed from `SystemCoreClock` = 168 MHz (HSI 16 MHz PLL ±1%); calls `fn_08023CF8` → `fn_08012370` |
| Task execution gate | ✅ | Gated by bits 0 and 2 of `[0x200001F8]` |
| Prescaler: divides 5.0 ms ticks by 20 to establish a 100 ms step tick | ✅ | `0x08012376`–`0x08012382` counts to `0x14` (20) × 5.0 ms = **0.100 s (100 ms) nominal** |
| **Nominal time per timer step = 0.100 seconds (100 ms)** | ✅ | $1.0\,\text{ms} \times 5 \times 20 = 100\,\text{ms}$ |
| Idle timer `[+0xA]`: decremented each pass; at 0 the accumulator is cleared | ✅ | `0x08012384`–`0x080123A2` (3000 steps = **300.0 s / 5.0 min**) |
| When timer % 50 == 0 (**every 5.000 s nominal**): subtract 125 for heads {0, 1} (**25.0 pts/s**), or 100 for heads {2, 3, 4} (**20.0 pts/s**) | ✅ | `0x080123B6`–`0x080123D8` |
| Flashes taken outside cooldown reset idle timer to 3000 (`0x080120F0`) | ✅ | `0x080120F0` |

## Custom Firmware Profiles

### Version display

The version is printed by a variadic formatter from `V%d.%d%d` format strings, with the digits loaded as immediates (e.g. `0x2ECC8`, `0x2ECD2`). The patcher rewrites the format strings as fixed text, so the digits are ignored and the immediates stay stock:

| File offset | Stock | Patched (Tier R) | Where it shows |
|---|---|---|---|
| `0x2EDCC` | `Version: V%d.%d%d` | `Version: V1.05.02` | Device info (EN) |
| `0x2EE14` | `版本: V%d.%d%d` | `版本: V1.05.02` | Device info (CN) |
| `0x2C4F8` | `V%d.%d%d` | `V1.05.02` | Settings-menu readout (ADR at `0x080383E8`, hardcoded digits) |

This ensures both the Device Info screen and the settings-menu readout display the patched version consistently.

### Tier S: Studio (`AD200ProII_V1.05.01_studio.bin`, version `V1.05.01`)
* Continuous `H200 II` cooling fan: File offset `0x178BA`: `28 78` → `01 20` (`ldrb r0, [r5]` → `movs r0, #1`); `0x1791A`: `2c 70` → `2f 70` (`strb r4, [r5]` → `strb r7, [r5]`). When `H200 II` (head code 6) is attached, body MCU transmits I2C slave `0x5C` Register `0x01` value `1` (Fan ON) unconditionally. For all non-fan heads, head detection branches to exit cleanly.
* Single-burst and leaky-bucket limits remain 100% factory stock.
* Version text `V1.05.01` (see above).

### Tier R: Recovery (`AD200ProII_V1.05.02_recovery.bin`, version `V1.05.02`)
* Tier S continuous `H200 II` head fan patch included.
* Faster leaky-bucket drain: Heads {0, 1} [H200 / H200 II] 125 → 250 (`0x63CA`, `0x63CE`), Heads {2, 3, 4} [H200R / H200J / H200J II / R200] 100 → 200 (`0x63D4`, `0x63D8`). (`H200 II` secondary accumulator `[r5,#0x18]` drain of `165 / 5.0 s` is left stock).
* Version text `V1.05.02` (see above).
* Single-burst limits remain 100% factory stock.

### Tier X: Super (`AD200ProII_V1.05.03_super.bin`, version `V1.05.03`)
* All Tier R drain and fan changes included.
* Version text `V1.05.03`.
* HSS Table C (`0x354FE`, 25 halfwords): reduced ~20% (185 → 148, 100 → 80, 80 → 64, 60 → 48, 40 → 32, 32 → 25).
* HSS Table D (`0x35530`, 25 halfwords): reduced ~20% (120 → 96, 75 → 60, 60 → 48, 44 → 35, 30 → 24, 24 → 19).
* Full-power continuous HSS shots at the 6000 threshold expand from **33 → 41** (Table C: `40 × 148 = 5920 < 6000`, 41st shot hits `6068`; on `H200 II` at 7500 threshold, **41 → 51** with secondary throttle from shot 41) and **50 → 63** (Table D: `62 × 96 = 5952 < 6000`, 63rd shot hits `6048`).

## Verified Hardware Architecture & Thermal Protection

- ✅ **Head fan (hardware & body-side I2C control):** The fresnel head (`H200 II`, head code `0x20000095 == 6`) has a built-in cooling fan, confirmed on hardware by the owner (2026-10-10), while the body itself has no fan. Disassembly of `fn_080237B0` (`0x08023850`–`0x080238CC`) confirms the body MCU directly switches the `H200 II` head fan over bit-banged I2C (PB6=SCL, PB7=SDA, slave `0x5C`, **Register `0x01`** via `fn_08011F1E`, state stored in `[0x200001CC]`):
  - **Stock Fan ON (`1`):** when the head's digital NTC (`[0x200001E6]`, I2C Reg `0x06`) is in `151..941`, or modeling lamp brightness `[0x200001E8] > 60`, or shot-counter bit `0x40` of `[0x200001F9]` is set after 5 full-power shots (`0x0801218E`–`0x080121BE`).
  - **Stock Fan OFF (`0`):** when `[0x200001E6] > 1084` (and modeling lamp ≤ 60 and shot-counter bit 0).
  - **Custom Firmware Mod (`Tier S, R, X`):** Patches `0x178BA` (`28 78` → `01 20`, `movs r0, #1`) and `0x1791A` (`2c 70` → `2f 70`, `strb r7, [r5]`), ensuring Register `0x01` value `1` (Fan ON) is transmitted unconditionally on every I2C cycle when `H200 II` is attached. For all non-fan heads (`r0 != 6`), the code branches to exit cleanly. **Continuous fan operation on physical hardware confirmed by owner (2026-10-14).**
- ✅ **DFU Bootloader Resilience & Recovery:**
  - The on-chip DFU bootloader resides in protected internal flash (`0x08000000`–`0x0800BFFF`).
  - An accidental cross-model flash (e.g. flashing a 357 KB AD100Pro II image onto the 387 KB AD200Pro II) produces a non-boot state where the unit blinks its color group indicator and does not power on the LCD.
  - However, the bootloader survives completely intact. Re-connecting to Godox G3 and flashing the correct `AD200ProII_V1.05.02_recovery.bin` (or factory `AD200ProII_V1.05.bin`) restores the strobe to full operational health immediately, confirming high bootloader resilience against accidental bricking.
- ✅ **Hardware Overheat Sensors vs. Battery Voltage (`0x200000A4`):**
  - **Correction (`0x200000A4` is Battery Voltage, NOT NTC):** `fn_0800C8EC` (`0x200000A4 < 541.42` setting `[0x20000124] = 1` and `[0x2000005E] = 1`) is the **battery voltage monitor** (`fn_0800CD40` uses `0x200000A4` to draw the 4-bar battery icon at thresholds `770/732/695/655` and triggers low-battery power-off via `0x2000005E`).
  - **Analog Head NTC (`0x200000AE` in `fn_08015C78`):** For heads other than `H200 II` (`0x20000095 != 6`), `fn_08015C78` monitors ADC channel `0x200000AE`: `< 75` sets `[0x200001BA] = 5` (severe overheat) and calls `fn_0800E1E4` (forced cooldown); `< 132` calls `fn_0800E1E4` and sets `[0x200001EA] = 1`; recovers at `≥ 235` (`fn_0801233E`).
  - **`H200 II` Digital Head NTC (`[0x200001E6]` in `fn_080237B0`):** Read from I2C slave `0x5C` Reg `0x06`: `< 260` sets `[0x200001CF] = 5` (severe overheat) and calls `fn_0800E1E4`; `< 396` calls `fn_0800E1E4`; recovers at `≥ 816` (`fn_0801233E`).
  - **Charge/Trigger Gates & Thermometer UI:** `0x0800D5E8` (`fn_0800D5CC`), `0x0800F84E` (`fn_0800F840`), and `fn_08015B58` gate charging (`0x20000049`) and firing (`0x2000004A`, `0x20000058`, `0x20000124`); the UI (`0x08036A10`–`0x08036A94`) renders a solid red thermometer when `0x2000004A == 1` and a blinking thermometer when `[0x200001CF] == 5` or `[0x200001BA] == 5`.
- ✅ The temperature warning string `"The temperature is\ntoo high to adjust."` (`0x0803C678`) is displayed when attempting to turn on the modeling lamp while `[0x200001EA] == 1` (`0x08031FE8`).
