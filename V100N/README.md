# Godox V100N (Tier 2)

| Item | Value |
|---|---|
| OEM image | `V100N_V1.04.bin` (1,001,676 bytes), SHA-256 `18e3581c601cc7c15e81bbbe951b8b336e133de822f99450f57f116ffab37ee6` |
| Custom builds | `V100N_V1.04.02_recovery.bin` (Tier R), `V100N_V1.04.03_super.bin` (Tier X) — **flashing & version display confirmed on hardware** (2026-10-10) |
| Patcher | [`patch.py`](patch.py) (version scheme: [root README §1](../README.md#1-firmware-profiles--version-scheme)) |
| Technical classification | [`../TIERED_RATINGS.md`](../TIERED_RATINGS.md) |

Status marks: ✅ verified in code · 🔶 partial · ⚠️ unverified ([legend](../FINDINGS.md#status-legend)). File offset = address − `0x08008000`.

## Heat counter: adding points (`fn_0800EFBC`)

Base `r3 = 0x20000594`. Primary accumulator = halfword `[+8]`, secondary = `[+0x10]`.

| Claim | Status | Evidence |
|---|---|---|
| Column (index 0–21) comes from power via `fn_0800EC4C`. `fn_0800ec4c` evaluates 21 comparisons (70, 67, … 3) returning 0 to 21. Power byte $P < 3$ ($P=0$ = 1/1) returns top column 21. UI formatter at `fn_08011670` renders 1/1 to 1/256 (capped at 80). When mode bits of `0x200004D3` = 0, column comes from `0x2000055B` thresholds. Called by 10 callers across binary. | ✅ | `0x0800EC4C`–`0x0800ECEC`, `0x08011670`–`0x08011770` |
| Row (0–10) = (`0x200004DA` & 0xF) + 1, forced to 5 if > 10, or 0 when `0x200004DE` = 1 | ✅ | `0x0800EFC0`–`0x0800EFDA` |
| What the row means: **Zoom Head Focal Length Position** | ✅ | Table `0x08051694` contains 11 focal lengths `[20, 24, 28, 35, 50, 70, 80, 105, 135, 200, 200]`. Since row = index + 1, **Row 0 is the special `0x200004DE == 1` flag** (wide diffuser panel / bounce position), and **Rows 1–10 map to focal lengths `20, 24, 28, 35, 50, 70, 80, 105, 135, 200` mm**. (Table `0x080516A0` is a charge-control table, not motor steps). |
| Tables are 11 rows × 22 halfwords (44 bytes per row). Row address = base + row × 44. | ✅ | `0x0800F166`–`0x0800F176` |
| When not in cooldown (`0x2000051E` = 0): idle timer `[+6]` = **3000** on every flash, then points are added to `[+8]` (flashes during cooldown do NOT reset the idle timer) | ✅ | `0x0800F14C`, `0x0800F17E` |
| **Primary cooldown threshold: 6000** (`0x1770`) | ✅ | `0x0800F1D4`–`0x0800F1DA` |
| At the threshold: cooldown counter `[+0]` = 10, `0x2000051D` = 1, `[+0xA]` = 3000, `0x2000051E` = 1 | ✅ | `0x0800F1DC`–`0x0800F1EE` |
| Flashing during cooldown adds 5 to `[+1]` (capped at 50), then caps it per column (10/20/30/50) | ✅ | `0x0800F100`–`0x0800F12A`, `0x0800F222`–`0x0800F256` |
| **Secondary accumulator `[+0x10]`:** fed from same tables, timer `[+0xE]` = 1200, **threshold 3000**. Sets `[+4]` = 1 and counter `[+2]` (`0x20000596`) to 0–15 delay steps. | ✅ | Enforced by charger control `fn_0800E52C` (`0x0800E5B6` charger-off GPIO) as a per-flash **hard charge inhibit of 0–1.5 s** until **120 s without flashes**. |
| In row 3 (28 mm) at column > 15, with bit 2 of `[0x20000034+3]` set, the secondary accumulator adds 1.75 × the row-3 value | ✅ | `0x0800F2A4`–`0x0800F2DA` |

### Table selection

| Flag `0x2000051F` | Table | File offset |
|---|---|---|
| 0 | **NORM** `0x0805174C` | `0x4974C` |
| 1 | **ALT (HSS)** `0x08051930` | `0x49930` |

✅ `0x0800F148`–`0x0800F196`. Both accumulators use the same selection.

### What sets flag `0x2000051F`

| Writer | Value | Context | Status |
|---|---|---|---|
| `0x0800A2E6`, `0x0800A8DA`, `0x0801F808` | 1 | Right after an 80-pass pulse loop (`cmp #0x50` calling `fn_08013984`). Sets timeout `0x200005A0` (= `[+0xC]`) = 10 (decremented in 5 ms ISR ticks ~50 ms). | 🔶 Code verified (HSS 80-pulse sequence; optical train unverified) |
| `0x0801F9A0` | 0 | Single-pulse path, right before calling `fn_0800EFBC` | ✅ |
| `0x0800F492` (drain routine) | 0 | When the `[+0xC]` timeout reaches 0 | ✅ |

This is the same pattern as the AD600Pro II and AD200Pro II: a multi-pulse train sets the flag, and single flashes clear it. 🔶 Physical optical train unverified on hardware.

### Table values (points per flash, column 0 → 21)

**NORM (`0x0805174C`):** columns 0–14 are the same in every row: `1,1,1,1,1,1, 2,2,2, 5, 10, 15, 20,20,20`. Columns 15–21:

| Rows | Columns 15–21 | Top entry | Shots from empty to 6000 at column 21 |
|---|---|---|---|
| 0–3 | `28, 35, 42, 57, 71, 78, 86` | 86 | **70** |
| 4 | `26, 33, 40, 53, 66, 73, 80` | 80 | **75** |
| 5 | `25, 31, 37, 50, 62, 68, 75` | 75 | **80** |
| 6 | `22, 28, 33, 45, 56, 61, 67` | 67 | **90** |
| 7–10 | `20, 25, 30, 40, 50, 55, 60` | 60 | **100** |

**ALT / HSS (`0x08051930`):** all 11 rows are identical: `60×16, 80×3, 100×3`. Top entry 100 → **60 shots** to 6000. Columns 0–15 → 100 shots.

Secondary accumulator (threshold 3000) at column 21: NORM row 0 → 35 shots, ALT → 30 shots.

Shot counts assume a continuous burst (no drain, see below). ✅ Verified: column 21 corresponds to 1/1 power via `fn_0800ec4c` ($P < 3$ returns 21), and the cooldown threshold check (`0x0800f1d8`) uses `cmp` + `blo` ($\ge 6000$), confirming exact integer shot counts.

## Drain (`fn_0800F3F4`)

## Drain (`fn_0800F3F4`)

| Claim | Status | Evidence |
|---|---|---|
| Hardware Timer Base: TIM5 IRQ 50 (`fn_0801E520`) runs at 1.0 ms / 5 = 5.0 ms task tick | ✅ | GD32F450/470 MCU: IRC16M → PLL M16 N480 P2 = 240 MHz, APB1 /4, TIMERSEL bit set (`0x0804382A`) so CK_TIMER = 240 MHz; TIM5 PSC 239 / CAR 999 = 1.0 ms |
| Task execution gate | ✅ | Gated while bits 2 and 3 of `[0x20000034]` are set |
| Prescaler: divides 5.0 ms ticks by 20 to establish a 100 ms step tick | ✅ | `0x0800F3FA`–`0x0800F406` counts to `0x14` (20) × 5.0 ms = **0.100 s (100 ms) nominal** |
| **Nominal time per timer step = 0.100 seconds (100 ms)** | ✅ | $1.0\,\text{ms} \times 5 \times 20 = 100\,\text{ms}$ |
| Timer `[+6]`: when timer % 50 == 0 (**every 5.000 s nominal**), `[+8]` loses 50 (or is cleared if below 50) | ✅ | `0x0800F418`–`0x0800F4A0` (10.0 pts/s stock, 20.0 pts/s Tier R) |
| Timer `[+0xE]`: when timer % 50 == 0 (**every 5.000 s nominal**), `[+0x10]` loses 50 | ✅ | `0x0800F46A`–`0x0800F4B6` (10.0 pts/s stock, 20.0 pts/s Tier R) |
| Flashes taken outside cooldown reset `[+6]` to 3000 (`0x0800F14C`) | ✅ | `0x0800F14C` (3000 steps = **300.0 s / 5.0 min**) |

## Custom Firmware Profiles

### Version display

The version is printed by a variadic formatter from `V%d.%d%d` format strings, with the digits loaded as immediates (e.g. `0x415CC`, `0x415D6`). The patcher rewrites the format strings as fixed text, so the digits are ignored and the immediates stay stock:

| File offset | Stock | Patched (Tier R) | Where it shows |
|---|---|---|---|
| `0x416E8` | `Version: V%d.%d%d` | `Version: V1.04.02` | Device info (EN) |
| `0x4172C` | `固件版本: V%d.%d%d` | `固件版本: V1.04.02` | Device info (CN) |
| `0x3CD34` | `V%d.%d%d` | `V1.04.02` | Settings-menu readout (ADR at `0x08044BA4`, hardcoded digits) |

This ensures both the Device Info screen and the settings-menu readout display the patched version consistently.

### Tier R (`V100N_V1.04.02_recovery.bin`, version `V1.04.02`)
* Faster leaky-bucket drain: `50` → `100` on primary and secondary accumulators (`0x7498`, `0x749C`, `0x74AE`, `0x74B2`).
* Version text `V1.04.02` (see above).
* Single-burst limits remain 100% factory stock.

### Tier X (`V100N_V1.04.03_super.bin`, version `V1.04.03`)
* All Tier R drain changes included.
* Version text `V1.04.03`.
* ALT (HSS) table (`0x49930`, 11 rows × 22 halfwords): reduced 20% across all rows (100 → 80, 80 → 64, 60 → 48).
* Full-power continuous HSS shots expand from 60 → 75 (+25% burst capacity).

## Verified Hardware Architecture & Thermal Protection

- ⚠️ **Chassis Cooling:** Absence of evidence: no fan control peripheral code or GPIO drivers exist in firmware.
- ✅ **Dynamic Recycle Throttling:** Secondary accumulator (`[+0x10]`, threshold 3000) sets delay counter `[+2]` (`0x20000596`) to 0–15 delay steps. Charger control `fn_0800E52C` (`0x0800E5B6` charger-off GPIO bit 1 of GPIOH OCTL) enforces a per-flash **hard charge inhibit of 0–1.5 s** until **120 s without flashes**. `fn_0800AECC` only suppresses the "ready" notification.
- ✅ **Software Overheat & Cooldown Semantics:** `0x2000051D` is a 1–5 s post-flash charge lockout, cleared when `[+0]` reaches 0 or by 300 s expiry (not cleared by draining). The red thermometer icon follows `0x2000051E` (300 s cooldown mode), not `0x51D`.
- ✅ **Hardware NTC Thermistor Protection:** Real NTC thermistor path sampled via ADC0 DMA average at `0x200004B6` by `fn_08022F30` (> 970 = open, < 20 = short). Raw ADC < 98.98 for > 100 samples forces a cooldown trip (`fn_0800D544`), recovering at ≥ 176.3.
