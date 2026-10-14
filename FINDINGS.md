# Findings: Godox Firmware Thermal & Shot-Limit Architecture

**Last audited:** 2026-10-13
**Scope:** AD600Pro II v1.08 (main focus), AD200Pro II v1.05, AD100Pro II v1.07, V100N v1.04, iT30ProN v1.02

## Status legend

| Mark | Meaning |
|---|---|
| ✅ **Verified** | Read directly from the disassembly or binary, with the address given. "Verified" means the code says this. It does **not** mean the behavior was tested on hardware. |
| 🔶 **Partial** | The instructions exist as described, but some register values or the meaning of a variable were not traced. |
| ⚠️ **Unverified** | A hypothesis, an inference, or an outside claim (manual, web) not confirmed in the code. |

Addresses are runtime addresses unless they're labeled as file offsets. File offset = address − load address.

---

## TL;DR

1. ✅ **The AD600Pro II has two protection layers:** thermistor-based protection that ends in Error E2, and a firmware heat counter that adds points per flash and forces a cooldown at 6400 points (Section 2).
2. ✅ **HSS heat tables located and traced end-to-end on all five models:** In code, enabling HSS sets bit 4 (`0x10`) of the mode byte (`0x2000009D` on AD600, `0x20000004` on AD200, `0x20000034` on AD100, `0x200004D3` on V100N, `0x2000053A` on iT30ProN), which dispatches trigger mode `0x1A` to execute a multi-pulse IGBT sequence (`105` pulses on AD600, `100` on AD200, `100`/`105` on AD100 `fn_08012334`/`fn_08017A8C`, `80` on V100N and iT30ProN) and sets the HSS table flag (`0x200000DD` → `0x080398F0` on AD600; `0x2000004B` → `0x080414FE`/`530` on AD200; `[0x20000028,#0xD]` = `0x20000035` → `0x08032F48` on AD100; `0x2000051F` → `0x08051930` on V100N; `0x20000585` → `0x0804FFAC` on iT30ProN) (Section 2.3, Section 3). Physical oscilloscope capture of the camera optical train remains 🔶.
3. ✅ **The 2× decay patch only matters during pauses.** Every flash outside cooldown resets an idle timer (1200 on AD600; 3000 on AD200, AD100, V100N, and iT30ProN), and the counter only drains after 50 timer steps (60 on iT30ProN) without a flash. Across all five models, a timer step is **0.100 s (100 ms)** (nominal ±1%, derived from internal RC oscillators), so the primary drain fires every **5.000 s** (**6.000 s** on iT30ProN). In a continuous burst the patch changes nothing. On secondary burst accumulators, 2× drain accelerates **pre-latch** pause recovery before the secondary threshold trips; once latched, clearing the latch still requires the full flash-free window (Section 2.4, Section 2.5, Section 3).
4. ✅ **The "50-shot burst table" at `0x08039A65` is verified as the Multi (stroboscopic) mode limit table** (covering 7 power levels from 1/4 to 1/256), not an HSS ceiling (Section 2.7).
5. ⚠️ **Safety concern with continuous burst counter changes (Section 4).** The heat counter exists to cover fast IGBT die heating the thermistors are too slow to catch. Raising burst limits removes margin that Error E2 cannot replace.

---

## 1. Load addresses

✅ Measured with `tools/disasm.py`, which scores candidate base addresses by how many embedded pointers land on valid code or strings. The vector tables agree with each base.

| Model | Load address | Initial SP | Reset handler |
|---|---|---|---|
| AD600Pro II | `0x0800C000` | `0x20018570` | `0x0800C1A1` |
| AD200Pro II | `0x0800C000` | `0x1000F000` | `0x0800C269` |
| AD100Pro II | `0x0800C000` | `0x2001BC00` | `0x0800C249` |
| V100N | `0x08008000` | `0x200AD678` | `0x0800829D` |
| iT30ProN | `0x0800C000` | `0x2001F3F0` | `0x0800C279` |

---

## 2. AD600Pro II thermal architecture

### 2.1 Thermistors and Error E2

Dual negative-temperature-coefficient (NTC) thermistors are monitored continuously by ADC sampling routines:
- **NTC A (`0x2000002C`, flash head / modeling-lamp sensor ✅)**: Sampled by `fn_08017120`, state stored at `0x20000144`. Directly coupled to the LED modeling lamp: when `[0x2000007B] != 0` (modeling lamp on), `0x08017126`–`0x0801713A` subtracts `10` raw ADC counts before threshold comparison, and dropping below `132.01` sets `[0x2000000C] = 1` (`0x080171B8`), which `fn_080167FC` (`0x0801686A`, `0x08016900`, `0x0801692A`) reads to throttle/shut off the modeling lamp.
- **NTC B (`0x2000002E`, main board / IGBT sensor ✅)**: Sampled by `fn_080172D8`, state stored at `0x20000145`. Uses post-flash timer `[0x20000150]` (`[0x20000144,#0xC]`) to select between `132` and `86` for forced cooldown, and exclusively triggers **Error E2** (`[0x20000147] = 1` below `49.69` counts).

