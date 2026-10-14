# Godox AD100Pro II

| Item | Value |
|---|---|
| OEM image | `AD100ProII_RF433V1_07.bin` (357,004 bytes), SHA-256 `5dd2dd434e0ca531a57fd5ad397a9de1cf4e8acf2374aa6bfc5d7fed17c135dc`. Not posted on Godox's public firmware page; obtain it from Godox support / an authorized channel. |
| Custom builds | `AD100ProII_V1.07.01_studio.bin` (Tier S), `AD100ProII_V1.07.02_recovery.bin` (Tier R), `AD100ProII_V1.07.03_super.bin` (Tier X) — **Tier R (`1.07.02`) flashed via G3; continuous fan and version display on both screens confirmed on hardware (2026-10-11)**; Tiers S and X not yet flashed |
| Patcher | [`patch.py`](patch.py) (version scheme: [root README §1](../README.md#1-firmware-profiles--version-scheme)) |
| Technical classification | [`../TIERED_RATINGS.md`](../TIERED_RATINGS.md) |

Status marks: ✅ verified in code · 🔶 partial · ⚠️ unverified ([legend](../FINDINGS.md#status-legend)). File offset = address − `0x0800C000`.

---

## 1. Heat Counter: Adding Points (`fn_08010fec`)

Base pointer `r6 = 0x20000028`. Primary accumulator = halfword `[+0x20]` (`0x20000048`), secondary accumulator = halfword `[+0x28]` (`0x20000050`).

| Claim | Status | Evidence |
|---|---|---|
| Row = `[0x20000001] & 7`. `[0x20000001]` is the **5-step Zoom Focal Length index (`0..4` = `28, 35, 50, 70, 85` mm)**: clamped to `0..4` in `fn_08013718` (`0x08013BF4`) and formatted into `"%2dmm"` via table `0x080340F4` (`[28, 35, 50, 70, 85]`) in `fn_08016024` (`0x080160BA`). Only rows 0–4 are reachable in normal operation (rows 5–10 are unused padding). | ✅ | `0x08011008`–`0x08011028`, `0x08013BF4`, `0x080160BA` |
| Column (0–24): normally `byte_table_0x08032CD0[P]` with `P` from `0x20000116` or `0x20000117`. The table maps `P = 0` → **24** and falls by one column about every 3⅓ steps (`P` in 1/10 stops, the same scheme as the other models), so **column 24 = 1/1**. When the low 2 bits of `[0x20000034]` are 0 (**TTL mode** ✅), the column comes from thresholds on `[0x2000002A]` instead (40/50/…/100 → 3/6/…/24, computed from TTL pre-flash metering). | ✅ | `0x08010FF2`–`0x080110A6`, table `0x08032CD0` |
| When not in cooldown (`[+0x0B] == 0`): idle timer `[+0x1E]` = **3000** (300 s) on every flash, then points are added to `[+0x20]` | ✅ | `0x080110A8`–`0x080110BC` |
| **Primary cooldown threshold: 6000 points** (`0x1770`, `cmp` + `blo`) | ✅ | `0x080110C0`–`0x080110C6` |
| At the threshold: `[+0]` = 10 (1.0 s), charge-inhibit flag `0x2000007B` = 1, 300 s window `[+0x22]` = 3000, trip flag `[+0x0B]` = 1 | ✅ | `0x080110C8`–`0x080110DC` |
| During the 300 s window, each flash adds 3 to `[+1]` (capped at 50) and reloads `[+0]` from it, i.e. a growing per-flash recycle lockout of up to 5.0 s. Lower columns get smaller caps (`0x080110E8`–`0x08011118`). This is a throttled window, not a hard 300 s lockout. | ✅ | `0x08011040`–`0x08011058` |
| **Secondary accumulator `[+0x28]`:** timer `[+0x26]` = **1800** (180 s), **threshold 3200** (`0x0C80`). On trip (`0x08011162`), latch `[+6]` = 1 and recycle delay `[+4]` = 5 (0.5 s); while latched (`[+6] == 1`), each later flash branches to `0x08011120` (bypassing `[+0x28]`), raises `[+4]` by 1 (by 5 when `[0x20000035] == 1`), capped at 15 steps (1.5 s), and reloads `[+0x26] = 1800`. Latch `[+6]` only clears when `[+0x26]` reaches 0 (180 s without flashes at `0x0801126E`). | ✅ | `0x0801111A`–`0x08011180`, `0x08011254`–`0x08011283` |

---

## 2. Cost Tables

Both tables are 11 rows × 25 halfwords (50 bytes per row). Rows 0–4 correspond to zoom positions `28, 35, 50, 70, 85` mm (rows 5–10 are unused padding with identical values to Row 4).

### Table Set 1 (`0x08032D22`, file offset `0x26D22`), used when `[0x20000035] != 1` (Normal mode)
* **Row 0 (`28 mm`):** `[1, 1, 1, 3, 3, 3, 6, 6, 6, 12, 12, 12, 24, 24, 24, 36, 36, 36, 50, 60, 60, 60, 70, 80, 100]` → 1/1 = 100 pts → **60 shots** to 6000 (secondary throttle at 32 shots).
* **Row 1 (`35 mm`):** top 90 → **67 shots** (`66 × 90 = 5940 < 6000`, 67th = 6030). **Row 2 (`50 mm`):** top 80 → **75 shots**. **Row 3 (`70 mm`):** top 70 → **86 shots** (`85 × 70 = 5950 < 6000`, 86th = 6020).
* **Row 4 (`85 mm`, and padding rows 5–7):** top 60 → **100 shots** (secondary throttle at 54 shots).
* ✅ This directly explains why wide zoom (`28 mm`, 100 pts/shot = 60 shots) vs. tele zoom (`85 mm`, 60 pts/shot = 100 shots) spans **60–100 full-power flashes**.

### Table Set 2 (`0x08032F48`, file offset `0x26F48`), used when `[0x20000035] == 1` (HSS mode) ✅
* **Rows 0–9:** `[22, 22, 22, 22, 22, 22, 36, 36, 36, 46, 46, 46, 60, 60, 60, 60, 70, 70, 70, 86, 86, 86, 100, 100, 100]` → **60 shots** at 1/1 (secondary throttle at 32 shots). Row 10 differs in one entry (unreachable).
* ✅ **Code verified as the HSS table (🔶 physical optical train unverified on hardware).** The flag at `0x20000035` (`[r5,#0xD]` where `r5 = 0x20000028`) is set to `1` (with timeout `[+0x24] = 3`) in two places right before calling `fn_08010fec`:
  1. **On-camera HSS flash (`fn_08012334` at `0x08012446`):** `strb r0, [r5, #0xd]` immediately after a 100-iteration pulse loop (`0x08012420`–`0x0801243E`, `cmp r4, #0x64`), gated by `0x20000002 == 0` and bit 4 (`0x10`, HSS icon) of `0x20000034`.
  2. **Wireless/remote HSS flash (`fn_08017A8C` at `0x08017B9A`):** `strb r0, [r5, #0xd]` immediately after a 105-iteration pulse loop (`0x08017B74`–`0x08017B92`, `cmp r4, #0x69`) when trigger mode `0x20000039 == 0x1A`.
  Single-pulse flash paths (`0x08012572`, `0x08013426`, `0x08013582`, `0x08017D0A`) write `0` to `[r5,#0xD]`, and the drain routine clears it when the `[+0x24]` timeout reaches 0 (`0x0801128C`–`0x08011296`).

---

## 3. Leaky-Bucket Drain (`fn_080111f4`)

| Claim | Status | Evidence |
|---|---|---|
| Tick source: TIM14 (vector slot 61 = IRQ 45), configured at `0x0801297C` with PSC 83 / ARR 199 → **200.0 µs** on an **84 MHz APB1 timer clock** (`fn_08016E8C`: HSI 16 MHz → PLLM=8, PLLN=168, PLLP=2 → SYSCLK 168 MHz, APB1 DIV4 → 84 MHz TIM clock; dynamically rescaled to PSC=27 at 28 MHz in sleep `0x08016DE6`). ISR `0x08017000` → `fn_080175d8` divides by 25 → 5.0 ms → drain prescaler `[+9]` divides by 20 | ✅ | `fn_08016E8C` (`0x08016E8C`–`0x08016F10`), `0x0801297C`–`0x08012996`, `0x080175E2`, `0x080111FA` |
| **Step = 0.100 s nominal**, gated by `[0x20000131] != 0` | ✅ | `0x0801765E`–`0x08017668` |
| Primary: `[+0x1E]` counts down; when `timer % 50 == 0` (every 5.0 s) subtract **25** (or clear if < 25); the accumulator is cleared when the timer reaches 0 (300 s idle) | ✅ | `0x08011208`–`0x0801122E` (**5.0 pts/s stock**, 10.0 pts/s Tier R/X) |
| Secondary: `[+0x26]` counts down; every 5.0 s subtract **30** from `[+0x28]` (accelerating **pre-latch `[+6] == 0` recovery** between bursts); at 0 (180 s idle with zero flashes) clear latch `[+6]`, `[+0x28]` and `[+4]` | ✅ | `0x08011254`–`0x08011283` (**6.0 pts/s stock**, 12.0 pts/s Tier R/X) |
| `[+0x22]` (300 s window) expiry calls `fn_080111c8`, which clears trip flags **and both the primary timer and accumulator** | ✅ | `0x08011242`–`0x08011250`, `0x080111C8`–`0x080111E6` |

---

## 4. Fan and Thermistor

### 4.1 Thermistor (`fn_08014234`, called every 21st pass of `fn_08014370`)
Reads the raw ADC halfword at `0x20000010`. As on the AD600Pro II, a lower count means hotter, and there is **no temperature conversion**: `fn_0803228a` is the compiler's `uint → double` helper (`__aeabi_ui2d`) and `fn_080322b0` is a double compare.

| Raw ADC count | Action | Status |
|---|---|---|
| > 950 (debounce > 10) | `[0x2000009E]` = 2 (shown as `NTC:E1` in the self-test), `[0x200000A0]` = 1, fan state 2 | ✅ |
| < 20 (debounce > 10) | `[0x2000009E]` = 3 (`NTC:E2`), `[0x200000A0]` = 2, fan state 2 | ✅ |
| < 114.59 (debounce > 10) | **Forced cooldown** via `fn_0800e178` (same 300 s throttled window as a counter trip, charge inhibit `0x2000007B`), `[0x20000139]` = 1 | ✅ |
| 114.59 – 204.14 | hold (hysteresis) | ✅ |
| ≥ 204.14 | if previously tripped: `fn_080111c8` (exits cooldown and clears the primary accumulator) | ✅ |
| < 271.06 (debounce > 10) | fan state `[0x20000093]` = 2 | ✅ |
| 271.06 – 356.03 | fan state 1 | ✅ |
| ≥ 356.03 | fan state 0 | ✅ |

Which physical component the thermistor sits on is unknown ⚠️.

### 4.2 Fan control (`fn_08014370`, main loop `0x0802C1FE`)
The fan is on **GPIOC pin 4** (`0x40020800`, mask `0x10`), driven through `fn_080100a2` (writes BSRR). The factory self-test (`fn_08017468`) toggles the same pin while showing `FAN:1` / `FAN:OFF`. During normal operation `fn_08014370` is the only PC4 writer. The other `mask 0x10` writes go to GPIOE/GPIOB, and the remaining GPIOC PC4 write at `0x080148EC` sits in a shutdown/peripheral-off sequence.

| Condition (evaluated in order) | Fan | Status |
|---|---|---|
| `[0x20000039]` or `[0x2000003E]` == `0x1A` | function returns; fan left as is (**active HSS pulse train** in progress ✅) | ✅ |
| `[0x2000007A]` == 1 | **off**. **Critically low battery cutoff** (`ADC 0x2000000C < 504.4` in `fn_0800CB78` at `0x0800CC04` ✅); also blocks firing (`fn_08014194`) and switches the UI to low-battery state 8 | ✅ |
| NTC state, `[0x20000094]`, `[0x20000096]` and the primary accumulator all 0 | off | ✅ |
| NTC state == 2 (raw < 271.06 or sensor fault) | **on** | ✅ |
| Primary accumulator > **1200** | **on** | ✅ |
| `[0x200000C7]` ≥ 5 and `[0x20000096]` == 1 (**modeling lamp brightness ≥ 60% while active** ✅), or `[0x20000033]` == 1 | **on** | ✅ |
| otherwise (including NTC state 1 by itself) | off. There is no hysteresis: the fan stops as soon as the accumulator drops back to ≤ 1200 | ✅ |

---

## 5. Custom Firmware Profiles

### Version display
The version is stored as the literal text `"V1.07\0\0\0"` in two 8-byte slots, each printed through `"%s"`:
* **Settings menu:** file offset `0x239FC` (`ADR r2` at `0x0802F91A`).
* **Device Info:** file offset `0x24484` (`ADR r2` at `0x080302D6`).

Both are rewritten to the 7-character build version (`"1.07.02\0"`), without the leading `V`, as on the AD600Pro II. ✅ Both screens confirmed showing `1.07.02` on hardware (2026-10-11). The other `%d.%d%d` strings in the image are time readouts (`…s` / `…秒`), not versions.

### Tier S: Studio (`AD100ProII_V1.07.01_studio.bin`, `1.07.01`)
* `0x080143A2` (file `0x83A2`): `ldrb r1, [r5]` (`29 78`) → `b 0x080143EE` (`24 E0`), the fan-on block. The thermistor call (`0x08014394`), the `0x1A` HSS early return and the `0x2000007A` low-battery fan-off check all run **before** the patch point, so they still work.
* Every heat limit stays stock.

### Tier R: Recovery (`AD100ProII_V1.07.02_recovery.bin`, `1.07.02`) — ✅ flashed, fan confirmed on hardware (2026-10-11)
* Tier S fan patch.
* Primary drain `25` → `50` (`0x5224`, `0x5228`); secondary drain `30` → `60` (`0x5278`, `0x527C`, accelerating pre-latch `[+6] == 0` recovery between bursts; once latched at 3200 pts, `[+6]` clears after 180 s idle).
* Single-burst limits stay stock. The 300 s / 180 s idle clears are unchanged, so Tier R only matters for pauses shorter than those.

### Tier X: Super (`AD100ProII_V1.07.03_super.bin`, `1.07.03`) ✅
* Tier R changes.
* Table Set 2 (`0x26F48`, all 11 rows) lowered by about 20%: `100→80, 86→69, 70→56, 60→48, 46→37, 36→29, 22→18`. At 1/1 in HSS mode (`[0x20000035] == 1`) this gives **60 → 75 shots** to primary cooldown (and **32 → 40 shots** to the 3200-pt secondary throttle).
