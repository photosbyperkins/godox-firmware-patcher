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
| Row = `[0x20000001] & 7`. Only rows 0–7 are reachable, although each table physically holds 11 rows (`0x226` = 11 × 50 bytes). What the row represents is unknown. | ✅ / ⚠️ meaning | `0x08011008`–`0x08011028` |
| Column (0–24): normally `byte_table_0x08032CD0[P]` with `P` from `0x20000116` or `0x20000117`. The table maps `P = 0` → **24** and falls by one column about every 3⅓ steps (`P` in 1/10 stops, the same scheme as the other models), so **column 24 = 1/1**. When the low 2 bits of `[0x20000034]` are 0, the column comes from thresholds on `[0x2000002A]` instead (40/50/…/100 → 3/6/…/24). | ✅ | `0x08010FF2`–`0x080110A6`, table `0x08032CD0` |
| When not in cooldown (`[+0x0B] == 0`): idle timer `[+0x1E]` = **3000** (300 s) on every flash, then points are added to `[+0x20]` | ✅ | `0x080110A8`–`0x080110BC` |
| **Primary cooldown threshold: 6000 points** (`0x1770`, `cmp` + `blo`) | ✅ | `0x080110C0`–`0x080110C6` |
| At the threshold: `[+0]` = 10 (1.0 s), charge-inhibit flag `0x2000007B` = 1, 300 s window `[+0x22]` = 3000, trip flag `[+0x0B]` = 1 | ✅ | `0x080110C8`–`0x080110DC` |
| During the 300 s window, each flash adds 3 to `[+1]` (capped at 50) and reloads `[+0]` from it, i.e. a growing per-flash recycle lockout of up to 5.0 s. Lower columns get smaller caps (`0x080110E8`–`0x08011118`). This is a throttled window, not a hard 300 s lockout. | ✅ | `0x08011040`–`0x08011058` |
| **Secondary accumulator `[+0x28]`:** timer `[+0x26]` = **1800** (180 s), **threshold 3200** (`0x0C80`). On trip, `[+6]` = 1 and recycle delay `[+4]` = 5; each later flash raises it by 1 (by 5 with the table-2 flag), capped at 15 steps | ✅ | `0x0801111A`–`0x08011180` |

---

## 2. Cost Tables

Both tables are 11 rows × 25 halfwords (50 bytes per row). Only rows 0–7 are reachable (see above).

### Table Set 1 (`0x08032D22`, file offset `0x26D22`), used when `[0x20000035] != 1`
* **Row 0:** `[1, 1, 1, 3, 3, 3, 6, 6, 6, 12, 12, 12, 24, 24, 24, 36, 36, 36, 50, 60, 60, 60, 70, 80, 100]` → 1/1 = 100 pts → **60 shots** to 6000.
* **Row 1:** top 90 → 66 shots. **Row 2:** top 80 → 75 shots. **Row 3:** top 70 → 85 shots.
* **Rows 4–7:** top 60 → **100 shots**.
* ⚠️ Godox's rating of "60–100 full-power flashes" (from a web summary, not a Godox spec sheet) fits this 60–100 spread, but what the row means hasn't been traced.

### Table Set 2 (`0x08032F48`, file offset `0x26F48`), used when `[0x20000035] == 1` 🔶
* **Rows 0–9:** `[22, 22, 22, 22, 22, 22, 36, 36, 36, 46, 46, 46, 60, 60, 60, 60, 70, 70, 70, 86, 86, 86, 100, 100, 100]` → **60 shots** at 1/1. Row 10 differs in one entry (unreachable).
* 🔶 **Probably the HSS table, but not proven.** The flag at `0x20000035` (`[+0xD]`) is cleared by the drain routine when the `[+0x24]` timeout runs out (`0x0801128C`–`0x08011296`). That is the same pattern as the multi-pulse flags on the AD600/AD200/V100N, and the high floor cost (22 pts even at 1/256) fits pulsed output. **The code that sets the flag to 1 has not been located**, so the HSS meaning is unconfirmed.

---

## 3. Leaky-Bucket Drain (`fn_080111f4`)