Both routines read a raw `u16` ADC value, convert it to double (`bl 0x0800C510`), and compare against calibration double thresholds (`bl 0x0800C55C`). **No temperature conversion (to °C or Kelvin) exists anywhere in firmware**; the doubles represent raw ADC counts (e.g. `271.0588 = 4608/17`).
Because NTC thermistor resistance and divider voltage drop as temperature rises, **lower ADC counts correspond to higher temperatures (hot)**.

**NTC A thresholds (`0x2000002C`, `fn_08017120`, after `-10` offset when modeling lamp `0x2000007B != 0`):**

| Raw ADC count | Action / State transition | Address |
|---|---|---|
| > 970 (debounce > 10) | `[0x200000F0]=2`, `[0x20000110]=1`, state 2 (sensor open / out of range) | `0x0801714A`–`0x0801715E` |
| < 20 (debounce > 10) | `[0x200000F0]=3`, `[0x20000110]=2`, state 2 (sensor short) | `0x08017170`–`0x08017186` |
| < 132.01 (debounce > 5) | `[0x200000F0]=1`, calls **`fn_080103B4` (thermal forced cooldown)**, `[0x2000000C]=1` (throttles modeling lamp), state 2 | `0x08017198`–`0x080171C8` |
| 132.01 – 271.06 | state 2 after > 10 samples | `0x080171D0`–`0x08017200` |
| 271.06 – 356.03 | state 1 (if previously 0); clears `[0x2000000C]=0` | `0x08017204`–`0x08017230` |
| 356.03 – 404.52 | hold (hysteresis) | `0x08017234`–`0x0801726A` |
| ≥ 404.52 | state 0 (coolest / normal) | `0x0801726C`–`0x08017286` |

**NTC B thresholds (`0x2000002E`, `fn_080172D8`):**

| Raw ADC count | Action / State transition | Address |
|---|---|---|
| > 970 / < 20 | `[0x200000F1]=2 / 3` (sensor open / short) | `0x080172F4`–`0x08017324` |
| **< 49.69 (debounce > 5)** | **`[0x20000147]=1` → Error E2**, state 2 | `0x0801734E`–`0x0801736E` |
| < 132 or < 86 (threshold `r8` chosen by timer `[0x20000150]`) | debounce > 5: `[0x200000F1]=1`, calls **`fn_080103B4` forced cooldown**, state 2 | `0x0801732E`–`0x0801739A` |
| up to 271.06 | state 2 after > 10 samples | `0x080173A2`–`0x080173D4` |
| 271.06 – 311.40 | state 1 (if previously 0) | `0x080173D6`–`0x080173FA` |
| 311.40 – 356.03 | hold | `0x080173FC`–`0x0801742E` |
| ≥ 356.03 | state 0 (coolest / normal) | `0x08017430`–`0x0801744E` |

**Thermal forced cooldown (`fn_080103B4`):**
When either NTC drops below 132 ADC counts, `fn_080103B4` executes (if not already in cooldown, `0x200000DC == 0`): sets cooldown counters to 90 (~9.0 s hold), sets charge-inhibit flag `0x200000DB = 1`, post-trip window `[+0x10] = 3000` (300 s), and cooldown flag `0x200000DC = 1`. **Thus, initial over-temperature response is a forced shot-counter cooldown. Error E2 is a separate, deeper trip triggered exclusively when NTC B drops below 49.69 counts.**

**Error code dispatch (`fn_080103E0`):**
- `0x200000F2 == 1` → writes `0xE1` to `0x20000079` (**E1**)
- `0x20000147 != 0` → writes `0xE2` to `0x20000079` (**E2**, NTC B < 49.69)
- `0x200000DE == 1` → writes `0xE3` to `0x20000079` (**E3**)
- Verified at `0x08011328`–`0x08011334`: Any non-zero error code in `0x20000079` gates and inhibits capacitor charging.

### 2.2 Fan control

