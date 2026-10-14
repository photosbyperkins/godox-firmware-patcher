# Godox AD600Pro II (Tier 1 — main focus)

| Item | Value |
|---|---|
| OEM image | `AD600PROII_v1.08.bin` (407,384 bytes) |
| Load address / SP / reset | `0x0800C000` / `0x20018570` / `0x0800C1A1` |
| Disassembly | [`disasm/AD600PROII_v1.08.asm`](disasm/AD600PROII_v1.08.asm) |
| Custom builds | `AD600PROII_v1.08.01_studio.bin` (Tier S), `.02_recovery` (Tier R), `.03_super` (Tier X), `.04_recovery_plus` (Tier R+), `.05_super_plus` (Tier X+) — **flashing, 1.08.04 display & Level 2 fan mod confirmed on hardware** (2026-10-10) |
| Patcher | [`patch.py`](patch.py) (version scheme: [root README §1](../README.md#1-firmware-profiles--version-scheme)) |
| Technical details | [`SUPER_MODE.md`](SUPER_MODE.md), [`../TIERED_RATINGS.md`](../TIERED_RATINGS.md) |
| Technical findings | [`../FINDINGS.md` §2](../FINDINGS.md#2-ad600pro-ii-thermal-architecture) |

## Firmware profiles at a glance

The version is shown as `1.08.TT` with no leading `v`, because the firmware's 8-byte version slot only fits 7 characters.

| Build | Version | Core Modifications | Burst Throttle (Shot 38 Stutter) | Max 1/1 Burst | Inter-Burst Recovery |
|---|---|---|---|---|---|
| **Tier S (Studio)** | `1.08.01` | Fan Level 2 continuous | Active | Stock (80 std / 64 HSS) | Stock (fan-assisted) |
| **Tier R (Recovery)** | `1.08.02` | Fan Level 2 + 2× primary drain (40 → 80) | Active | Stock | 2× primary drain |
| **Tier X (Super)** | `1.08.03` | Fan Level 2 + 2× primary drain + Lowered HSS table | Active | 80 std / 80 HSS | 2× primary drain |
| **Tier R+ (Recovery Plus)** | `1.08.04` | Fan Level 2 + 2× primary drain + **2× secondary drain (40 → 80)** | Active | Stock | **2× primary + 2× pre-latch secondary** |
| **Tier X+ (Super Plus)** | `1.08.05` | Fan Level 2 + 2× drain (both) + Lowered HSS table + **Burst throttle bypassed** | **Disabled (Bypassed)** | **80 std / 80 HSS clean** | **2× on both (throttle disabled)** |

## Key addresses & verified architecture

| What | Where | Details |
|---|---|---|
| Error E2 set from flag `0x20000147` | `0x080103F4` | Triggered exclusively when NTC B drops below 49.69 raw ADC count for > 5 samples (`0x08017360`) |
| NTC A Thermistor — Flash head / modeling lamp (`✅`) | `0x2000002C` (`fn_08017120`) | Raw ADC counts (no °C conversion; lower is hotter): subtracts `10` counts when modeling lamp is on (`[0x2000007B] != 0` at `0x08017126`); < 132.01 (debounce > 5) sets `[0x2000000C] = 1` (throttles/shuts off modeling lamp in `fn_080167FC`) and calls `fn_080103B4` (forced 9.0 s cooldown); < 271.06 Fan Level 2; < 356.03 Fan Level 1; ≥ 404.52 Fan Level 0 |
| NTC B Thermistor — Main board / IGBT (`✅`) | `0x2000002E` (`fn_080172D8`) | Raw ADC counts: < 49.69 (debounce > 5) sets `0x20000147` → Error E2; < 132.01 or < 86.0 (debounce > 5) calls `fn_080103B4` (forced 9.0 s cooldown); < 271.06 Fan Level 2; < 311.40 Fan Level 1; ≥ 356.03 Fan Level 0 |
| Fan level decision / fan GPIO driver | `fn_08017480` / `fn_08010E74` | PC14 = low speed, PC14+PA4+PA7 = high speed; Level 2 if NTC A/B state 2, cooldown (`0x200000DC == 1`), or `0x2000004E == 2` (`[r5,#8]`); Level 1 if NTC A/B state 1, `0x2000004C == 1` (`[r5,#6]` secondary latch), `0x2000004E == 1`, or modeling lamp on > 20% (`[0x2000007B] != 0 && [0x20000007] > 20`) |
| Shutdown / standby flags | `0x200000A6`, `0x20000080` | `0x200000A6`: Low battery cutoff (battery gauge ≤ 3); `0x20000080`: Low-voltage power-down latch (raw ADC < 0x1BA) |
| Hardware step timer | TIM14 IRQ 45 (`0x0801EE58`) | 200 µs base × 25 (`0x0801F4DC`) × 20 (`fn_08013694`) = **0.100 s (100 ms) nominal / step** (HSI 16 MHz PLL at 168 MHz ±1%, gated by `[0x2000016E] != 0` and `[0x200000A7] == 0`) |
| Heat counter add / drain | `fn_080134E4` / `fn_08013694` | Primary drain: 50 steps = **5.000 s nominal** (stock: 8.0 pts/s; Tier R/X/R+/X+: 16.0 pts/s; plus `-5 / 4.0 s` = `1.25 pts/s` at `0x080136D8` when HSS is off `[0x20000E80+3] == 0` ✅) |
| Heat state struct | `0x20000046` (accumulator `+0xE` = `0x20000054`) | Idle timer `[+0xC]` = 1200 steps (**120.0 s** outside cooldown; clears accumulator at 0) |
| Accumulator, threshold | `0x20000054`, 6400 (`0x0801358E`) | Cooldown hold `[r5]` = 10..80 steps (1.0..8.0 s; 9.0 s thermal-forced); `[+0x10]` = 3000 steps (**300.0 s post-trip window**) |
| Fan-demand stages from accumulator (`0x2000004E`) | > 4000 → 2 (`0x080135AC`), ≥ 2000 → 1 (`0x080135B6`) | Active in stock firmware |
| Cooldown penalty counter `[+1]` | +3 while ≤ 40, then +1, cap 80 (`0x08013522`–`0x080135D2`) | Added on each flash during cooldown |
| Secondary burst accumulator / window / lock | `[+0x16]` (threshold 3000), `[+0x14]` (300 = 30.0 s), lock `0x2000004A` (`[r5,#4] = 5` = **0.5 s pause**), latch `0x2000004C` (`[r5,#6]`) | Triggers after ~38 full-power shots (30 HSS); latch clears only after 30.0 s without flashes |
| Charge gate (cooldown `0x200000DB`, lock `0x2000004A`) | `0x08011344`–`0x08011370` | Halts or delays capacitor charging |
| Heat tables | `0x080398B8` (standard), `0x080398F0` (selected by `0x200000DD`) | ✅ `0x080398F0` linked from UI `'HSS'` (`[0x20000E80,#3]` / bit 4 of `0x2000009D`) → mode `0x1A` in `0x200000D5` → `fn_0801F6C0` (105-pulse loop) & `fn_0801F674` → `0x200000DD = 1` |
| Power map / UI formatter | `0x0803985C` (maps $P=0$ to index 27) / `fn_08016aac` (`0x08016aac`) | Exact 1/10-stop EV mapping |
| Multi-mode stroboscopic table | `0x08039A65` | Flash count vs frequency vs power table (7 rows × 13 cols, $P=20 \dots 80$, 1/4 to 1/256) |

## Secondary burst throttle

✅ Verified in disassembly (`fn_080134E4` and `fn_08013694`). After the main heat counter is updated, `fn_080134E4` runs a second, short-window accumulator:

- **Pre-latch (`0x2000004C == 0`):** Every flash adds the same table cost to `[0x20000046+0x16]` and reloads the 300-step (`30.0 s`) window `[+0x14]` (`0x08013606`–`0x0801361A`). The drain routine (`0x08013742`–`0x0801374F`) subtracts 40 points (80 in Tier R+/X+) every 20 window steps (`2.0 s`), accelerating pre-latch recovery between bursts so the accumulator drains before reaching 3000.
- **Trip at 3000 points (`0x0801361E`–`0x0801362E`):** Sets the lock byte `0x2000004A` (`[r5,#4]`) = 5 (decremented every 0.1 s step at `0x08013750`–`0x08013756` for a **0.5 s charge pause**), fan demand `0x2000004E` (`[r5,#8]`) = 2, and latch `0x2000004C` (`[r5,#6]`) = 1.
- **Post-latch (`0x2000004C == 1`):** Every later flash takes the branch at `0x080135EC`–`0x08013604`, which **never reads or adds to `[+0x16]`**, re-arms `0x2000004A = 5` (**0.5 s pause**) if the table index is ≥ 24 (1/1 to 1/2) or `0x200000DD != 0` (HSS), and reloads `[+0x14] = 300` (**30.0 s**) on every flash. Periodic draining of `[+0x16]` to 0 (`0x0801374A`) does **not** clear `0x2000004C`; the latch only clears when `[+0x14]` expires to 0 after **30.0 s with zero flashes** (`0x0801373A`).
- The charge gate at `0x0801135C` treats a non-zero `0x2000004A` the same way as the main cooldown flag `0x200000DB`.

In practice the unit starts inserting 0.5 s charge pauses after **38 rapid full-power shots** (30 in HSS mode), well before the 80-shot main cooldown.

## Comparison with AD600BM II v1.02

The AD600BM II is known to allow longer bursts than the Pro II. Its v1.02 firmware (base `0x0800C000`, not distributed here) uses the **same heat-counter design**: identical power→index map, standard table, idle timer (1200), drain (40 per 50 steps) and cooldown recycle value (3000). The difference comes from constants and one disabled feature.

| | Pro II v1.08 | BM II v1.02 |
|---|---|---|
| Add / drain routine | `fn_080134E4` / `fn_08013694` | `fn_08012CA8` / `fn_08012E18` |
| Heat state struct | `0x20000046` | `0x200000B8` |
| Tables (std / alt) | `0x080398B8` / `0x080398F0` | `0x08037584` / `0x080375BC` |
| **Main cooldown threshold** | **6400** (`b0f5c85f` @ `0x0801358E`) | **8000** (`b0f5fa5f` @ `0x08012D84`) |
| Fan-demand stages | 4000 / 2000 | 4800 / 2400 |
| **Secondary burst throttle** | **Active** (3000 pts) | **Dead code**: drain, charge gate (`0x08010BB2`) and fan check (`0x080160DA`) still read the fields, but the add routine never writes them |
| Cooldown penalty | +3 then +1, cap 80 | +1, cap 30 |
| Index from `[+2]` when mode bits = 0 (**TTL mode** ✅: `[0x20000048]` from pre-flash `0x200000E1` + FEC `0x200000D4`) | 6 … 27 | 3 … 24 (one table step cheaper at every level) |
| Alt table | `25 … 100` | `30 … 120` (**stricter**) |
| Extra conditional drain (−5 / 40 steps when HSS Off `[0x20000E80+3] == 0`, `0x080136D8`) | Present | Absent (**stricter**) |
| Raw ADC thermistor thresholds (NTC A / NTC B) | NTC A (`fn_08017120`): `404.52 / 356.03 / 271.06 / 132.01`<br>NTC B (`fn_080172D8`): `356.03 / 311.40 / 271.06 / 132.01 / 86.0 / 49.69 (E2)` | NTC A (`fn_08015DAC`): `404.52 / 356.03 / 311.40 / 271.06 / 176.32` (**stricter** forced cooldown `< 176.32`)<br>NTC B (`fn_08015F10`): `356.03 / 311.40 / 271.06 / 235.70 / 132.01` (fan 2 `< 235.70`, fan 1 `< 271.06`, cooldown `< 132.01`, no `49.69` / no `E2`) |

Shots until the main counter trips, in a continuous burst from empty (each flash resets the idle timer, so nothing drains):

| Index | Pro II std | BM II std | Pro II alt | BM II alt |
|---|---|---|---|---|
| 27 (1/1) | 80 *(throttled from 38)* | **100** | 64 *(throttled from 30)* | 67 |
| 26 | 107 | 134 | 72 | 80 |
| 24 | 160 | 200 | 72 | 80 |
| 21 | 320 | 400 | 92 | 100 |

**Summary:** the BM II's extra headroom comes from the 25% higher main threshold, the missing burst throttle, and the shorter cooldown penalty. In alt-table (HSS) mode the two are almost even, because the BM II's per-shot costs there are higher.

### Candidate BM II-parity patches (not applied)

| # | Change | Address (file offset) | Bytes |
|---|---|---|---|
| 1 | Main threshold 6400 → 8000 | `0x0801358E` (`0x758E`) | `b0f5c85f` → `b0f5fa5f` |
| 2 | Fan stages 4000 / 2000 → 4800 / 2400 | `0x080135AC` (`0x75AC`) / `0x080135B6` (`0x75B6`) | `b0f57a6f` → `b0f5965f`; `b0f5fa6f` → `b0f5166f` |
| 3 | Disable the secondary burst throttle (`blo` → `b`) | `0x0801361C` (`0x761C`) | `09d3` → `09e0` |
| 4 | *(optional)* Cooldown penalty cap 80 → 30 | `0x080135CC` (`0x75CC`) / `0x080135D0` (`0x75D0`) | `5028` → `1e28`; `5020` → `1e20` |

*(Note: Bypassing the burst throttle [#3] and doubling the secondary drain have now been integrated into official custom profiles **Tier R+ (`1.08.04`)** and **Tier X+ (`1.08.05`)**).*

*(Note on Alt Table Parity: If the main threshold were raised to 8000, true BM parity would actually require porting the BM II's higher alt table [120 vs 100 at 1/1] to achieve 67 HSS shots. Leaving the Pro II's lower table with an 8000 threshold yields 80 shots, and stacking it with Tier X's table yields 100 shots [+56% over stock], which is unsafe and not recommended.)*

> [!WARNING]
> The BM II 8000 threshold and reduced cooldown penalty shipped from Godox on **different hardware**. Nothing in the firmware proves the BM II and Pro II share identical capacitor banks, IGBTs, or tube cooling. Godox may have tuned the Pro II more conservatively on purpose (e.g. accounting for its 0.9s recycle time and continuous LED modeling lamp). The safe enhancements derived from BM II are the synchronized secondary drain (Tier R+, `1.08.04`) and the throttle bypass (Tier X+, `1.08.05`).

