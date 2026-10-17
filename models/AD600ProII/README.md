# Godox AD600Pro II

600 Ws battery strobe with a two-speed internal fan, dual NTC thermistors and an LED modelling lamp. Primary target of the project.

| | |
|---|---|
| OEM image | `AD600PROII_v1.08.bin` · 407,384 bytes · SHA-256 `33e327457bef0023af5254153a990a572c6a3afeb792fdb84e5bf137613bf910` |
| Platform | STM32F4-class, HSI 16 MHz → 168 MHz · load `0x0800C000` · SP `0x20018570` · reset `0x0800C1A1` |
| File offset | address − `0x0800C000` |
| Patcher | [`patch.py`](patch.py) → Tiers S, R, X, R+, X+ |
| Disassembly | [`disasm/AD600PROII_v1.08.asm`](disasm/AD600PROII_v1.08.asm) |
| Hardware | `1.08.04` flashed with G3; version display and continuous Level 2 fan confirmed (2026-10-10). Other tiers code-verified only. |

Status marks and notation: [architecture.md › Conventions](../../docs/architecture.md#conventions).

## Builds

The 8-byte version slot holds at most 7 characters, so the version is shown as `1.08.TT` without the leading `v`.

| Tier | File | Version | SHA-256 |
|---|---|---|---|
| S Studio | `AD600PROII_v1.08.01_studio.bin` | `1.08.01` | `d85d22f05b84e5d259250da3c618f776e340f75d4f98dce922cc91f6c56c62ab` |
| R Recovery | `AD600PROII_v1.08.02_recovery.bin` | `1.08.02` | `d51033cc1dd911764b9995ef81dee7e449ab8db6ef3c2886c7c414c386ee63de` |
| X Super | `AD600PROII_v1.08.03_super.bin` | `1.08.03` | `a9b4b0f5fc18a44d1e0af5a1e03db9da199fabfdcc4737c6a7f8f734cd780d27` |
| R+ Recovery+ | `AD600PROII_v1.08.04_recovery_plus.bin` | `1.08.04` | `69b27c2789c9604db6aa6bab507e02303f3fb3f07c308076b1c17eb11a849114` |
| X+ Super+ | `AD600PROII_v1.08.05_super_plus.bin` | `1.08.05` | `c62e16a60bee7cf534469e19dfc6acf21f821b7c3ecc570063099c58e2e0109e` |

| Tier | Fan | Primary drain | Secondary drain | Burst throttle | 1/1 burst: normal / HSS |
|---|---|---|---|---|---|
| Stock | auto | 8 pts/s | 20 pts/s | from shot 38 / 30 | 80 / 64 |
| S | Level 2 always | stock | stock | from 38 / 30 | 80 / 64 |
| R | Level 2 always | **16 pts/s** | stock | from 38 / 30 | 80 / 64 |
| X | Level 2 always | **16 pts/s** | stock | from 38 / 38 | 80 / **80** |
| R+ | Level 2 always | **16 pts/s** | **40 pts/s** | from 38 / 30 | 80 / 64 |
| X+ | Level 2 always | **16 pts/s** | **40 pts/s** | **removed** | 80 / **80**, no stutter |

### Byte diff

| File offset | Address | Stock → patched | Effect | Tiers |
|---|---|---|---|---|
| `0xB4BC` | `0x080174BC` | `1D D0` → `1D E0` | `beq 0x080174FA` → `b`: always take the fan Level 2 path | all |
| `0x76CC` | `0x080136CC` | `28 29` → `50 29` | primary drain compare `cmp r1,#40` → `#80` | R, X, R+, X+ |
| `0x76D0` | `0x080136D0` | `28 39` → `50 39` | primary drain `subs r1,#40` → `#80` | R, X, R+, X+ |
| `0x7744` | `0x08013744` | `28 28` → `50 28` | secondary drain compare `cmp r0,#40` → `#80` | R+, X+ |
| `0x7748` | `0x08013748` | `28 38` → `50 38` | secondary drain `subs r0,#40` → `#80` | R+, X+ |
| `0x761C` | `0x0801361C` | `09 D3` → `09 E0` | `blo 0x08013632` → `b`: secondary throttle never trips | X+ |
| `0x2D8F0`–`0x2D927` | `0x080398F0` | 28 halfwords | HSS cost table (values below) | X, X+ |
| `0xF738`–`0xF73F` | `0x0801B738` | `v1.08\0\0\0` → `1.08.TT\0` | Device Info version | all |
| `0x123FC`–`0x12403` | `0x0801E3FC` | `v1.08\0\0\0` → `1.08.TT\0` | Settings menu version | all |

Bytes changed: S 15, R 17, X 45, R+ 19, X+ 48.

## Heat counter

### State (`r5 = 0x20000046`)

| Field | Address | Meaning |
|---|---|---|
| `[+0x0]` | `0x20000046` | Cooldown hold, in steps (10 at trip, up to 80; 90 when forced by a thermistor). At 0: accumulator cleared, charging re-enabled |
| `[+0x2]` | `0x20000048` | TTL power 0–100 (pre-flash `0x200000E1` + FEC `0x200000D4`) |
| `[+0x4]` | `0x2000004A` | Secondary lock: 5 steps = 0.5 s charge pause |
| `[+0x6]` | `0x2000004C` | Secondary latch |
| `[+0x8]` | `0x2000004E` | Heat stage / fan demand: 1 at ≥ 2000 pts, 2 above 4000 pts or on secondary trip |
| `[+0xC]` | `0x20000052` | Idle timer, reloaded to 1200 (120 s) by each flash outside cooldown |
| `[+0xE]` | `0x20000054` | **Primary accumulator** |
| `[+0x10]` | `0x20000056` | Post-trip window, 3000 steps (300 s) |
| `[+0x14]` | `0x2000005A` | Secondary window, 300 steps (30 s), reloaded by every flash |
| `[+0x16]` | `0x2000005C` | **Secondary accumulator** |

Flags: `0x200000DB` charge inhibit · `0x200000DC` cooldown active · `0x200000DD` HSS table select.

### Add (`fn_080134E4`)

| Step | Evidence |
|---|---|
| Index = `0x0803985C[P]`, with `P` from `0x2000009E` (Manual) or `0x2000009F` (Multi). In TTL (`[0x2000009D] & 3 == 0`) the index comes from `[+0x2]` via thresholds → 6, 9 … 27. `P = 0` (1/1) → index 27. | `0x080134F6`–`0x0801356E` |
| Outside cooldown: idle timer = 1200, then add the cost from `0x080398F0` if `0x200000DD = 1`, else `0x080398B8`. | `0x08013570`–`0x080135AA` |
| At `≥ 6400` (`0x1900`): hold = 10, `0x200000DB = 1`, window = 3000, `0x200000DC = 1`, call `fn_08039170`. | `0x0801358E`–`0x080135A0` |
| Stage `[+0x8]`: 2 above 4000, 1 at ≥ 2000. | `0x080135AC`–`0x080135C2` |
| During cooldown each flash extends the hold by 3 steps (1 once above 40), capped at 80 (8.0 s), and reloads the 300 s window. | `0x08013522`–`0x080135DE` |

Standard table `0x080398B8`: entries 3 … 80; index 27 = 80 → 6400 ÷ 80 = **80 shots** at 1/1, matching the user manual.

HSS table `0x080398F0` (index 0 → 27):

| | Values | Index 27 | Shots at 1/1 |
|---|---|---|---|
| Stock | `25×6, 27×3, 30×4, 35×2, 45×3, 55×3, 70×3, 90×3, 100` | 100 | 64 |
| Tier X / X+ | `20×9, 25×6, 32×3, 40×3, 50×3, 64×3, 80` | 80 | 80 |

Each entry drops 16.7–28.9 % (+20.0–40.6 % shots at that power).

### Secondary burst throttle

Runs in `fn_080134E4` right after the primary add. Found by comparison with the AD600BM II, where the same fields exist but are never written.

| Step | Evidence |
|---|---|
| Unlatched (`[+0x6] = 0`): add the same cost to `[+0x16]` and reload `[+0x14] = 300`. | `0x080135EC`, `0x08013600`–`0x08013618` |
| At `≥ 3000` (`movw sl,#0xbb8` at `0x0801351C`, `cmp` at `0x0801361A`): lock `[+0x4] = 5`, stage `[+0x8] = 2`, latch `[+0x6] = 1`. | `0x0801361E`–`0x08013624` |
| Latched: each flash skips `[+0x16]`, reloads `[+0x14] = 300`, and re-arms lock = 5 if the index is ≥ 24 (1/1–1/2) or HSS is active. | `0x080135EC`–`0x080135FE` |
| The charge gate treats a non-zero lock like `0x200000DB`: it calls `fn_0801243A(…, 4, 1)` to hold charging and suppresses the ready beep (`0x0800F3C4`). | `0x0801135C`–`0x0801136A` |

In practice the strobe inserts a 0.5 s charge pause after **38** full-power shots (3000 ÷ 80; 30 in stock HSS), long before the 80-shot cooldown. Tier R+ doubles the pre-latch drain; Tier X+ skips the trip entirely.

### Drain (`fn_08013694`, from scheduler `0x0801F572`)

| Action | Evidence |
|---|---|
| Step = 100 ms: TIM14 200 µs × 25 × 20 (see [architecture.md §3](../../docs/architecture.md#3-timer-one-step--100-ms)). | `0x0801369A`–`0x080136A6` |
| Idle timer at 0 (120 s without a flash outside cooldown): accumulator and stage cleared. | `0x080136A8`–`0x080136C6` |
| Every 50 steps (5.0 s): −40 (Tier R and above: −80). | `0x080136B6`–`0x080136D6` |
| Every 40 steps (4.0 s), only while HSS is off (`[0x20000E80+3] = 0`, set in `fn_0801BBE0` at `0x0801BDCC`): −5 more (1.25 pts/s). | `0x080136D8`–`0x080136F2` |
| Hold `[+0x0]` at 0: accumulator cleared, `0x200000DB = 0`. | `0x080136F8`–`0x0801370A` |
| Window `[+0x10]` at 0: `fn_08013664` clears `0x200000DC`. | `0x0801370C` |
| Every 20 secondary-window steps (2.0 s): `[+0x16]` −40 (R+/X+: −80). Draining to 0 does **not** clear the latch. | `0x0801372C`–`0x0801374F` |
| Secondary window at 0 (30 s without a flash): latch and `[+0x16]` cleared. Lock decremented every step. | `0x0801371E`–`0x0801373E`, `0x08013750` |

## HSS detection

Selecting HSS (`'高速同步'`) sets `[0x20000E80,#3] = 1` and bit 4 of `0x2000009D` (`0x0801394E`, `0x08017D2E`). The trigger dispatchers (`0x08017E82`, `0x080182CC`, `0x080196F6`) write `([0x2000009D] & 0x10) | 0x0A` = `0x1A` to `0x200000D5`. In mode `0x1A`, `fn_0801F6C0` runs a 105-pulse loop (`cmp r4,#0x69` at `0x0801F796`), writes `0x200000DD = 1` (`0x0801F7C2`; also `fn_0801F674` at `0x0801F694`) and calls `fn_080134E4`. Standard flash paths write 0 first: `0x08016D4C` (`fn_08016CF0`), `0x08016DB2` (`fn_08016D70`), `0x0801F820` (mode `0x0A`). 🔶 Light output not scope-verified.

## Fan

`fn_08017480` runs every 21st call (skipped while `0x200000D5` or `0x200000E0` = `0x1A`). It samples NTC B (`fn_080172D8`, `0x080174AE`) and NTC A (`fn_08017120`, `0x080174B2`), then chooses the level in `0x20000106`:

| Level | Condition |
|---|---|
| 2 (high) | either NTC in state 2, cooldown `0x200000DC = 1`, or stage `0x2000004E = 2` |
| 1 (low) | either NTC in state 1, modelling lamp on (`[0x2000007B] ≠ 0`) above 20 % (`[0x20000007] > 0x14`), secondary latch `0x2000004C = 1`, or stage `0x2000004E = 1` |
| 0 | otherwise |

Driver `fn_08010E74`: Level 1 = PC14 high, PA4 low; Level 2 = PC14, PA4, PA7 high. It forces the fan off when `0x200000A6 = 1` (low-battery cutoff: gauge ≤ 3, set at `0x0800E7A8`) or `0x20000080 = 1` (low-voltage power-down latch: `0x2000002A < 0x1BA` for > 50 passes, set at `0x0800E690`; also clears PC10/PC11). Both also inhibit charging.

**Fan patch.** The branch at `0x080174BC` comes *after* both thermistor calls, so it skips only the level decision (`0x080174BE`–`0x080174F8`). The driver's off-conditions still apply. No limit changes.

## Thermistors and errors

Both routines read a raw `u16`, convert with `bl 0x0800C510` and compare doubles with `bl 0x0800C55C`.

**NTC A** — `0x2000002C`, `fn_08017120`, flash head / modelling lamp. While the lamp is on, 10 counts are subtracted first (`0x08017126`–`0x0801713A`).

| Raw ADC | Result | Evidence |
|---|---|---|
| > 970 (> 10 samples) | open fault: `0x200000F0 = 2`, `0x20000110 = 1`, state 2 | `0x0801714A`–`0x0801715E` |
| < 20 (> 10 samples) | short fault: `0x200000F0 = 3`, `0x20000110 = 2`, state 2 | `0x08017170`–`0x08017186` |
| < 132.01 (> 5 samples) | `0x200000F0 = 1`, forced cooldown `fn_080103B4`, lamp throttle `[0x2000000C] = 1` (read by `fn_080167FC`), state 2 | `0x08017198`–`0x080171C8` |
| 132.01–271.06 | state 2 (> 10 samples) | `0x080171D0`–`0x08017200` |
| 271.06–356.03 | state 1; clears `[0x2000000C]` | `0x08017204`–`0x08017230` |
| 356.03–404.52 | hold | `0x08017234`–`0x0801726A` |
| ≥ 404.52 | state 0 | `0x0801726C`–`0x08017286` |

**NTC B** — `0x2000002E`, `fn_080172D8`, main board / IGBT.

| Raw ADC | Result | Evidence |
|---|---|---|
| > 970 / < 20 | `0x200000F1 = 2` / `3` (open / short) | `0x080172F4`–`0x08017324` |
| < 49.69 (> 5 samples) | `0x20000147 = 1` → **Error E2**, state 2 | `0x0801734E`–`0x0801736E` |
| < 132 or < 86 (> 5 samples; threshold chosen by post-flash timer `0x20000150`) | `0x200000F1 = 1`, forced cooldown `fn_080103B4`, state 2 | `0x0801732E`–`0x0801739A` |
| < 271.06 | state 2 (> 10 samples) | `0x080173A2`–`0x080173D4` |
| 271.06–311.40 | state 1 | `0x080173D6`–`0x080173FA` |
| 311.40–356.03 | hold | `0x080173FC`–`0x0801742E` |
| ≥ 356.03 | state 0 | `0x08017430`–`0x0801744E` |

**Forced cooldown** `fn_080103B4` (only if `0x200000DC = 0`): hold = 90 (9.0 s), `0x200000DB = 1`, window = 3000 (300 s), `0x200000DC = 1`. A thermistor trip therefore starts with the same cooldown as the counter; E2 is a separate, deeper trip from NTC B only.

**Errors** `fn_080103E0` → `0x20000079`: `0x200000F2 = 1` → E1; `0x20000147 ≠ 0` → E2; `0x200000DE = 1` → E3. Any non-zero code blocks charging (`0x08011328`–`0x08011334`).

## Other findings

- **Version strings.** `v1.08` sits in two 8-byte slots: `0x0801B738`, referenced at `0x0801B666` / `0x0801B68C` on the Device Info screen (next to `"Device Info"` and `"Model:"`), and `0x0801E3FC`, referenced at `0x0801E25C` (EN) / `0x0801E49C` (CN) in `fn_0801DE80` as the right-aligned value of row 15 (`"Device info"` / `"设备信息"`) in the Settings menu. Both confirmed on hardware.
- **Multi (stroboscopic) limit table** `0x08039A65`: flash count vs. frequency for 7 power levels (`P = 20…80`, 1/4–1/256). `0x20000077` divides 50000 to set the timer period (frequency in Hz, `0x08016DF8`); counter `0x200000CF` is compared with `0x20000076` (`0x0801B8D2`); the row base `0x08039AA6 ± 13·k` is chosen by `[0x20000074,#0x2B]` (`0x08016C8E`–`0x08016CE6`). It is not an HSS limit. `0x08039A56` is a separate 15-byte setting-limit table.

## Comparison with AD600BM II v1.02

The AD600BM II (manual-only sibling, not distributed here) allows longer bursts. Its firmware (base `0x0800C000`) uses the same heat-counter design — same power map, standard table, idle timer (1200), drain (40 per 50 steps) and window (3000) — and differs in constants:

| | Pro II v1.08 | BM II v1.02 |
|---|---|---|
| Add / drain | `fn_080134E4` / `fn_08013694` | `fn_08012CA8` / `fn_08012E18` |
| State struct | `0x20000046` | `0x200000B8` |
| Tables (std / alt) | `0x080398B8` / `0x080398F0` | `0x08037584` / `0x080375BC` |
| **Primary threshold** | **6400** (`b0f5c85f` at `0x0801358E`) | **8000** (`b0f5fa5f` at `0x08012D84`) |
| Fan-demand stages | 4000 / 2000 | 4800 / 2400 |
| **Secondary throttle** | active (3000) | dead code: drain, charge gate (`0x08010BB2`) and fan check (`0x080160DA`) read the fields, but the add routine never writes them (exits at `0x08012D06`) |
| Cooldown penalty | +3 then +1, cap 80 | +1, cap 30 |
| TTL index range | 6 … 27 | 3 … 24 (one step cheaper at every level) |
| Alt (HSS) table | `25 … 100` | `30 … 120` (stricter) |
| Extra −5 / 40-step drain with HSS off | present | absent (stricter) |
| NTC A thresholds | `404.52 / 356.03 / 271.06 / 132.01` | `404.52 / 356.03 / 311.40 / 271.06 / 176.32` (forced cooldown below 176.32, stricter) |
| NTC B thresholds | `356.03 / 311.40 / 271.06 / 132.01 / 86.0 / 49.69 (E2)` | `356.03 / 311.40 / 271.06 / 235.70 / 132.01` (no E2) |

Shots to the primary trip from empty in a continuous burst:

| Index | Pro II std | BM II std | Pro II alt | BM II alt |
|---|---|---|---|---|
| 27 (1/1) | 80 (throttled from 38) | **100** | 64 (throttled from 30) | 67 |
| 26 | 107 | 134 | 72 | 80 |
| 24 | 160 | 200 | 72 | 80 |
| 21 | 320 | 400 | 92 | 100 |

The BM II's extra headroom comes from the 25 % higher threshold, the missing throttle and the smaller cooldown penalty. In HSS the two are close because the BM II's alt costs are higher.

Candidate BM II-parity patches. Only #3 is used (Tier X+); the rest are **not applied**:

| # | Change | Address (file offset) | Bytes |
|---|---|---|---|
| 1 | Primary threshold 6400 → 8000 | `0x0801358E` (`0x758E`) | `b0f5c85f` → `b0f5fa5f` |
| 2 | Fan stages 4000 / 2000 → 4800 / 2400 | `0x080135AC` (`0x75AC`) / `0x080135B6` (`0x75B6`) | `b0f57a6f` → `b0f5965f`; `b0f5fa6f` → `b0f5166f` |
| 3 | Disable the secondary throttle | `0x0801361C` (`0x761C`) | `09d3` → `09e0` |
| 4 | Cooldown penalty cap 80 → 30 | `0x080135CC` (`0x75CC`) / `0x080135D0` (`0x75D0`) | `5028` → `1e28`; `5020` → `1e20` |

With #1 alone, true HSS parity would also need the BM II's higher alt table (120 at 1/1 → 67 shots); keeping the Pro II table gives 80 shots, and adding Tier X's table gives 100 (+56 %), which is not recommended.

> [!WARNING]
> The BM II limits ship on **different hardware**. Nothing in the firmware shows that the two share capacitor banks, IGBTs or tube cooling, and Godox may have tuned the Pro II more conservatively on purpose (0.9 s recycle, continuous LED modelling lamp).