| Claim | Status | Evidence |
|---|---|---|
| `fn_08017480` runs its body every 21st call (unless `0x200000D5` or `0x200000E0 == 0x1A`), calls thermistor routines `fn_080172D8` and `fn_08017120`, then picks fan level (`0x20000106`) | ✅ | `0x0801748C`–`0x08017500` |
| Fan Level 2 (HIGH): set if either NTC state == 2, or shot cooldown active `0x200000DC == 1`, or `0x2000004E == 2` (`[r5,#8]` > 4000 pts or secondary throttle tripped) | ✅ | `0x080174B6`–`0x080174D2` |
| Fan Level 1 (LOW): set if either NTC state == 1, or modeling lamp active (`[0x2000007B] != 0`) at brightness `> 20%` (`[0x20000007] > 0x14`), or `0x2000004C == 1` (`[r5,#6]` secondary burst latch), or `0x2000004E == 1` (`[r5,#8]` ≥ 2000 pts) | ✅ | `0x080174D4`–`0x080174F4` |
| Fan driver `fn_08010E74`: fan off if `0x200000A6` = 1 or `0x20000080` = 1. Level 1: PC14 high, PA4 low. Level 2: PC14, PA4, PA7 high (discrete GPIO speed switching). | ✅ | `0x08010E74`–`0x08010ECA` |
| Meaning of `0x200000A6`: Low Battery Cutoff flag | ✅ | Set to 1 in `0x0800E7A8` when battery gauge is ≤ 3 (after 5 identical samples and > 15 debounce passes). Forces fan off and inhibits charging. |
| Meaning of `0x20000080`: Low-Voltage Power-Down Latch | ✅ | Set to 1 in `0x0800E690` when raw ADC `0x2000002A` is below `0x1BA` (442 counts) for > 50 debounce passes. Clears PC10/PC11, forces fan off, and inhibits charging. |
| Studio Mode patch (`0x080174BC`, `beq` → `b`) runs **after** both thermistor calls and skips only the fan-level conditional checks | ✅ | Branch follows `bl` calls at `0x080174AE` and `0x080174B2` |

### 2.3 Shot-limit heat counter: adding points (`fn_080134E4`)

Base `r5 = 0x20000046`. The accumulator is the halfword at `0x20000054` (`[r5,#0xE]`).

| Claim | Status | Evidence |
|---|---|---|
| Table index comes from `0x0803985C[power]`, where power is `0x2000009E` (mode 1 = Manual) or `0x2000009F` (mode 2 = Multi). Mode 0 (`([0x2000009D] & 3) == 0` = **TTL**) derives index from `[r5,#2]` (`0x20000048`, `0..100` TTL power computed from pre-flash metering `0x200000E1` + FEC `0x200000D4`) via thresholds → `6, 9, … 27`. | ✅ | `0x080134F6`–`0x0801356E`, `fn_08016E7C`, `fn_08019928` |
| Outside cooldown (`0x200000DC` = 0): idle timer `[r5,#0xC]` is set to 1200, then points from selected table are added | ✅ | `0x08013570`–`0x0801358A` |
| Table selection: `0x080398F0` if `0x200000DD` = 1, otherwise `0x080398B8` | ✅ | `0x08013580`–`0x080135AA` |
| Standard flash paths write 0 to `0x200000DD` immediately before calling `fn_080134E4` | ✅ | `0x08016D4C` (`fn_08016CF0`), `0x08016DB2` (`fn_08016D70`), and `0x0801F820` (`fn_0801F6C0` mode `0x0A`) |
| `0x080398F0` is the **HSS table**, selected when `0x200000DD` = 1 | ✅ | Enabling `'HSS'` (`'高速同步'`) sets `[0x20000E80,#3] = 1` and bit 4 (`0x10`) of `0x2000009D` (`0x0801394E`, `0x08017D2E`). Trigger dispatchers (`0x08017E82`, `0x080182CC`, `0x080196F6`) compute `([0x2000009D] & 0x10) \| 0x0A` → `0x1A` in `0x200000D5`. In `fn_0801F6C0`, mode `0x1A` runs a 105-iteration pulse loop (`0x0801F796`), writes `1` to `0x200000DD` (`0x0801F7C2`; also via `fn_0801F674` at `0x0801F694`), and calls `fn_080134E4`. (Hardware oscilloscope capture of optical train remains 🔶). |
| At ≥ 6400 (`0x1900`) points: cooldown counter `[r5]` = 10, `0x200000DB` = 1, `[r5,#0x10]` = 3000, `0x200000DC` = 1, then `fn_08039170` is called | ✅ | `0x0801358E`–`0x080135A0` |
| Warning levels: above 4000 points `[r5,#8]` = 2; at 2000 or more `[r5,#8]` = 1 | ✅ | `0x080135AC`–`0x080135C2` |
| Flashing during cooldown extends cooldown hold counter `[r5]` by 3 (or by 1 once above 40), capped at 80 (8.0 s), and reloads 300 s window `[r5,#0x10]` | ✅ | `0x08013522`–`0x080135DE` |
| Standard table (`0x080398B8`) entries: 3 … 80. Entry 27 is 80, giving 6400 ÷ 80 = 80 shots at 1/1. Cooldown uses `cmp` + `blo` (≥ 6400). | ✅ | Verified in code. Matches the official user manual specification. |
| Power variable ($P$) and table mapping: $P$ is stored as 1/10-stop EV decrements below 1/1 ($P=0$ is 1/1, $P=10$ is 1/2, $P=90$ is 1/512). UI formatter `fn_08016aac` formats $P=0$ as `'1'` (1/1) in fraction mode and `'10.0'` in decimal mode. Table `0x0803985C[0] = 27`. | ✅ | `0x08016aac`–`0x08016b86`, `0x0803985C` |

