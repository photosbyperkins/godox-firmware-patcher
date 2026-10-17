# Godox AD100Pro II

100 Ws round-head pocket strobe with a 5-step zoom, an on/off internal fan and one NTC thermistor.

| | |
|---|---|
| OEM image | `AD100ProII_RF433V1_07.bin` · 357,004 bytes · SHA-256 `5dd2dd434e0ca531a57fd5ad397a9de1cf4e8acf2374aa6bfc5d7fed17c135dc`. Not on Godox's public download page; request it from Godox support. |
| Platform | STM32F4-class, HSI 16 MHz → 168 MHz, APB1 timers 84 MHz · load `0x0800C000` · SP `0x2001BC00` · reset `0x0800C249` |
| File offset | address − `0x0800C000` |
| Patcher | [`patch.py`](patch.py) → Tiers S, R, X |
| Disassembly | [`disasm/AD100ProII_RF433V1_07.asm`](disasm/AD100ProII_RF433V1_07.asm) |
| Hardware | `1.07.02` flashed with G3; continuous fan and version on both screens confirmed (2026-10-11). Tiers S and X not yet flashed. |

Status marks and notation: [architecture.md › Conventions](../../docs/architecture.md#conventions).

## Builds

The version is stored as text in two 8-byte slots, so it is shown as `1.07.TT` without the leading `V`.

| Tier | File | Version | SHA-256 |
|---|---|---|---|
| S Studio | `AD100ProII_V1.07.01_studio.bin` | `1.07.01` | `8995f2b85fe0380282913d4d0697b7d3709d457b68257f6df2d57aec6eb55cc2` |
| R Recovery | `AD100ProII_V1.07.02_recovery.bin` | `1.07.02` | `86386df6319f9e4ba3719e514525f565968d7a456c424008d26ba7eb892006bc` |
| X Super | `AD100ProII_V1.07.03_super.bin` | `1.07.03` | `71ad25e7f833f655fa129a6e37f048ed0baba09e1ce34e21f325834765d6b381` |

- **S** — fan on whenever awake (except low-battery cutoff). Limits stock.
- **R** — S + 2× drain on both counters: primary 25 → 50, secondary 30 → 60 per 5 s. The 300 s / 180 s idle clears are unchanged, so R only matters for pauses shorter than those.
- **X** — R + HSS table −20 % on all rows: 1/1 HSS burst 60 → 75 shots, secondary throttle 32 → 40.

### Byte diff

| File offset | Address | Stock → patched | Effect | Tiers |
|---|---|---|---|---|
| `0x83A2` | `0x080143A2` | `29 78` → `24 E0` | `ldrb r1,[r5]` → `b 0x080143EE`: jump to the fan-on block | all |
| `0x5224`, `0x5228` | `0x08011224`, `0x08011228` | `19` → `32` | primary drain `cmp` / `subs r0,#25` → `#50` | R, X |
| `0x5278`, `0x527C` | `0x08011278`, `0x0801127C` | `1E` → `3C` | secondary drain `cmp` / `subs r0,#30` → `#60` | R, X |
| `0x26F48`–`0x2716D` | `0x08032F48` | 11 × 25 halfwords | HSS table (Table Set 2) | X |
| `0x239FC`–`0x23A03` | `0x0802F9FC` | `V1.07\0\0\0` → `1.07.TT\0` | Settings menu (ADR `0x0802F91A`) | all |
| `0x24484`–`0x2448B` | `0x08030484` | `V1.07\0\0\0` → `1.07.TT\0` | Device Info (ADR `0x080302D6`) | all |

Bytes changed: S 16, R 20, X 295. The other `%d.%d%d` strings in the image are time readouts (`…s` / `…秒`), not versions.

## Heat counter

### State (`r6 = 0x20000028`)

| Field | Meaning |
|---|---|
| `[+0x0]` | Per-flash charge lockout, steps |
| `[+0x1]` | Lockout length in cooldown: +3 per flash, cap 50 (5.0 s); lower caps at low power (`0x080110E8`–`0x08011118`) |
| `[+0x4]` | Secondary recycle delay, steps |
| `[+0x6]` | Secondary latch |
| `[+0x9]` | Drain prescaler (÷20) |
| `[+0xB]` | Cooldown (trip) flag |
| `[+0xD]` = `0x20000035` | HSS table flag |
| `[+0x1E]` | Primary idle timer, 3000 (300 s) |
| `[+0x20]` = `0x20000048` | **Primary accumulator** |
| `[+0x22]` | Cooldown window, 3000 (300 s) |
| `[+0x24]` | HSS flag timeout, 3 × 5 ms |
| `[+0x26]` | Secondary timer, 1800 (180 s) |
| `[+0x28]` = `0x20000050` | **Secondary accumulator** |

Charge-inhibit flag: `0x2000007B`.

### Add (`fn_08010FEC`)

| Step | Evidence |
|---|---|
| Row = `[0x20000001] & 7`, the zoom index 0–4 = 28 / 35 / 50 / 70 / 85 mm (clamped in `fn_08013718` at `0x08013BF4`; formatted as `"%2dmm"` from table `0x080340F4` in `fn_08016024` at `0x080160BA`). Rows 5–10 are unreachable padding. | `0x08011008`–`0x08011028` |
| Column 0–24 = `0x08032CD0[P]`, `P` from `0x20000116` / `0x20000117`. `P = 0` → 24; the map drops one column per ~3⅓ tenths of a stop, so column 24 = 1/1. TTL (low 2 bits of `[0x20000034]` = 0): thresholds on `[0x2000002A]` 40/50/…/100 → 3/6/…/24. | `0x08010FF2`–`0x080110A6` |
| Outside cooldown (`[+0xB] = 0`): idle timer = 3000, then add to `[+0x20]`. | `0x080110A8`–`0x080110BC` |
| At `≥ 6000` (`0x1770`): `[+0x0] = 10`, `0x2000007B = 1`, window = 3000, `[+0xB] = 1`. | `0x080110C0`–`0x080110DC` |
| During the window each flash raises `[+0x1]` by 3 and reloads `[+0x0]` from it: a growing per-flash lockout, not a hard 300 s lock. | `0x08011040`–`0x08011058` |
| **Secondary:** fed while `[+0x6] = 0`; timer `[+0x26]` = 1800; at `≥ 3200` (`0x0C80`, `0x08011162`) latch `[+0x6] = 1` and delay `[+0x4] = 5` (0.5 s). Latched flashes branch to `0x08011120` (skip `[+0x28]`), add 1 to `[+0x4]` (5 in HSS), cap 15 (1.5 s), and reload the timer. | `0x0801111A`–`0x08011180` |

### Tables (11 rows × 25 halfwords, 50 bytes per row)

**Table Set 1** `0x08032D22` (file `0x26D22`), used when `[0x20000035] ≠ 1`. Row 0 (28 mm): `1,1,1, 3,3,3, 6,6,6, 12,12,12, 24,24,24, 36,36,36, 50, 60,60,60, 70, 80, 100`.

| Row (zoom) | Column 24 | Shots to 6000 | Shots to 3200 (throttle) |
|---|---|---|---|
| 0 (28 mm) | 100 | 60 | 32 |
| 1 (35 mm) | 90 | 67 | 36 |
| 2 (50 mm) | 80 | 75 | 40 |
| 3 (70 mm) | 70 | 86 | 46 |
| 4 (85 mm; rows 5–7 identical) | 60 | 100 | 54 |

**Table Set 2** `0x08032F48` (file `0x26F48`), used when `[0x20000035] = 1` (HSS). Rows 0–9 are identical; row 10 differs in one entry and is unreachable.

| | Row values | Column 24 | Shots to 6000 / 3200 |
|---|---|---|---|
| Stock | `22×6, 36×3, 46×3, 60×4, 70×3, 86×3, 100×3` | 100 | 60 / 32 |
| Tier X | `18×6, 29×3, 37×3, 48×4, 56×3, 69×3, 80×3` | 80 | 75 / 40 |

### HSS flag `[+0xD]`

Set to 1 (with timeout `[+0x24] = 3`) right before calling `fn_08010FEC` in:

1. `fn_08012334` at `0x08012446`, after a 100-pulse loop (`0x08012420`–`0x0801243E`, `cmp r4,#0x64`), gated by `0x20000002 = 0` and bit 4 of `0x20000034` (the HSS icon) — on-camera HSS.
2. `fn_08017A8C` at `0x08017B9A`, after a 105-pulse loop (`0x08017B74`–`0x08017B92`, `cmp r4,#0x69`) when trigger mode `0x20000039 = 0x1A` — wireless HSS.

Single-pulse paths (`0x08012572`, `0x08013426`, `0x08013582`, `0x08017D0A`) write 0; the drain clears it when `[+0x24]` expires (`0x0801128C`–`0x08011296`). 🔶 Light output not scope-verified.

### Drain (`fn_080111F4`)

| Action | Evidence |
|---|---|
| Step = 100 ms: TIM14 (vector slot 61, IRQ 45) at PSC 83 / ARR 199 on an 84 MHz clock (`fn_08016E8C`: PLLM 8, PLLN 168, PLLP 2, APB1 ÷4) = 200 µs; ISR `0x08017000` → `fn_080175D8` ÷25 → `[+9]` ÷20. Gated by `[0x20000131] ≠ 0`. In sleep the clock drops to 28 MHz and PSC to 27 (`0x08016DE6`). | `0x0801297C`–`0x08012996`, `0x080175E2`, `0x0801765E`–`0x08017668` |
| Primary: every 50 steps −25 (clear if < 25); idle timer at 0 (300 s) clears the accumulator. | `0x08011208`–`0x0801122E` |
| Secondary: every 50 steps −30; timer at 0 (180 s without a flash) clears the latch, `[+0x28]` and `[+0x4]`. | `0x08011254`–`0x08011283` |
| Window `[+0x22]` at 0 → `fn_080111C8`: clears the trip flags, the primary timer and the accumulator. | `0x08011242`–`0x08011250`, `0x080111C8`–`0x080111E6` |

## Thermistor (`fn_08014234`)

Called every 21st pass of `fn_08014370`. Reads the raw ADC halfword `0x20000010`; `fn_0803228A` is `__aeabi_ui2d` and `fn_080322B0` a double compare, so there is no temperature conversion. ⚠️ Which component the thermistor sits on is unknown.

| Raw ADC (> 10 samples) | Result |
|---|---|
| > 950 | `[0x2000009E] = 2` (self-test `NTC:E1`), `[0x200000A0] = 1`, fan state 2 |
| < 20 | `[0x2000009E] = 3` (`NTC:E2`), `[0x200000A0] = 2`, fan state 2 |
| < 114.59 | forced cooldown `fn_0800E178` (same 300 s window as a counter trip, sets `0x2000007B`), `[0x20000139] = 1` |
| 114.59–204.14 | hold |
| ≥ 204.14 | if tripped: `fn_080111C8` (leave cooldown, clear the primary counter) |
| < 271.06 | fan state `[0x20000093]` = 2 |
| 271.06–356.03 | fan state 1 |
| ≥ 356.03 | fan state 0 |

## Fan (`fn_08014370`, main loop `0x0802C1FE`)

The fan is on GPIOC pin 4 (`0x40020800`, mask `0x10`), written through BSRR by `fn_080100A2`. The factory self-test (`fn_08017468`) toggles the same pin (`FAN:1` / `FAN:OFF`). In normal operation `fn_08014370` is the only writer; the other PC4 write (`0x080148EC`) is in a shutdown sequence.

| Condition, in order | Fan |
|---|---|
| `[0x20000039]` or `[0x2000003E]` = `0x1A` (HSS pulse train running) | unchanged; return |
| `[0x2000007A] = 1` — low-battery cutoff (`0x2000000C < 504.4` in `fn_0800CB78` at `0x0800CC04`; also blocks firing via `fn_08014194`) | off |
| NTC state, `[0x20000094]`, `[0x20000096]` and accumulator all 0 | off |
| NTC state 2 (raw < 271.06 or sensor fault) | on |
| Primary accumulator > 1200 | on |
| `[0x200000C7] ≥ 5` and `[0x20000096] = 1` (modelling lamp ≥ 60 %), or `[0x20000033] = 1` | on |
| otherwise, including NTC state 1 alone | off (no hysteresis) |

**Fan patch.** `0x080143A2` comes after the thermistor call (`0x08014394`), the `0x1A` early return and the low-battery check, so all three still work; only the on/off decision is replaced by "on".
