# Godox iT30ProN

| Item | Value |
|---|---|
| OEM image | `iT30ProN_V1.02.bin` (688,172 bytes), SHA-256 `a6920833d267834e7ff41f537ce8b897bab47234013731ae79b4affcbf41847e` |
| Custom builds | `iT30ProN_V1.02.02_recovery.bin` (Tier R), `iT30ProN_V1.02.03_super.bin` (Tier X) — **flashing & version display confirmed on hardware** (2026-10-10) |
| Patcher | [`patch.py`](patch.py) (version scheme: [root README §1](../README.md#1-firmware-profiles--version-scheme)) |
| Technical classification | [`../TIERED_RATINGS.md`](../TIERED_RATINGS.md) |

Status marks: ✅ verified in code · 🔶 partial · ⚠️ unverified. File offset = address − `0x0800C000`.

> [!IMPORTANT]
> **This is the only model in the repo with an integrity footer.** The last 44 bytes hold an MD5 of the image. Every patched build recomputes it automatically in `patch.py`. Unofficial builds without a valid recomputed MD5 will have a stale checksum and must not be flashed.

## Image layout

| Claim | Status | Evidence |
|---|---|---|
| Load address `0x0800C000`, initial SP `0x2001F3F0`, reset `0x0800C279` | ✅ | Vector table. `--detect` scores 281 against 61 for the next candidate. `fn_08021660` writes `0x0800C000` to VTOR |
| Cortex-M4F with the FPU enabled | ✅ | `fn_08021660` sets CPACR bits 20–23. VFP instructions are used (e.g. `0x08013E5E`) |
| Code/data payload ends at file offset `0xA48C8`, then `0xFF` padding up to `0xA8000` | ✅ | Byte scan |
| **Footer at `0xA8000`:** 16-byte MD5 of `file[0:0xA8000]`, the 18-byte name `iT30ProN_V1.02.bin`, a u16 length (`0x0012`), then the magic `AA 55 66 99 77 88 22 33` | ✅ | MD5 recomputed and matches |
| The MD5 is checked by the G3 updater and/or the bootloader, not by the application | 🔶 | The app has no MD5 constants (`0x67452301` is absent) and no reference to the magic. Which component actually checks it is unknown |

## Heat counter: struct at `0x200005F4`

| Field | Meaning | Status |
|---|---|---|
| `[+0]` byte | Per-flash **charge lockout** countdown in 100 ms steps. `0x20000583` is cleared when it reaches 0 | ✅ `0x0801416E` |
| `[+1]` byte | Lockout length while in cooldown: +10 per flash, capped at 70 (7.0 s), then capped per column at 6/8/10/15/20/30/50 | ✅ `0x08013C8E`–`0x08013CA8`, `0x08013DC4`–`0x08013E56` |
| `[+2]` byte | Charge-inhibit delay from the **secondary** accumulator (100 ms steps) | ✅ `0x08013FE8`; read by the charge gate `fn_0800D89C` |
| `[+3]` byte | Secondary throttle is active | ✅ `0x08013F2A`, cleared at `0x080141D8` |
| `[+4]` byte | Prescaler: 20 × 5 ms = 100 ms step | ✅ `0x08014132`–`0x0801413C` |
| `[+6]` half | Primary idle timer. Set to **3000** (300 s) on each flash outside cooldown. Clears `[+8]` when it reaches 0 | ✅ `0x08013CEC`, `0x08014162` |
| `[+8]` half | **Primary accumulator.** Cooldown starts at **≥ 6000** | ✅ `0x08013D54` (`cmp` + `blo`) |
| `[+0xA]` half | Cooldown window, set to **6000** (600 s). Each flash during cooldown restarts it. At 0, `fn_080140F4` resets everything | ✅ `0x08013CBC`, `0x08013D60`, `0x0801418E` |
| `[+0xC]` half | Timeout for the table-select flag: 10 × 5 ms | ✅ `0x0800D3AA`, `0x080141BA` |
| `[+0xE]` half | Secondary idle timer, **2400** (240 s) per flash | ✅ `0x08013E9A`, `0x08013FEA` |
| `[+0x10]` half | **Secondary accumulator.** Throttle starts at **≥ 2000** | ✅ `0x08013F20`, `0x08013F8A` |
| `[+0x14]` float | Throttle delay. Starts at 5.0 and grows by 1/2/3 per flash, capped at 20 or 25 (2.0–2.5 s) | ✅ `0x08013E96`, `0x08013F92`–`0x08014034` |

Related flags:

| Flag | Meaning | Status |
|---|---|---|
| `0x20000582` | Charge enable. Mirrored to GPIOB pin 12 by the TIM2 ISR (`fn_08021894`) | ✅ |
| `0x20000583` | Charge lockout. `fn_0800D89C` will not enable charging while it is set | ✅ |
| `0x20000584` | Cooldown mode (600 s window). Flashing still works, but each flash gets a lockout of up to 7 s | ✅ |
| `0x20000585` | Cost table select: 1 = second table (`0x0804FFAC`). Set right after an **80-pulse loop**, cleared by single-pulse paths and by the `[+0xC]` timeout | 🔶 Same multi-pulse pattern as the V100N. The optical train hasn't been checked on hardware |

### Point add (`fn_08013B54`, 11 callers)

- **Row** comes from `0x200005B9`: non-zero selects row 0, zero selects row 1. Rows 2–10 are never selected in this image. ✅ `0x08013B58`–`0x08013B62`
- `0x200005B9` is a debounced read of **GPIOC pin 15**: high for more than 10 samples gives 1 (`fn_0800DE10`). The same flag also selects rows in two other tables (`0x08050190` with 81 halfwords per row, `0x080502D4` with 101 per row), so it changes output calibration too. **What the switch physically is remains unknown.** The earlier "flip-out diffuser" label has no support in the code. ⚠️
- **Column** (0–21) comes from 21 thresholds on `0x200005C2` (capped at 100) when the mode bits of `0x2000053A` are 0. 22 columns fits 1/128–1/1 in 1/3 stops, and costs rise with the column, so column 21 is the highest power. The exact column-to-power mapping is unverified. 🔶
- A side flag: when row ≤ 3, column ≥ 15 and the primary is ≥ 750, bit 1 of `0x2000007B` is set. Its purpose is unknown. 🔶 `0x08013D20`–`0x08013D4C`

### Tables (points per flash), 11 × 22 halfwords

| Table | Row | Column 21 | Shots to primary 6000 | Shots to secondary 2000 (throttle starts) |
|---|---|---|---|---|
| `0x0804FDC8` | 1 (`0x5B9` = 0) | 200 | **30** | **10** |
| `0x0804FDC8` | 0 (`0x5B9` ≠ 0) | 300 | **20** | **7** |
| `0x0804FFAC` (multi-pulse) | any | 150 | **40** | **14** |

Counts assume a continuous burst from empty with no drain. Recycle slows down well before the primary cooldown: the secondary throttle adds 0.5 s, growing to about 2–2.5 s, to every charge from about shot 10 onward.

## Drain (`fn_0801412C`)

| Claim | Status | Evidence |
|---|---|---|
| Called every 5 ms: the TIM4 ISR (`fn_08021918`, IRQ 30) counts 5 ticks, then `fn_0802D2D4` runs | ✅ | `0x0802194C`, `0x0802D308` |
| TIM4 PSC 83 / ARR 999, giving 1 ms if the timer clock is 84 MHz | 🔶 | `fn_0802220C(0x54, 0x3E8)`. The RCC/PLL setup wasn't traced |
| Step = 20 calls (100 ms nominal) | ✅ | `0x0801413A` |
| Every 60 steps (**6.0 s**), primary and secondary each lose **80** (13.3 pts/s) | ✅ | `0x88888889` reciprocal gives `% 60`. `0x080141CC`, `0x080141E2` |

The patch doubles the drain, which halves recovery time no matter what the absolute clock is.

## Hardware temperature protection

| Path | Logic | Status |
|---|---|---|
| NTC A, ADC word `0x20000520` (`fn_08025B88`, called from `0x0804E8BE`) | > 970 → open (state 2). < 20 → short (state 3). **20–203 for more than 10 samples → forced cooldown** via `fn_0800FA1C`. Recovers at ≥ 235 | ✅ |
| NTC B, ADC word `0x20000522` (`fn_0801797C`) | ≥ 1004 → open. **< 183 for more than 10 samples → state 5 + forced cooldown** via `fn_0800FA1C` | ✅ |
| `fn_0800FA1C` | Starts the same 600 s cooldown as the accumulator does (`0x20000584`, `0x20000583`, `[+0xA]` = 6000). It does not depend on the accumulator | ✅ |
| No fan | No fan driver found | ⚠️ absence of evidence |

**Correction:** `fn_08010444` (thresholds 447/401/494 and floats 509.52/504.42 on ADC word `0x2000051C`) is a **charge-regulation loop**: it calls the charge gate `fn_0800D89C`. It is not a thermistor check. This README previously listed it as the NTC path.

## Version display (`0x0804A08A`)

`fn_0803B02A` is a variadic text formatter. For `V%d.%d%d` the arguments are r2 = `1` (`0x0804A094` imm), r3 = `0`, and [sp] = `2` (`0x0804A08A` imm). ✅ The Chinese string at `0x0804A17C` uses the same registers.

How the patcher sets the version: the format strings are rewritten as fixed text, so the formatter prints them and ignores its arguments. The digit immediates stay stock.

| File offset | Stock | Patched (Tier R) |
|---|---|---|
| `0x3E1C4` | `Version: V%d.%d%d` | `Version: V1.02.02` |
| `0x3E214` | `固件版本: V%d.%d%d` (CN) | `固件版本: V1.02.02` |

## Custom firmware profiles

| Build | Version | SHA-256 | Changes |
|---|---|---|---|
| Tier R | `V1.02.02` | `13357697a6aa2c56afd15727f9f32148f5c11e6954e205337fa7031b0d317c27` | Drain 80 → 160 on **both** accumulators. Version text. MD5 footer |
| Tier X | `V1.02.03` | `eebbc0210a912dff953cff3a89a0cbba722ef847bc1b2400480676bb6f9afaac` | Tier R + multi-pulse table −20% on all 11 rows (60/80/150 → 48/64/120). Version text. MD5 footer |

Bytes changed (34 for Tier R):
- 4 drain bytes at `0x81CC`, `0x81D0`, `0x81E2` and `0x81E6` (`50` → `A0`).
- 14 version-text bytes: `%d.%d%d` → `1.02.02` at `0x3E1CE` and `0x3E223`.
- 16 MD5 bytes at `0xA8000`.

Tier X (276 bytes) also changes 242 table bytes in `0x43FAC`–`0x4418F`. Superseded hashes are listed in the [build changelog](../README.md#8-build-changelog).

Notes:
- Tier R doubles the drain on both accumulators. That matches V100N Tier R. On the AD600Pro II, doubling both is called R+ (tier code `.04`).
- Tier X multi-pulse limits at column 21: primary 40 → 50 shots, secondary throttle 14 → 17 shots.
- Neither tier touches the 6000/2000 thresholds, the NTC paths or `fn_0800FA1C`.

## Hardware verification & open questions

1. ✅ **[Confirmed] Footer name field & flashing:** Godox G3 accepted `iT30ProN_V1.02.03_super.bin` without requiring the file on disk to match the internal footer name string (`iT30ProN_V1.02.bin`). Flashing completed successfully via G3, and the unit rebooted cleanly.
2. ✅ **[Confirmed] MD5 integrity & version display:** The recomputed MD5 at `0xA8000` is accepted by the bootloader/G3. The fixed-text version patch renders correctly on the LCD as `V1.02.03`.
3. ⚠️ **Remaining open questions:**
   - The physical meaning of the GPIOC15 row switch, and the absolute timer clock.
   - Long-term endurance of the iT30Pro's small, fanless body under faster recovery (Tier R) and lower multi-pulse heat cost (Tier X). Functional firing and thermal endurance tests are pending.