### 2.4 Secondary burst throttle (`[r5,#0x16]`, threshold 3000)

✅ Discovered in cross-analysis with the AD600BM II. Immediately following the primary heat accumulator addition, `fn_080134E4` executes a secondary short-window burst tracker:

| Claim | Status | Evidence |
|---|---|---|
| While unlatched (`[r5,#6] == 0`), secondary accumulator `[r5,#0x16]` accumulates points from the same table | ✅ | `0x080135EC`, `0x08013600`–`0x08013618` |
| Each flash resets a 300-step (30.0 s) window timer `[r5,#0x14]` | ✅ | `0x080135E8`, `0x080135F2`, `0x08013604` (`mov.w r1, #0x12c`, `strh r1, [r5,#0x14]`) |
| Secondary threshold: 3000 points (`0xBB8`) | ✅ | `0x0801351C` (`movw sl, #0xbb8`), `0x0801361A` (`cmp r2, sl`) |
| On trip: lock byte `[r5,#4]` (`0x2000004A`) is set to 5 (decremented every 0.1 s step at `0x08013750` for a **0.5 s charge pause**), fan demand `[r5,#8]` = 2, and latch `[r5,#6]` (`0x2000004C`) = 1 | ✅ | `0x0801361E`–`0x08013624`, `0x08013750`–`0x08013756` |
| Charge gate checks `0x2000004A`: if non-zero, calls `fn_0801243A(..., 4, 1)` to inhibit charging for those 5 steps (0.5 s) and holds off ready beep (`0x0800F3C4`) | ✅ | `0x0801135C`–`0x0801136A`, `0x0800F3C4` |
| While latched (`[r5,#6]` = 1), `fn_080134E4` skips `[r5,#0x16]` entirely, reloads `[r5,#0x14] = 300`, and re-arms `[r5,#4] = 5` on every flash at power index ≥ 24 or in HSS mode | ✅ | `0x080135EC`–`0x080135FE` |
| Secondary drain: subtracts 40 points (80 in Tier R+/X+) from `[r5,#0x16]` every 20 window timer steps (2.0 s), **but draining `[r5,#0x16]` to 0 does not clear the latch `[r5,#6]`** | ✅ | `0x0801372C`–`0x0801374F` |
| The latch `[r5,#6]` and `[r5,#0x16]` clear **only** when the 300-step (30.0 s) window `[r5,#0x14]` reaches 0 without a flash | ✅ | `0x0801372A`–`0x0801373E` (`0x0801373A: strb r3, [r4,#6]`) |
| Comparison with AD600BM II: the struct fields and drain exist, but the BM II add routine never writes them (dead code on BM II) | ✅ | BM II `fn_08012CA8` exits directly at `0x08012D06` |
| Bypass in Tier X+ (`1.08.05`): branch at `0x0801361C` changed from `blo` (`09 D3`) to `b` (`09 E0`), preventing the latch and lock from ever being set | ✅ | Unconditional branch skips lines `0x0801361E`–`0x08013626` |

In practice on stock firmware and Tiers S/R/X/R+, this throttle inserts a 0.5 s charge pause per flash starting after **~38 full-power shots** in standard mode (3000 ÷ 80) and **~30 shots** in stock HSS mode (3000 ÷ 100). **Tier R+ (`1.08.04`)** doubles the pre-latch secondary drain (20 → 40 pts/s) during pauses between shorter bursts so `[r5,#0x16]` drains twice as fast before reaching 3000; once latched, a full 30.0 s pause without flashes is still required to unlatch. In **Tier X+ (`1.08.05`)**, this throttle is completely bypassed.

### 2.5 Shot-limit heat counter: draining points (`fn_08013694`, called from `0x0801F572`)

