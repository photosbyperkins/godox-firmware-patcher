# Godox AD200Pro II (Tier 2)

| Item | Value |
|---|---|
| OEM image | `AD200ProII_V1.05.bin` (387,248 bytes), SHA-256 `30783860ede87b4bd30678cf820a8f2f6e0d8bc505344d42de1d3561c69f400b` |
| Custom builds | `AD200ProII_V1.05.02_recovery.bin` (Tier R), `AD200ProII_V1.05.03_super.bin` (Tier X) — **flashing & version display confirmed on hardware** (2026-10-10) |
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
| **Cooldown threshold: 6000** (`0x1770`). It's **7500** (`0x1D4C`) when `0x20000095` in {6, 7} (H200 II / H200J II heads). | ✅ | `0x0801214A`, `0x080121C0` (bytes at `0x080121A8`–`0x080121BF` are code decoded by hand) |
| At the threshold: cooldown counter `[r5,#0xE]` = `[r5,#0x14]` (10, or 12 when `0x20000095` in {6, 7}), `0x20000049` = 1, `[r5,#0x10]` = 3000, `0x2000004A` = 1 | ✅ | `0x080120D6`–`0x080120DA`, `0x08012106`, `0x08012158`–`0x0801216A` |
| Flashing during cooldown adds 3 to the counter (capped at 100). It's then capped per index: 5/10/20/30/40 when the HSS flag = 0, 50/60/70/80/90 when it = 1. | ✅ | `0x0801205A`–`0x0801206C`, `0x080121C6`–`0x08012240` |
| A warning bit (bit 0 of `[0x200001F8+3]`) is set when index ≥ 19 and accumulator ≥ 3000 (≥ 1500 when `0x20000093` = 1) | ✅ | `0x0801212E`–`0x08012144`, `0x0801217E`–`0x0801218A` |
| When `0x20000095` in {6, 7} (H200 II / H200J II heads, `[0x20000096] = 1`), a secondary accumulator `[r5,#0x18]` is enabled (threshold 6000, timer `[r5,#0x16]` = 1800 steps [180 s], drained 165 per 50 steps = 16.5 pts/s) | ✅ | Traced to H200 II head heat tracking |

### Table selection

Two selectors pick one of four 25-entry halfword tables:

| | `0x20000093` ∉ {2, 3, 4} (Heads {0, 1}: H200 standard fresnel) | `0x20000093` ∈ {2, 3, 4} (Heads {2, 3, 4}: H200R / H200J / R200) |
|---|---|---|
| **HSS flag `0x2000004B` = 0** | **A** `0x0804149A` (file `0x3549A`) | **B** `0x080414CC` (file `0x354CC`) |
| **HSS flag `0x2000004B` = 1** | **C** `0x080414FE` (file `0x354FE`) | **D** `0x08041530` (file `0x35530`) |

✅ Selection logic: `0x080120DC`–`0x0801211A`, `0x08012174`–`0x0801217C`.
✅ `0x20000093` / `0x95` identify the attached flash head (sampled from ADC1 IN15 by `fn_0800F064`):
- Display routine `fn_08039E2C` maps raw codes: 1 = H200, 2 = H200R, 3 = H200J, 4 = R200/AD-S200, 5 = AD-L, 6 = H200 II, 7 = H200J II (6 remapped to 1 and 7 remapped to 3 into `0x93`).
- Power limit: 1/512 (`0x5A`) for heads {1, 2, 3}; 1/256 (`0x50`) for heads {4, 5}.
- Drain split: Heads {2, 3, 4} drain 100 points / 5.0 s (20.0 pts/s); other heads {0, 1} drain 125 points / 5.0 s (25.0 pts/s).

### What sets the HSS flag `0x2000004B`

| Writer | Value | Context | Status |
|---|---|---|---|
| `0x08013F2E` (`fn_08013C80`) | 1 | Right after a 100-pass pulse loop (`cmp r4,#0x64` at `0x08013F1C`). Sets timeout `[0x2000015C,#0x12]` = 3 (decremented every 5 ms ISR call ~15 ms). Gated by `0x2000001A` = 1 and bit 4 of `0x20000004`. | 🔶 Code verified (100-pulse sequence; optical train unverified) |
| `0x08019E92` | 1 | Same pattern (sets `#0x12` timeout = 3) before calling `fn_08012018` | 🔶 |
| `0x0801405E`, `0x080151AA`, `0x08015306`, `0x0801A002` | 0 | Single-pulse flash paths, right before calling `fn_08012018` | ✅ |
| `0x0801245C` (drain routine) | 0 | When the `#0x12` timeout reaches 0 | ✅ |