| Claim | Status | Evidence |
|---|---|---|
| Tick source: TIM14 (vector slot 61 = IRQ 45), set up at `0x0801297C` with PSC 83 / ARR 199 → 200 µs, assuming an 84 MHz APB1 timer clock (RCC not traced). ISR `0x08017000` → `fn_080175d8` divides by 25 → 5 ms → drain prescaler `[+9]` divides by 20 | 🔶 clock assumed | `0x0801297C`–`0x08012996`, `0x080175E2`, `0x08017646`, `0x080111FA` |
| **Step = 0.100 s nominal**, gated by `[0x20000131] != 0` | 🔶 | `0x0801765E`–`0x08017668` |
| Primary: `[+0x1E]` counts down; when `timer % 50 == 0` (every 5.0 s) subtract **25** (or clear if < 25); the accumulator is cleared when the timer reaches 0 (300 s idle) | ✅ | `0x08011208`–`0x0801122E` (**5.0 pts/s stock**, 10.0 pts/s Tier R/X) |
| Secondary: `[+0x26]` counts down; every 5.0 s subtract **30**; at 0 (180 s idle) clear `[+6]`, `[+0x28]` and `[+4]` | ✅ | `0x08011254`–`0x08011282` (**6.0 pts/s stock**, 12.0 pts/s Tier R/X) |
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
| `[0x20000039]` or `[0x2000003E]` == `0x1A` | function returns; fan left as is (mode meaning unknown ⚠️) | ✅ |
| `[0x2000007A]` == 1 | **off**. This global inhibit flag also blocks firing (`fn_08014194`) and switches the UI to state 8. Its exact meaning is unverified ⚠️ | ✅ |
| NTC state, `[0x20000094]`, `[0x20000096]` and the primary accumulator all 0 | off | ✅ |
| NTC state == 2 (raw < 271.06 or sensor fault) | **on** | ✅ |
| Primary accumulator > **1200** | **on** | ✅ |
| `[0x200000C7]` ≥ 5 and `[0x20000096]` == 1, or `[0x20000033]` == 1 | **on** | ✅ |
| otherwise (including NTC state 1 by itself) | off. There is no hysteresis: the fan stops as soon as the accumulator drops back to ≤ 1200 | ✅ |

---

## 5. Custom Firmware Profiles

### Version display
The version is stored as the literal text `"V1.07\0\0\0"` in two 8-byte slots, each printed through `"%s"`:
* **Settings menu:** file offset `0x239FC` (`ADR r2` at `0x0802F91A`).
* **Device Info:** file offset `0x24484` (`ADR r2` at `0x080302D6`).

Both are rewritten to the 7-character build version (`"1.07.02\0"`), without the leading `V`, as on the AD600Pro II. ✅ Both screens confirmed showing `1.07.02` on hardware (2026-10-11). The other `%d.%d%d` strings in the image are time readouts (`…s` / `…秒`), not versions.

### Tier S: Studio (`AD100ProII_V1.07.01_studio.bin`, `1.07.01`)
* `0x080143A2` (file `0x83A2`): `ldrb r1, [r5]` (`29 78`) → `b 0x080143EE` (`24 E0`), the fan-on block. The thermistor call (`0x08014394`), the `0x1A` early return and the `0x2000007A` fan-off check all run **before** the patch point, so they still work.
* Every heat limit stays stock.

### Tier R: Recovery (`AD100ProII_V1.07.02_recovery.bin`, `1.07.02`) — ✅ flashed, fan confirmed on hardware (2026-10-11)
* Tier S fan patch.
* Primary drain `25` → `50` (`0x5224`, `0x5228`); secondary drain `30` → `60` (`0x5278`, `0x527C`).
* Single-burst limits stay stock. The 300 s / 180 s idle clears are unchanged, so Tier R only matters for pauses shorter than those.

### Tier X: Super (`AD100ProII_V1.07.03_super.bin`, `1.07.03`) 🔶
* Tier R changes.
* Table Set 2 (`0x26F48`, all 11 rows) lowered by about 20%: `100→80, 86→69, 70→56, 60→48, 46→37, 36→29, 22→18`. At 1/1 this gives **60 → 75 shots** while the table-2 flag is set.
* 🔶 This only helps HSS if Table Set 2 really is the HSS table (see §2).