| Claim | Status | Evidence |
|---|---|---|
| Clock source: HSI 16 MHz internal RC oscillator → PLL M=8, N=168, P=2 → SYSCLK = 168 MHz, APB1 = 42 MHz, timer clock = 84 MHz | ✅ | Configured in `0x0801ECA0`–`0x0801ECBE`. No HSE crystal is used; timing is nominal ±1% via HSI. |
| Hardware timer base: TIM14 (`0x40002000`) runs at 5.0 kHz (PSC=83, ARR=199, 200 µs period) | ✅ | Configured in `fn_0801617C`; IRQ 45 vector at `0x0800C0F4` executes `fn_0801EE58`. |
| Prescaler 1: divides TIM14 interrupts by 25 to establish a 5.0 ms (200 Hz) task tick | ✅ | `0x0801F4DC` counts to `0x19` (25) × 0.2 ms = 5.0 ms, invoking scheduler `0x0801F572`. |
| Prescaler 2: divides 5.0 ms ticks by 20 to establish a 100 ms (10 Hz) step tick | ✅ | `0x0801369A`–`0x080136A6` counts to `0x14` (20) × 5.0 ms = **0.100 s (100 ms)**. |
| Execution gating: drain routine only executes when `[0x2000016E] != 0` and `[0x200000A7] == 0` | ✅ | Verified at `0x0801F568`–`0x0801F572`. Pauses in sleep / shutdown states. |
| **Exact time per timer step = 0.100 seconds (100 ms)** (nominal ±1%) | ✅ | Hardware timer math verified: $200\,\mu\text{s} \times 25 \times 20 = 100\,\text{ms}$. |
| Idle timer `[r5,#0xC]`: decremented each pass (10 Hz). When it reaches 0 (after 1200 steps = **120.0 s / 2.0 min**) the accumulator and warning flags are cleared. | ✅ | `0x080136A8`–`0x080136C6` |
| Primary drain: when timer % 50 == 0 (**every 5.000 s**), subtract 40 from accumulator (stock: **8.00 pts/s**; Tier R/X/R+/X+: 80 points = **16.00 pts/s**) | ✅ | `0x080136B6`–`0x080136D6` |
| Extra primary drain: when `[0x20000E80+3]` = 0 (**HSS Off**, verified in `fn_0801BBE0` at `0x0801BDCC`) and timer % 40 == 0 (**every 4.000 s**), subtract 5 more (**1.25 pts/s**) | ✅ | `0x080136D8`–`0x080136F2` |
| Cooldown hold counter `[r5]`: 10 steps base (up to 80, 90 thermal). At 0, clears accumulator and unblocks charging `0x200000DB = 0`. | ✅ | `0x080136F8`–`0x0801370A` (hold time: 1.0 s to 8.0 s / 9.0 s) |
| Post-trip cooldown window `[r5,#0x10]`: 3000 steps = **300.0 s (5.0 min)** | ✅ | Decremented at `0x0801370C`. At 0, `fn_08013664` clears `0x200000DC`. While active, flashes extend hold and reload 300 s. |
| Secondary window timeout `[r5,#0x14]`: 300 steps = **30.0 s** (clears latch `[r5,#6]` and `[r5,#0x16]` at 0) | ✅ | `0x0801371E`–`0x0801373E` |
| Secondary burst drain (pre-latch): subtracts 40 points (80 in Tier R+/X+) from `[r5,#0x16]` every 20 steps (**2.000 s** = **20.0 pts/s** stock, **40.0 pts/s** Tier R+/X+) | ✅ | `0x0801372C`–`0x0801374A` |

### 2.6 Version strings

✅ `'v1.08'` appears in two 8-byte slots:
- `0x0801B738` (file offset `0xF738`), referenced at `0x0801B666` (CN) and `0x0801B68C` (EN) in `fn_0801B5A0` (**Device Info popup dialog** alongside `"Device Info"` and `"Model:"`).
- `0x0801E3FC` (file offset `0x123FC`), referenced at `0x0801E25C` (EN) and `0x0801E49C` (CN) in `fn_0801DE80` (**Settings Menu (`MENU`) list row 15**, right-aligned next to `"Device info"` / `"设备信息"`).

### 2.7 The "burst limit table" at `0x08039A65` (verified)

Audited and verified as the **Multi (stroboscopic) mode flash limit table** (maximum flashes vs. frequency vs. power) printed in the Godox AD600Pro II user manual:
- ✅ `0x20000077` is used as a divisor of 50000 to set a timer period (`0x08016DF8`–`0x08016E02`). Confirms frequency in Hz.
- ✅ The counter at `0x200000CF` is incremented per flash and compared against `0x20000076` (`0x0801B8D2`–`0x0801B8DE`). Confirms flash burst count limit.
- ✅ The table row base `0x08039AA6` ± 13·k is chosen by `[0x20000074,#0x2B]` with values 20, 30 … 80 (`0x08016C8E`–`0x08016CE6`), corresponding to 7 power levels from 1/4 to 1/256 ($P = 20 \dots 80$).
- *(Note: table `0x08039A56` referenced at `0x080138F8` and `0x0800FD44` is a separate 15-byte setting limit table, not this Multi table.)*
- ✅ Conclusion: This is the Multi-mode limit table (e.g. 7 flashes at 1/4, 20 at 1/8, up to 100 at 1/128–1/256). It is not an HSS limit.

