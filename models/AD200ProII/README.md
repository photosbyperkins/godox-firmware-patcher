# Godox AD200Pro II

200 Ws modular pocket strobe with interchangeable heads. The body is fanless; the H200 II fresnel head has its own fan, which the body controls over I2C.

| | |
|---|---|
| OEM image | `AD200ProII_V1.05.bin` · 387,248 bytes · SHA-256 `30783860ede87b4bd30678cf820a8f2f6e0d8bc505344d42de1d3561c69f400b` |
| Platform | STM32F4-class, HSI 16 MHz → 168 MHz · load `0x0800C000` · SP `0x1000F000` (stack in CCM RAM at `0x10000000`) · reset `0x0800C269` |
| File offset | address − `0x0800C000` |
| Patcher | [`patch.py`](patch.py) → Tiers S, R, X |
| Disassembly | [`disasm/AD200ProII_V1.05.asm`](disasm/AD200ProII_V1.05.asm) · model string `"Model: AD200ProII"` at `0x2EDB8` |
| Hardware | `V1.05.01` and `V1.05.02` flashed with G3; version display and continuous H200 II fan confirmed (2026-10-14). Tier X code-verified only. |

Status marks and notation: [architecture.md › Conventions](../../docs/architecture.md#conventions).

## Builds

| Tier | File | Version | SHA-256 |
|---|---|---|---|
| S Studio | `AD200ProII_V1.05.01_studio.bin` | `V1.05.01` | `c26d91f59f85217474ab1e1b828e17f5370646c48621036a937aaea1394e9292` |
| R Recovery | `AD200ProII_V1.05.02_recovery.bin` | `V1.05.02` | `716b0048a784891858047c433d83c191b0442f00421ff034a222cdddb2b80c86` |
| X Super | `AD200ProII_V1.05.03_super.bin` | `V1.05.03` | `f4aacd86f89d2de6ba4128b883f3e85b0c85aab3b1986e5378fc2722be86f1b3` |

- **S** — H200 II head fan always on. Limits stock.
- **R** — S + 2× drain: group A 125 → 250, group B 100 → 200 per 5 s. The H200 II secondary drain (165 per 5 s) is left stock.
- **X** — R + HSS tables C and D −20 %: 1/1 HSS burst 33 → 41 (A; 41 → 51 on H200 II) and 50 → 63 (B).

### Byte diff

| File offset | Address | Stock → patched | Effect | Tiers |
|---|---|---|---|---|
| `0x178BA` | `0x080238BA` | `28 78` → `01 20` | `ldrb r0,[r5]` → `movs r0,#1`: I2C fan command is always 1 | all |
| `0x1791A` | `0x0802391A` | `2C 70` → `2F 70` | `strb r4,[r5]` → `strb r7,[r5]`: fan state `[0x200001CC]` stays 1 | all |
| `0x63CA`, `0x63CE` | `0x080123CA`, `0x080123CE` | `7D` → `FA` | group A drain compare / subtract 125 → 250 | R, X |
| `0x63D4`, `0x63D8` | `0x080123D4`, `0x080123D8` | `64` → `C8` | group B drain compare / subtract 100 → 200 | R, X |
| `0x354FE`–`0x3552F` | `0x080414FE` | 25 halfwords | HSS table C | X |
| `0x35530`–`0x35561` | `0x08041530` | 25 halfwords | HSS table D | X |
| `0x2EDCC` | `0x0803ADCC` | `Version: V%d.%d%d` → `Version: V1.05.TT` | Device Info (EN), ADR `0x0803ACD8` | all |
| `0x2EE14` | `0x0803AE14` | `版本: V%d.%d%d` → `版本: V1.05.TT` | Device Info (CN), ADR `0x0803AD98` | all |
| `0x2C4F8` | `0x080384F8` | `V%d.%d%d` → `V1.05.TT` | Settings-menu readout, ADR `0x080383E8` | all |

The version digits are passed to a variadic formatter as immediates. Rewriting the format strings as fixed text makes the formatter ignore them, so the code stays stock. Bytes changed: S 24, R 28, X 78.

## Heads

`0x20000093` / `0x20000095` hold the attached head, sampled from ADC1 IN15 by `fn_0800F064`. `fn_08039E2C` names the raw codes:

| Code | Head | `0x93` | Group | Power limit |
|---|---|---|---|---|
| 1 | H200 | 1 | A | 1/512 |
| 2 | H200R | 2 | B | 1/512 |
| 3 | H200J | 3 | B | 1/512 |
| 4 | R200 / AD-S200 | 4 | B | 1/256 |
| 5 | AD-L | 5 | A | 1/256 |
| 6 | H200 II | → 1 | A | — |
| 7 | H200J II | → 3 | B | — |

`0x93` remaps 6 → 1 and 7 → 3, and `0x96 = 1` marks the II heads. `0x95` keeps the raw code: **`0x95 = 6` (H200 II only)** raises the primary threshold to 7500 and enables a secondary accumulator. The H200J II uses the standard 6000.

## Heat counter

### Add (`fn_08012018`, `r5 = 0x2000015C`, accumulator `[+0xC]`)

Same design as the AD600Pro II's `fn_080134E4`.

| Step | Evidence |
|---|---|
| Index = `0x0804143E[P]` (92 bytes, 24 → 0); `P` = `0x20000010` when the mode bits of `0x20000004` = 1, else `0x20000011`. TTL (mode bits 0): byte `0x2000015C` through thresholds 40/50/…/100 → 3, 6, … 24. `P = 0` → index 24 = 1/1 (formatter `0x080148BE`–`0x08014938` computes `(90 − P) / 10`). | `0x0801201C`–`0x080120D4` |
| Outside cooldown (`0x2000004A = 0`): idle timer `[+0xA]` = 3000 (300 s), then add. Accumulator clamped at 65000. | `0x080120F0`, `0x08012124`–`0x0801212C` |
| Threshold 6000 (`0x1770`); 7500 (`0x1D4C`) when `0x95 = 6` (`cmp r4,#6` at `0x08012146`). | `0x08012146`–`0x08012154` |
| Trip: hold `[+0xE]` = `[+0x14]` (10, or 12 on H200 II), `0x20000049 = 1` (charge inhibit), window `[+0x10]` = 3000, `0x2000004A = 1` (cooldown). | `0x080120D6`–`0x080120DA`, `0x08012106`, `0x08012158`–`0x0801216A` |
| During cooldown: +3 per flash, cap 100, then capped per index at 5/10/20/30/40 (HSS flag 0) or 50/60/70/80/90 (flag 1). | `0x0801205A`–`0x0801206C`, `0x080121C6`–`0x08012240` |
| Warning bit 0 of `[0x200001F8+3]` when index ≥ 19 and accumulator ≥ 3000 (≥ 1500 when `0x93 = 1`). | `0x0801212E`–`0x08012144`, `0x0801217E`–`0x0801218A` |
| **H200 II secondary** (`cmp r4,#6` at `0x08012242`): `[+0x18]`, threshold 6000 (`0x08012288`), timer `[+0x16]` = 1800 (180 s), drain −165 per 50 steps. Because it trips before the 7500 primary, shots 41–50 (normal) or 34–41 (HSS) get a 0.5–1.7 s recycle delay (`[+2]`, cap 17) until 180 s without a flash. | `0x08012242`–`0x08012304`, `0x08012412`–`0x0801243A` |

Bytes `0x080121A8`–`0x080121BF` are code that `disasm.py` leaves undecoded; they were decoded by hand.

### Table selection

| | Group A (`0x93` ∉ {2, 3, 4}) | Group B (`0x93` ∈ {2, 3, 4}) |
|---|---|---|
| HSS flag `0x2000004B` = 0 | **A** `0x0804149A` (file `0x3549A`) | **B** `0x080414CC` (file `0x354CC`) |
| HSS flag `0x2000004B` = 1 | **C** `0x080414FE` (file `0x354FE`) | **D** `0x08041530` (file `0x35530`) |

Selection logic: `0x080120DC`–`0x0801211A`, `0x08012174`–`0x0801217C`.

### Tables (points per flash, index 0 → 24)

| Table | Values | Index 24 | Shots at 1/1 (6000) |
|---|---|---|---|
| A | `2,2,2, 3,3,3, 6,6,6, 12,12,12, 20,20,20, 30,30,30, 60,60,60, 80, 100, 120, 150` | 150 | 40 (H200 II at 7500: 50) |
| B | `1,1,1, 2,2,2, 4,4,4, 8,8,8, 15,15,15, 23,23,23, 40,40,40, 50, 60, 75, 100` | 100 | 60 |
| C | `32×12, 40×3, 60×3, 80×3, 100×3, 185` | 185 | 33 (H200 II: 41) |
| C, Tier X | `25×12, 32×3, 48×3, 64×3, 80×3, 148` | 148 | 41 (H200 II: 51) |
| D | `24×12, 30×3, 44×3, 60×3, 75×3, 120` | 120 | 50 |
| D, Tier X | `19×12, 24×3, 35×3, 48×3, 60×3, 96` | 96 | 63 |

The table at `0x08041562` (23500 → 13440) sits next to these but is not read by `fn_08012018`; it is not a heat table.

### HSS flag `0x2000004B`

| Writer | Value | Context |
|---|---|---|
| `0x08013F2E` (`fn_08013C80`) | 1 | After a 100-pulse loop (`cmp r4,#0x64` at `0x08013F1C`), gated by bit 4 of `0x20000004` (the UI HSS icon, `0x08036754`) and `0x2000001A = 0` (`0x2000001A = 1` is the single-pulse TEST/S1/S2 override). Sets timeout `[+0x12] = 3` (~15 ms). |
| `0x08019E92` (`fn_08019CDC`) | 1 | Wireless 105-pulse loop (`cmp r4,#0x69` at `0x08019E80`, mode `0x20000020 = 0x1A`); same timeout. |
| `0x0801405E`, `0x080151AA`, `0x08015306`, `0x0801A002` | 0 | Single-pulse paths, before calling `fn_08012018`. |
| `0x0801245C` (drain) | 0 | When `[+0x12]` reaches 0. |

🔶 Light output not scope-verified.

### Drain (`fn_08012370`)

| Action | Evidence |
|---|---|
| Step = 100 ms: SysTick 1 ms ÷ 5 ÷ 20, gated by bits 0 and 2 of `[0x200001F8]`. | `0x08012376`–`0x08012382` |
| Idle timer `[+0xA]` at 0 (300 s): accumulator cleared. | `0x08012384`–`0x080123A2` |
| Every 50 steps (5.0 s): −125 for group A (25 pts/s), −100 for group B (20 pts/s). | `0x080123B6`–`0x080123D8` |
| H200 II secondary: −165 per 50 steps (33 pts/s). | `0x0801242E`–`0x08012432` |

## H200 II head fan and sensors (`fn_080237B0`)

The body talks to the H200 II over bit-banged I2C (PB6 = SCL, PB7 = SDA, slave `0x5C`): register `0x01` is the fan (written via `fn_08011F1E`, state in `[0x200001CC]`), register `0x06` is the head's digital NTC (`[0x200001E6]`).

| Stock fan logic | Condition | Evidence |
|---|---|---|
| On | NTC in 151–941, modelling lamp `[0x200001E8] > 60`, or bit `0x40` of `[0x200001F9]` (set after 5 full-power shots) | `0x08023850`–`0x080238CC`, `0x0801218E`–`0x080121BE` |
| Off | NTC > 1084, lamp ≤ 60 and the shot bit clear | |

The Tier S patch forces register `0x01` to 1 on every I2C cycle while the H200 II is attached; other heads branch out before this code. Confirmed on hardware (2026-10-14).

## Thermal protection

| Path | Logic |
|---|---|
| Analog head NTC, ADC `0x200000AE` (`fn_08015C78`; heads other than H200 II) | < 132 → forced cooldown `fn_0800E1E4` and `[0x200001EA] = 1`; < 75 → also severe `[0x200001BA] = 5`; recovers at ≥ 235 (`fn_0801233E`) |
| H200 II digital NTC `[0x200001E6]` | < 396 → `fn_0800E1E4`; < 260 → also severe `[0x200001CF] = 5` (modelling lamp off); recovers at ≥ 816 |
| Gates | `0x0800D5E8` (`fn_0800D5CC`), `0x0800F84E` (`fn_0800F840`) and `fn_08015B58` block charging (`0x20000049`) and firing (`0x2000004A`, `0x20000058`, `0x20000124`) |
| UI | Solid red thermometer while `0x2000004A = 1`; blinking when `[0x200001CF]` or `[0x200001BA]` = 5 (`0x08036A10`–`0x08036A94`). `"The temperature is\ntoo high to adjust."` (`0x0803C678`) appears when the modelling lamp is turned on while `[0x200001EA] = 1` (`0x08031FE8`). |

`0x200000A4` is the **battery voltage**, not a thermistor: `fn_0800C8EC` sets `[0x20000124]` and `[0x2000005E]` below 541.42, and `fn_0800CD40` draws the 4-bar battery icon at 770 / 732 / 695 / 655 and powers off via `0x2000005E`.