This is the same signature as the AD600Pro II's HSS path: a multi-pulse train sets the flag, and single flashes clear it. The longer cooldown caps when the flag = 1 also fit HSS. 🔶 Physical optical train unverified on hardware.

### Table values (points per flash, index 0 → 24)

| Table | Values | Top entry | Shots from empty to 6000 at top index |
|---|---|---|---|
| A (normal, heads {0, 1}) | `2,2,2, 3,3,3, 6,6,6, 12,12,12, 20,20,20, 30,30,30, 60,60,60, 80, 100, 120, 150` | 150 | **40** |
| B (normal, heads {2, 3, 4}) | `1,1,1, 2,2,2, 4,4,4, 8,8,8, 15,15,15, 23,23,23, 40,40,40, 50, 60, 75, 100` | 100 | **60** |
| C (HSS, heads {0, 1}) | `32×12, 40×3, 60×3, 80×3, 100×3, 185` | 185 | **33** |
| D (HSS, heads {2, 3, 4}) | `24×12, 30×3, 44×3, 60×3, 75×3, 120` | 120 | **50** |

Shot counts assume a continuous burst (no drain, see below) and the 6000 threshold. With the 7500 threshold (`0x20000095` in {6, 7}): A 50, B 75, C 41, D 63. ✅ Verified: the top index 24 corresponds to 1/1 power via `0x0804143E[0]`, and the threshold check (`0x08012154`) uses `cmp` + `blo` ($\ge 6000$), confirming exact integer shot counts.

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

### Tier R (`AD200ProII_V1.05.02_recovery.bin`, version `V1.05.02`)
* Faster leaky-bucket drain: Heads {0, 1} [H200] 125 → 250 (`0x63CA`, `0x63CE`), Heads {2, 3, 4} [H200R / H200J / R200] 100 → 200 (`0x63D4`, `0x63D8`).
* Version text `V1.05.02` (see above).
* Single-burst limits remain 100% factory stock.

### Tier X (`AD200ProII_V1.05.03_super.bin`, version `V1.05.03`)
* All Tier R drain changes included.
* Version text `V1.05.03`.
* HSS Table C (`0x354FE`, 25 halfwords): reduced ~20% (185 → 148, 100 → 80, 80 → 64, 60 → 48, 40 → 32, 32 → 25).
* HSS Table D (`0x35530`, 25 halfwords): reduced ~20% (120 → 96, 75 → 60, 60 → 48, 44 → 35, 30 → 24, 24 → 19).
* Full-power continuous HSS shots expand from 33 → 40 (Table C) and 50 → 62 (Table D).

## Verified Hardware Architecture & Thermal Protection

- ✅ **Head fan (hardware):** The fresnel head (`H200 II`, head code 6) has a built-in cooling fan, confirmed on hardware by the owner (2026-10-10). The body itself has no fan.
- ⚠️ **Fan control path:** No routine that switches or modulates this fan has been identified in the body firmware yet. It's open whether the body drives it through the head connector's extra contacts or the head regulates it on its own. If the body drives it, a Tier S (forced fan) build would be possible for this head. Note that the firmware already treats the `H200 II` / `H200J II` heads differently: 7500-point cooldown threshold and a secondary accumulator (see above). The fan may be part of the reason, but that link is unverified.
- 🔶 **Hardware Overheat Sensor:** ADC1 IN2 (`0x200000A4`) is sampled, converted to float, and compared against `541.42` (`0x44075AE1`). When reading is below 541.42 for 101 debounce calls, sets `[0x20000124] = 1`, and after 12,000 cycles (~60 s) sets `[0x2000005E] = 1` (`0x58` is set separately on median < 688.16 ×10 or boot < 695.75; both clear > 748.88). Charge/trigger gate readers at `0x0800D5E8`/`0x0800F84E` and thermometer icon display are unverified in code (⚠️). Physical sensor type on ADC1 IN2 is unknown.
- ✅ The temperature warning string "The temperature is\ntoo high to adjust." is at `0x0803C678`.