---

## 3. AD200Pro II, AD100Pro II, V100N, and iT30ProN

All five models share a dual-tier software timer architecture yielding **0.100 s (100 ms) per timer step** (nominal ±1% based on internal oscillators), with per-flash points from power-indexed tables, second tables chosen by multi-pulse HSS flags, 6000-point cooldown thresholds (6400 on AD600Pro II, 7500 on AD200Pro II with the `H200 II` head), and idle timers reset by flashes outside cooldown. Complete 5-model comparison is tabulated in [`firmware_comparison_analysis.md`](firmware_comparison_analysis.md); detailed model breakdowns are in [`AD200ProII/README.md`](AD200ProII/README.md), [`AD100ProII/README.md`](AD100ProII/README.md), [`V100N/README.md`](V100N/README.md), and [`it30ProN/README.md`](it30ProN/README.md).

| Item | AD600Pro II (reference) | AD200Pro II | V100N |
|---|---|---|---|
| Hardware Timer Base | ✅ TIM14 (200 µs) → div 25 → 5.0 ms (HSI 16 MHz PLL, 168 MHz) | ✅ SysTick (1.0 ms) → div 5 → 5.0 ms (`fn_080193B8`, HSI 16 MHz PLL, 168 MHz) | ✅ TIM5 (1.0 ms) → div 5 → 5.0 ms (`fn_0801E520`, GD32F450/470 240 MHz, TIMERSEL set) |
| Step Prescaler | ✅ div 20 (`fn_08013694`) | ✅ div 20 (`fn_08012370`) | ✅ div 20 (`fn_0800F3F4`) |
| **Exact Step Time** | ✅ **0.100 s (100 ms)** (nominal ±1%) | ✅ **0.100 s (100 ms)** (nominal ±1%) | ✅ **0.100 s (100 ms)** |
| Execution Gating | ✅ `[0x2000016E] != 0` & `[0x200000A7] == 0` | ✅ `[0x200001F8]` bits 0 and 2 set | ✅ `[0x20000034]` bits 2 and 3 set |
| Add routine | `fn_080134E4` | ✅ `fn_08012018` | ✅ `fn_0800EFBC` (10 callers in binary) |
| Accumulator | `0x20000054` | ✅ `[0x2000015C,#0xC]` (+ `H200 II` secondary `[+0x18]`) | ✅ `[0x20000594,#8]` (+ secondary `[+0x10]`) |
| Table shape | 28 entries × 2 tables | ✅ 25 entries × 4 tables (normal/HSS × 2 head groups via `0x20000093`) | ✅ 11 rows × 22 columns × 2 tables (row from `0x200004DA`) |
| Normal table(s) | `0x080398B8` | ✅ `0x0804149A`, `0x080414CC` | ✅ `0x0805174C` |
| HSS-flag table(s) | `0x080398F0` | ✅ `0x080414FE`, `0x08041530` | ✅ `0x08051930` |
| HSS flag | ✅ `0x200000DD` | ✅ `0x2000004B` | ✅ `0x2000051F` |
| Flag set to 1 after | ✅ 105-pulse loop (`fn_0801F6C0` mode `0x1A` from HSS bit 4 of `0x2000009D`) | ✅ 100-pulse loop (`0x08013F1C`, gated by HSS bit 4 of `0x20000004` & `0x2000001A == 0`); timeout ~15 ms | ✅ 80-pulse loop (`0x0800A2D0`, `fn_0801F698` mode `0x1A` from HSS bit 4 of `0x200004D3`); timeout ~50 ms |
| Head Group / Row Meaning | Single head | ✅ `0x20000093` / `0x95`: 1=H200, 2=H200R, 3=H200J, 4=R200, 5=AD-L, 6=H200 II, 7=H200J II. {2,3,4} drain 100 pts; else 125 pts | ✅ `0x200004DA` via table `0x08051694`: Row 0 = special `0x200004DE==1` case; Rows 1–10 = 20, 24, 28, 35, 50, 70, 80, 105, 135, 200 mm |
| Cooldown threshold | 6400 | ✅ **6000** (`0x0801214A`); **7500** when `H200 II` attached (`0x20000095 == 6` via `cmp r4, #6`, plus 6000 secondary throttle `[+0x18]`) | ✅ **6000** (`0x0800F1D4`); secondary 3000 latches 0–1.5 s charge delay |
| Idle timer reset per flash | 1200 (120 s) outside cooldown | ✅ 3000 (300 s) outside cooldown (`0x080120F0`) | ✅ 3000 (300 s) outside cooldown (`0x0800F14C`) |
| Top normal entry → shots to threshold | 80 → 80 | ✅ 150 → 40 (heads 0, 1; 50 with `H200 II`); 100 → 60 (heads 2, 3, 4) | ✅ 86 → 70 (wide 20–35mm); 60 → 100 (tele 105–200mm) |
| Top HSS entry → shots to threshold | 100 → 64 | ✅ 185 → 33 (heads 0, 1; 41 with `H200 II`); 120 → 50 (heads 2, 3, 4) | ✅ 100 → 60 |
| Drain routine | −40 / 5.0 s (8.0 pts/s) | ✅ `fn_08012370`: −125 / 5.0 s (25.0 pts/s), −100 / 5.0 s (20.0 pts/s heads {2,3,4}); `H200 II` secondary −165 / 5.0 s (33.0 pts/s) | ✅ `fn_0800F3F4`: −50 / 5.0 s (10.0 pts/s on primary & pre-latch secondary) |
| Firmware fan control | ✅ `fn_08017480` | ✅ Body chassis fanless; body controls `H200 II` head fan via bit-banged I2C slave `0x5C` reg `0x01` (`fn_080237B0` at `0x080238C8`) | ⚠️ None located in firmware (fanless speedlite) |
| Hardware thermal sensor protection | ✅ Dual NTC thermistors (raw ADC: NTC B < 49.69 → E2; NTC A/B < 132 → forced cooldown) | ✅ Analog head NTC on ADC `0x200000AE` (`fn_08015C78`: < 75 severe, < 132 forced cooldown `fn_0800E1E4`) + `H200 II` digital NTC on I2C reg `0x06` (`[0x200001E6]` in `fn_080237B0`: < 260 severe, < 396 forced cooldown) | ✅ Real NTC path via ADC0 DMA (`0x200004B6`): < 98.98 raw count forces cooldown trip (`fn_0800D544`), recovers at ≥ 176.3 |

