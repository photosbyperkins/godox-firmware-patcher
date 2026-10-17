# Godox V100N

100 Ws round-head on-camera speedlite for Nikon with a motorized zoom. Fanless.

| | |
|---|---|
| OEM image | `V100N_V1.04.bin` · 1,001,676 bytes · SHA-256 `18e3581c601cc7c15e81bbbe951b8b336e133de822f99450f57f116ffab37ee6` |
| Platform | GD32F450/470, IRC16M → PLL (M16 N480 P2) 240 MHz, APB1 ÷4 with `TIMERSEL` set (`0x0804382A`) so timers run at 240 MHz · load `0x08008000` · SP `0x200AD678` · reset `0x0800829D` |
| File offset | address − `0x08008000` |
| Patcher | [`patch.py`](patch.py) → Tiers R, X (no fan, so no Tier S) |
| Disassembly | [`disasm/V100N_V1.04.asm`](disasm/V100N_V1.04.asm). About 80 % of the image is GUI and font data. Model string `" Model: V100 N"` at `0x416D7`. |
| Hardware | Flashed with G3; version display confirmed (2026-10-10). |

Status marks and notation: [architecture.md › Conventions](../../docs/architecture.md#conventions).

## Builds

| Tier | File | Version | SHA-256 |
|---|---|---|---|
| R Recovery | `V100N_V1.04.02_recovery.bin` | `V1.04.02` | `f3855ac2132eade59df334b4d1d406c38689d72ab4d91be9ba6c8cbb8ebba80d` |
| X Super | `V100N_V1.04.03_super.bin` | `V1.04.03` | `af32bb854c4a7551029874151a930210ef0cb1cb3a9ecc3acd4df72bdbba383c` |

- **R** — 2× drain on both counters (50 → 100 per 5 s). Single-burst limits stock. Once the secondary throttle has latched it still needs 120 s without a flash.
- **X** — R + HSS (ALT) table −20 % on all 11 rows: 1/1 HSS burst 60 → 75 shots, secondary throttle 30 → 38.

### Byte diff

| File offset | Address | Stock → patched | Effect | Tiers |
|---|---|---|---|---|
| `0x7498`, `0x749C` | `0x0800F498`, `0x0800F49C` | `32` → `64` | primary drain compare / subtract 50 → 100 | R, X |
| `0x74AE`, `0x74B2` | `0x0800F4AE`, `0x0800F4B2` | `32` → `64` | secondary drain compare / subtract 50 → 100 | R, X |
| `0x49930`–`0x49B13` | `0x08051930` | 11 × 22 halfwords | ALT (HSS) table | X |
| `0x416E8` | `0x080496E8` | `Version: V%d.%d%d` → `Version: V1.04.TT` | Device Info (EN), ADR `0x080495DC` | all |
| `0x4172C` | `0x0804972C` | `固件版本: V%d.%d%d` → `固件版本: V1.04.TT` | Device Info (CN), ADR `0x080496B2` | all |
| `0x3CD34` | `0x08044D34` | `V%d.%d%d` → `V1.04.TT` | Settings-menu readout, ADR `0x08044BA4` | all |

As on the AD200Pro II, the version digits are immediates passed to a formatter; the format strings are rewritten as fixed text and the code stays stock. Bytes changed: R 25, X 267.

## Heat counter

### Add (`fn_0800EFBC`, 10 callers; `r3 = 0x20000594`)

| Step | Evidence |
|---|---|
| Column 0–21 from `fn_0800EC4C` (called at `0x0800F0DA`): 21 compares (70, 67, … 3); `P < 3` (1/1) → 21. UI formatter `fn_08011670` shows 1/1–1/256. TTL (mode bits of `0x200004D3` = 0): thresholds on `0x2000055B` (0–100). | `0x0800EC4C`–`0x0800ECEC`, `0x08011670`–`0x08011770` |
| Row 0–10 = (`0x200004DA` & 0xF) + 1, forced to 5 if > 10, or 0 when `0x200004DE = 1`. | `0x0800EFC0`–`0x0800EFDA` |
| Row meaning: zoom position. Table `0x08051694` lists `20, 24, 28, 35, 50, 70, 80, 105, 135, 200, 200` mm; since row = index + 1, rows 1–10 are 20–200 mm and row 0 is the `0x200004DE` special case (wide panel / bounce). `0x0805169E` is a charge-duration table, not motor steps. | `0x08051694` |
| Row address = base + row × 44. | `0x0800F166`–`0x0800F176` |
| Outside cooldown (`0x2000051E = 0`): idle timer `[+6]` = 3000 (300 s), then add to `[+8]`. | `0x0800F14C`, `0x0800F17E` |
| At `≥ 6000` (`0x1770`): hold `[+0] = 10`, `0x2000051D = 1`, window `[+0xA]` = 3000, `0x2000051E = 1`. | `0x0800F1D4`–`0x0800F1EE` |
| During cooldown: +5 per flash to `[+1]` (cap 50), then capped per column at 10/20/30/50. | `0x0800F100`–`0x0800F12A`, `0x0800F222`–`0x0800F256` |
| **Secondary** `[+0x10]`: fed while `[+4] = 0`; timer `[+0xE]` = 1200 (120 s); at `≥ 3000` (`0x0800F2FC`) latch `[+4] = 1` and delay `[+2]` (`0x20000596`) = 5–15 steps. Latched flashes branch to `0x0800F262` (skip `[+0x10]`), raise `[+2]` up to 15 and reload the timer. | `0x0800F262`, `0x0800F2FC` |
| Rapid-recycle surcharge: in row 3 (28 mm), column > 15, with bit 2 of `0x20000037` set, the secondary adds 1.75 × the cost. That bit is set in `fn_0800E52C` when the capacitor recharges in < 75 % of the expected time from `0x0805169E` (back-to-back flashes). | `0x0800F2A4`–`0x0800F2DA`, `0x0800E740`–`0x0800E77E` |

`0x2000051D` is a 1–5 s post-flash charge lockout, cleared when `[+0]` reaches 0 or when the window expires. The red thermometer icon follows `0x2000051E` (the 300 s cooldown), not `0x2000051D`.

### Table selection

| Flag `0x2000051F` | Table | File offset |
|---|---|---|
| 0 | NORM `0x0805174C` | `0x4974C` |
| 1 | ALT (HSS) `0x08051930` | `0x49930` |

Both accumulators use the same selection (`0x0800F148`–`0x0800F196`).

### Tables (points per flash, column 0 → 21)

**NORM:** columns 0–14 are `1,1,1,1,1,1, 2,2,2, 5, 10, 15, 20,20,20` in every row. Columns 15–21:

| Rows | Columns 15–21 | Column 21 | Shots to 6000 |
|---|---|---|---|
| 0–3 (special, 20–28 mm) | `28, 35, 42, 57, 71, 78, 86` | 86 | 70 |
| 4 (35 mm) | `26, 33, 40, 53, 66, 73, 80` | 80 | 75 |
| 5 (50 mm) | `25, 31, 37, 50, 62, 68, 75` | 75 | 80 |
| 6 (70 mm) | `22, 28, 33, 45, 56, 61, 67` | 67 | 90 |
| 7–10 (80–200 mm) | `20, 25, 30, 40, 50, 55, 60` | 60 | 100 |

**ALT (HSS):** all 11 rows identical.

| | Row values | Column 21 | Shots to 6000 / 3000 |
|---|---|---|---|
| Stock | `60×16, 80×3, 100×3` | 100 | 60 / 30 |
| Tier X | `48×16, 64×3, 80×3` | 80 | 75 / 38 |

Secondary throttle at column 21, NORM row 0: 35 shots.

### HSS flag `0x2000051F`

| Writer | Value | Context |
|---|---|---|
| `0x0800A2E6`, `0x0800A8DA`, `0x0801F808` | 1 | After an 80-pulse loop (`cmp #0x50`, calling `fn_08013984`), gated by bit 4 of `0x200004D3` (set from the UI HSS sync mode `[0x200003DC+4] = 1` in `fn_0800F504` at `0x0800F612`). Sets timeout `[+0xC]` (`0x200005A0`) = 10 (~50 ms). |
| `0x0801F9A0` | 0 | Single-pulse path, before calling `fn_0800EFBC`. |
| `0x0800F492` (drain) | 0 | When `[+0xC]` reaches 0. |

🔶 Light output not scope-verified.

### Drain (`fn_0800F3F4`)

| Action | Evidence |
|---|---|
| Step = 100 ms: TIM5 (PSC 239, CAR 999 at 240 MHz) = 1 ms ÷ 5 ÷ 20. Runs while bits 2 and 3 of `[0x20000034]` are set. | `fn_0801E520`, `0x0800F3FA`–`0x0800F406` |
| Primary: every 50 steps `[+8]` −50 (clear if < 50); idle timer at 0 clears it. | `0x0800F418`–`0x0800F4A0` |
| Secondary: every 50 steps `[+0x10]` −50. Draining does **not** clear the latch; `[+4]` and `[+2]` clear when `[+0xE]` reaches 0 (120 s without a flash, `0x0800F4A4`), or in sleep if `[+0x10] < 20` (`0x0801D820`). | `0x0800F46A`–`0x0800F4B8` |

## Thermal protection

- **Thermistor.** ADC0 DMA average `0x200004B6`, sampled by `fn_08022F30` (> 970 open, < 20 short). Below 98.98 for > 100 samples it forces a cooldown (`fn_0800D544`); recovers at ≥ 176.3.
- **Secondary throttle enforcement.** While latched, charger control `fn_0800E52C` drives the charger-off GPIO (bit 1 of GPIOH OCTL, `0x0800E5B6`) for 0.5–1.5 s after each flash. `fn_0800AECC` only suppresses the "ready" notification.
- **Fan.** ⚠️ No fan driver or fan GPIO found (absence of evidence).
