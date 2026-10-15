# Godox AD600Pro II (Tier 1 — main focus)

| Item | Value |
|---|---|
| OEM image | `AD600PROII_v1.08.bin` (407,384 bytes), SHA-256 `c1743f54bf691456a297e29cb005085e33ae4c8d76dfcbf6c7df33b934b17b6a` |
| Load address / SP / reset | `0x0800C000` / `0x20018570` / `0x0800C1A1` |
| Disassembly | [`disasm/AD600PROII_v1.08.asm`](disasm/AD600PROII_v1.08.asm) |
| Custom builds | `AD600PROII_v1.08.01_studio.bin` (Tier S), `.02_recovery` (Tier R), `.03_super` (Tier X), `.04_recovery_plus` (Tier R+), `.05_super_plus` (Tier X+) — **flashing, 1.08.04 display & Level 2 fan mod confirmed on hardware** (2026-10-10) |
| Patcher | [`patch.py`](patch.py) (version scheme: [root README §1](../README.md#1-firmware-profiles--version-scheme)) |
| Technical classification | [`../TIERED_RATINGS.md`](../TIERED_RATINGS.md) |
| Technical findings | [`../FINDINGS.md` §2](../FINDINGS.md#2-ad600pro-ii-thermal-architecture) |

Status marks follow [FINDINGS.md](../FINDINGS.md#status-legend): ✅ verified in code · 🔶 partial · ⚠️ unverified. File offset = address − `0x0800C000`.

## Firmware profiles at a glance

The version is shown as `1.08.TT` with no leading `v`, because the firmware's 8-byte version slot only fits 7 characters.

| Build | Version | Core Modifications | Burst Throttle (Shot 38 Stutter) | Max 1/1 Burst | Inter-Burst Recovery |
|---|---|---|---|---|---|
| **Tier S (Studio)** | `1.08.01` | Fan Level 2 continuous | Active | Stock (80 std / 64 HSS) | Stock (fan-assisted) |
| **Tier R (Recovery)** | `1.08.02` | Fan Level 2 + 2× primary drain (40 → 80) | Active | Stock | 2× primary drain |
| **Tier X (Super)** | `1.08.03` | Fan Level 2 + 2× primary drain + Lowered HSS table | Active | 80 std / 80 HSS | 2× primary drain |
| **Tier R+ (Recovery Plus)** | `1.08.04` | Fan Level 2 + 2× primary drain + **2× secondary drain (40 → 80)** | Active | Stock | **2× primary + 2× pre-latch secondary** |
| **Tier X+ (Super Plus)** | `1.08.05` | Fan Level 2 + 2× drain (both) + Lowered HSS table + **Burst throttle bypassed** | **Disabled (Bypassed)** | **80 std / 80 HSS clean** | **2× on both (throttle disabled)** |

## Detailed Profile Modifications

### 1. Fan always at level 2 (`Tier S, R, X, R+, X+`)

| Item | Details |
|---|---|
| Change | File offset `0xB4BD`: `D0` → `E0`. At `0x080174BC`, `beq 0x080174FA` becomes `b 0x080174FA`. |
| Effect | ✅ **Confirmed on hardware (2026-10-10):** `fn_08017480` forces fan level 2 in `0x20000106`, skipping only the fan-level decision tree (`0x080174BE`–`0x080174F8`: NTC states, cooldown `0x200000DC`, secondary latch `0x2000004C` = `[r5,#6]`, heat stage `0x2000004E` = `[r5,#8]`, and modeling lamp `[0x2000007B] != 0 && [0x20000007] > 20`). The chassis fan runs continuously at high speed, actively circulating cooling airflow over the heatsink. |
| Thermistor routines still run | ✅ `fn_080172D8` (NTC B: main board / IGBT) and `fn_08017120` (NTC A: flash head / modeling lamp) are called before the branch (`0x080174AE`, `0x080174B2`). |
| Fan driver still honors off flags | ✅ `fn_08010E74` forces the fan off when `0x200000A6` (low battery cutoff, gauge ≤ 3) or `0x20000080` (low-voltage power-down latch, raw ADC < 0x1BA) = 1. |
| Loosens any limit? | No. |

### 2. Heat-counter drain 40 → 80 (`Tier R, X, R+, X+`)

| Item | Details |
|---|---|
| Change | Primary: file offset `0x76CC` (`28` → `50`, `cmp r1,#0x50`) and `0x76D0` (`28` → `50`, `subs r1,#0x50`). In Tier R+/X+, also secondary: `0x7744` and `0x7748` (`28` → `50`). |
| Effect | ✅ Primary: when `[+0xC]` idle timer is a multiple of 50 (every 5.0 s), 80 points are drained instead of 40 (plus the stock `-5 / 4.0 s` extra drain at `0x080136D8` when HSS is off `[0x20000E80+3] == 0` ✅). Secondary (Tier R+/X+): when `[+0x14]` is a multiple of 20 (every 2.0 s), 80 points are drained instead of 40, accelerating **pre-latch (`[r5,#6] == 0`) recovery between bursts**. Once the secondary latch `0x2000004C` (`[r5,#6]`) is set at 3000 pts, draining `[+0x16]` to 0 does not clear the latch—it only clears when `[+0x14]` expires after 30.0 s with zero flashes (`0x0801373A`). |
| During a continuous burst | ✅ **No effect.** Every flash resets the primary idle timer to 1200 (`0x0801357C`) outside cooldown and the secondary timer to 300 (`0x08013604`/`0x0801360C`). |
| After a long pause | ✅ The primary counter resets to zero after 1200 steps (120.0 s) with no flash outside cooldown (`0x080136C4`), and the secondary state resets after 300 steps (30.0 s) with no flash (`0x08013734`–`0x08013740`). |
| Time per step | ✅ **0.100 s (100 ms) nominal.** Derived from TIM14 200 µs base × 25 (`0x0801F4DC`) × 20 (`fn_08013694`), based on internal HSI 16 MHz PLL at 168 MHz ±1%, gated by `[0x2000016E] != 0` and `[0x200000A7] == 0`. The 50-step primary drain interval is **5.000 s nominal** (8.00 → 16.00 pts/s, or 9.25 → 17.25 pts/s when HSS is off). |
| Loosens any limit? | ⚠️ Yes, during pauses. |

### 3. Secondary burst throttle bypass (`Tier X+`)

| Item | Details |
|---|---|
| Change | File offset `0x761D`: `D3` → `E0`. At `0x0801361C`, `blo 0x08013632` becomes `b 0x08013632`. |
| Effect | ✅ Bypasses the 3000-point secondary trip branch, preventing lock byte `0x2000004A = 5` (0.5 s charge pause) and latch `0x2000004C = 1` from ever arming. Enables continuous, uninterrupted firing up to the 80-shot main threshold. |
| Loosens any limit? | ⚠️ Yes, removes the mid-burst stutter after 38 shots. |

### 4. Second heat table lowered (HSS table `0x080398F0`) (`Tier X, X+`)

| Item | Details |
|---|---|
| Change | 28 halfwords at file offset `0x2D8F0` (`0x080398F0`). |
| Original values | `25×6, 27×3, 30×4, 35×2, 45×3, 55×3, 70×3, 90×3, 100` |
| Patched values | `20×9, 25×6, 32×3, 40×3, 50×3, 64×3, 80` |
| When the table is used | ✅ Only when `0x200000DD` = 1 (`0x08013580`). |
| Is it HSS? | ✅ **Code verified end-to-end (🔶 physical optical train unverified on hardware).** The UI `'HSS'` icon (`fn_0801BD28` at `0x0801BD90`) is driven by `[0x20000E80,#3]` (`fn_0801BBE0` at `0x0801BDCC`) and bit 4 (`0x10`) of `0x2000009D`, which sets trigger mode `0x200000D5 = 0x1A` (`0x08010D28`/`0x0801FBC0`). In `fn_0801F6C0` (105-iteration pulse sequence at `0x0801F796`, `cmp r4, #0x69`) and `fn_0801F674` (`0x0801F692`), mode `0x1A` writes `1` to `0x200000DD` before calling `fn_080134E4`. Standard flash paths (`0x08016D4C`, `0x08016DB2`, and mode `0x0A`) write `0`. |
| Shots to threshold | ✅ Traced from power representation: $P=0$ corresponds to 1/1 power at top index 27. 6400 ÷ 100 = 64 shots stock, patched to 6400 ÷ 80 = 80 shots (+25%). |
| Loosens any limit? | ⚠️ Yes, in HSS mode. |

### 5. Version strings → 1.08.TT (`All profiles`)

| Item | Details |
|---|---|
| Change | File offsets `0xF738` and `0x123FC`. Each holds `v1.08` in an 8-byte slot (`v1.08` + 3 NUL bytes). The patcher replaces the whole slot with `1.08.TT` + NUL, where `TT` is the tier code (`01` S … `05` X+). The leading `v` is dropped because 7 characters is the most the slot can hold. [`tools/fwversion.py`](../tools/fwversion.py) refuses a version that doesn't fit. |
| Status | ✅ **Both screens verified in code & confirmed on hardware.** Offset `0xF738` (`0x0801B738`) is rendered inside the dedicated Device Info sub-screen (`fn_0801B6C0` at `0x0801B6FC`); offset `0x123FC` (`0x0801E3FC`) is rendered at `0x0801E25C` (EN) and `0x0801E49C` (CN) in `fn_0801DE80` as the right-aligned version preview on Row 15 (`'Device info'` / `'设备信息'`) of the Settings Menu (`MENU`) list. |

### Byte diff by profile

| File offset | Old | New | Purpose | Profile |
|---|---|---|---|---|
| `0xB4BD` | `D0` | `E0` | Fan branch (Level 2) | S, R, X, R+, X+ |
| `0x76CC` | `28` | `50` | Drain compare (80 pts) | R, X, R+, X+ |
| `0x76D0` | `28` | `50` | Drain subtract (80 pts) | R, X, R+, X+ |
| `0x7744` | `28` | `50` | Secondary drain compare (80 pts, pre-latch) | R+, X+ |
| `0x7748` | `28` | `50` | Secondary drain subtract (80 pts, pre-latch) | R+, X+ |
| `0x761D` | `D3` | `E0` | Burst throttle `blo` → `b` (`0x0801361C`) | X+ only |
| `0x2D8F0`–`0x2D927` | see §4 | see §4 | Second heat table (28 halfwords) | X, X+ |
| `0xF738`–`0xF73F` | `v1.08` | `1.08.TT` | Device info sub-screen string (`fn_0801B6C0`) | all |
| `0x123FC`–`0x12403` | `v1.08` | `1.08.TT` | Settings menu Row 15 version string (`fn_0801DE80`) ✅ | all |

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