Shot counts assume a continuous burst from an empty counter in Manual mode. ✅ Verified: the top table index on all five models corresponds to 1/1 power, proven by tracing the UI power formatting routines (`fn_08016aac` / `0x08014914` / `fn_08010fec` / `fn_08011670` / `fn_080109bc`), their internal 1/10-stop EV representation ($P=0$ = 1/1), and the power-to-index lookup tables. All models evaluate the cooldown threshold with `cmp` + `blo` ($\ge \text{threshold}$), confirming exact integer shot limits ($\lceil \text{threshold} / \text{cost} \rceil$).

---

## 4. Why the heat counter matters for safety

⚠️ This is engineering reasoning, not a measurement.

- **What the counter covers:** in a burst, especially in HSS, the IGBT's silicon die heats within milliseconds. Heat takes seconds to reach a thermistor on the board or heatsink, so the counter limits shots before the sensors can react.
- **Why E2 doesn't replace it:** E2 is driven by those same slow sensors. Raising the counter's limits therefore removes margin that E2 can't make up.
- **Why the fan doesn't replace it:** a fan cools the heatsink. Over milliseconds, die temperature depends on the chip-to-case thermal path, which airflow barely changes.
- **Why AC power doesn't change it:** the IGBT heats from the flash discharge itself, regardless of the power source.
- **What's at stake:** these units switch a 350–450 V capacitor bank. A failed IGBT can short, damage the board, or start a fire.

The fan-only change (Section 2.2) adds cooling without changing any limit.

---

## 5. Practical options that don't change protection logic

- **Fan always on (firmware):** a single branch patch at `0x080174BC` on AD600Pro II (Section 2.2) or `0x080143A2` on AD100Pro II.
- **Remote head:** the H600P extension head moves the flash tube away from the body electronics.
- **Modeling lamp off during bursts:** removes a continuous heat source from the head.
- **Two strobes at lower power instead of one at full:** the same total light, with less heat per unit.
- **Thermal paste:** renewing the IGBT/diode thermal interface material lowers the die-to-heatsink resistance.

Earlier versions of this file gave percentage gains for these options. Those figures had no source and have been removed.

---

## 6. Open questions

1. 🔶 Confirm on physical hardware with an oscilloscope that the multi-pulse paths (`0x1A` on AD600, 100-pulse on AD200, 100/105-pulse on AD100, 80-pulse on V100 and iT30ProN) match camera HSS optical trigger trains. End-to-end firmware code paths from UI HSS settings to table selection are verified in §2.3 and §3.
2. ✅ **[Solved]** Updater/bootloader checksum verification: Disassembly of `Godox_G3_v1.1.exe` (`0x00404D1B`) confirms G3 only checks `file_size <= 1 MB` (`0x100000`) and performs no checksum, MD5, or signature check, streaming raw 1 KB blocks over USB HID to the device bootloader. AD600Pro II, AD200Pro II, AD100Pro II, and V100N have no image checksum; `iT30ProN` has a 44-byte MD5 footer at `0xA8000` verified on-device by its bootloader (or a newer host tool).
3. ✅ **[Solved]** Mode 0 table index derivation (TTL algorithmic power determination): `([0x2000009D] & 3) == 0` is TTL mode; flash duration routines combine pre-flash metering (`0x200000E1` on AD600) and FEC (`0x200000D4`) into a normalized `0..100` power value (`0x20000048` on AD600, `0x2000015C` on AD200, `0x2000002A` on AD100, `0x2000055B` on V100N, `0x200005C2` on iT30ProN) mapped to heat table indices via threshold ladders (§2.3).
4. ✅ **[Solved]** Thermistor sensor assignments on AD600Pro II: NTC A (`0x2000002C`, `fn_08017120`) is coupled to the LED modeling lamp (`-10` ADC count offset when lamp is on; throttles/shuts off lamp via `0x2000000C = 1` below 132.01 → flash head / modeling-lamp sensor), while NTC B (`0x2000002E`, `fn_080172D8`) triggers Error E2 below 49.69 (main board / IGBT sensor) (§2.1).
5. ✅ **[Solved]** AD200Pro II thermal sensors & `H200 II` fan control: `0x200000A4` (`fn_0800C8EC`, `< 541.42`) is verified as the battery voltage monitor (`fn_0800CD40` battery bars & low-battery power-off). Real overheat sensors are ADC `0x200000AE` (`fn_08015C78` for analog heads) and `H200 II` digital NTC `[0x200001E6]` read via bit-banged I2C slave `0x5C` reg `0x06` in `fn_080237B0` (which also controls the `H200 II` cooling fan via I2C reg `0x01`) (§3).
6. ✅ **[Solved]** Step timer tick period: traced and confirmed across all five models (§2.5, §3). 1 timer step = 0.100 s (100 ms) nominal.
7. ✅ **[Solved]** Thermistor trip logic on AD600Pro II: raw ADC thresholds (NTC B < 49.69 trips E2; NTC A/B < 132 trips 9 s forced cooldown; fan stages at < 271 and < 356) (§2.1).
8. ✅ **[Solved]** Power monitor flags on AD600Pro II: `0x200000A6` (low battery gauge ≤ 3) and `0x20000080` (low voltage latch ADC < 0x1BA) (§2.2).
9. ✅ **[Solved]** Power → table-index mapping in Manual mode: traced and confirmed across all five models (§2.3, §3). Stored as 1/10-stop EV decrements below 1/1 ($P=0$ maps to top indices 27, 24, 24, 21, 21).
10. ✅ **[Solved]** AD200Pro II head IDs (`0x20000093` / `0x95`): 1=H200, 2=H200R, 3=H200J, 4=R200, 5=AD-L, 6=H200 II, 7=H200J II; Head code `6` (`H200 II` only, via `cmp r4, #6`) raises primary threshold to 7500 and enables the 6000-point secondary `H200 II` burst throttle `[r5,#0x18]` (§3).
11. ✅ **[Solved]** V100N zoom row mapping (`0x200004DA`): Row 0 = special `0x200004DE` flag, Rows 1–10 = 20mm to 200mm via `0x08051694`; Secondary accumulator latches hard charge inhibit of 0–1.5 s via `fn_0800E52C` charger-off GPIO; `0x20000037` bit 2 is a rapid-recycle detector (`< 75%` expected full-charge time from `0x0805169E`) (§3).
12. ✅ **[Solved]** V100N hardware thermal sensor: traced to ADC0 DMA reading at `0x200004B6` (raw ADC < 98.98 forces cooldown trip) (§3).
13. ✅ **[Solved]** AD100Pro II row selector (`[0x20000001] & 7` = 5-step Zoom Focal Length `28, 35, 50, 70, 85` mm in `fn_08013718` / `fn_08016024`), Table Set 2 HSS flag setter (`[0x20000028,#0xD]` set in `fn_08012334` and `fn_08017A8C`), and 84 MHz APB1 timer clock (`fn_08016E8C`).
14. ✅ **[Solved]** iT30ProN 84 MHz TIM4 clock (`fn_08021534`), column-to-power mapping (`fn_080109BC`), `0x200005B9` status-bar diffuser icon (`0x08045B0C`), and `0x2000007B` dead/vestigial bits.

---

## 7. Repository actions
 
| Action | Location |
|---|---|
| Disassembled and audited binaries with validated load addresses | `<Model>/disasm/` |
| Added multi-profile patchers (Tiers S, R, X, R+, X+) | `<Model>/patch.py` |
| Switched to the `<Godox version>.<tier code>` version scheme (2026-10-10), shared by all patchers | [`tools/fwversion.py`](tools/fwversion.py), [README §1](README.md#1-firmware-profiles--version-scheme) |
| Restoring official OEM factory firmware with G3: confirmed working on hardware (2026-10-09) | — |
