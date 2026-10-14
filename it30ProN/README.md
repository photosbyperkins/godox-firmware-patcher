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
| The MD5 footer is **not** checked by the application or by `Godox_G3_v1.1.exe` (which only checks `file_size <= 0x100000` at `0x00404D1B`); if checked, it is verified by the on-chip USB DFU bootloader (`0x08000000`–`0x0800BFFF`) or a newer updater utility | ✅ / 🔶 | App and `Godox_G3_v1.1.exe` have no MD5 constants (`0x67452301`) or footer checks; `patch.py` always recomputes the MD5 for bootloader/updater compatibility |

## Heat counter: struct at `0x200005F4`

| Field | Meaning | Status |
|---|---|---|
| `[+0]` byte | Per-flash **charge lockout** countdown in 100 ms steps. `0x20000583` is cleared when it reaches 0 | ✅ `0x0801416E` |
| `[+1]` byte | Lockout length while in cooldown: +10 per flash, capped at 70 (7.0 s), then capped per column at 6/8/10/15/20/30/50 | ✅ `0x08013C8E`–`0x08013CA8`, `0x08013DC4`–`0x08013E56` |
| `[+2]` byte | Charge-inhibit delay from the **secondary** accumulator (100 ms steps, decremented every step at `0x080141F2` when `[+0] == 0`) | ✅ `0x08013FE8`; read by the charge gate `fn_0800D89C` |
| `[+3]` byte | Secondary throttle latch (`0x200005F7`). While `1`, every flash branches to `0x08013E6E` (bypassing `[+0x10]`, incrementing `[+0x14]`, and reloading `[+0xE] = 2400`). **Only cleared when `[+0xE]` reaches 0 (240 s with zero flashes at `0x080141D8`, or on 600 s primary cooldown expiry via `fn_080140F4`), NOT when `[+0x10]` drains to 0 (`0x080141E8`).** | ✅ `0x08013F2A`, `0x08013E6E`, `0x080141D8` |
| `[+4]` byte | Prescaler: 20 × 5 ms = 100 ms step | ✅ `0x08014132`–`0x0801413C` |
| `[+6]` half | Primary idle timer. Set to **3000** (300 s) on each flash outside cooldown. Clears `[+8]` when it reaches 0 | ✅ `0x08013CEC`, `0x08014162` |
| `[+8]` half | **Primary accumulator.** Cooldown starts at **≥ 6000** | ✅ `0x08013D54` (`cmp` + `blo`) |
| `[+0xA]` half | Cooldown window, set to **6000** (600 s). Each flash during cooldown restarts it. At 0, `fn_080140F4` resets everything | ✅ `0x08013CBC`, `0x08013D60`, `0x0801418E` |
| `[+0xC]` half | Timeout for the table-select flag: 10 × 5 ms | ✅ `0x0800D3AA`, `0x080141BA` |
| `[+0xE]` half | Secondary idle timer, **2400** (240 s) reloaded on every flash (both pre-latch and post-latch) | ✅ `0x08013E9A`, `0x08013FEA` |
| `[+0x10]` half | **Secondary accumulator.** Fed when `[+3] == 0`; throttle latch `[+3]` starts at **≥ 2000** | ✅ `0x08013F20`, `0x08013F8A` |
| `[+0x14]` float | Throttle delay. Starts at `5.0` (0.5 s) and grows by **`1.0 / 2.0 / 3.0 / 5.0` per flash** (`+5.0` at Row 0, Col 21 at `0x08014010`), capped at `20.0` or `25.0` (`2.0–2.5 s`) | ✅ `0x08013E96`, `0x08013F92`–`0x08014034` |

Related flags:

| Flag | Meaning | Status |
|---|---|---|
| `0x20000582` | Charge enable. Mirrored to GPIOB pin 12 by the TIM2 ISR (`fn_08021894`) | ✅ |
| `0x20000583` | Charge lockout. `fn_0800D89C` will not enable charging while it is set | ✅ |
| `0x20000584` | Cooldown mode (600 s window). Flashing still works, but each flash gets a lockout of up to 7 s | ✅ |
| `0x20000585` | Cost table select: 1 = second table (`0x0804FFAC`, HSS). Set right after an **80-pulse loop** (`0x0800D3A8`, `0x0800D9CC`, `0x0802EF4E`, gated by bit 4 of `0x2000053A` / UI HSS sync mode `[0x20000440+4] == 1` at `0x08014F7A`), cleared by single-pulse paths and by the `[+0xC]` timeout | ✅ Code verified end-to-end (🔶 physical optical train unverified on hardware) |

### Point add (`fn_08013B54`, 10 callers)

- **Row** comes from `0x200005B9`: non-zero selects row 0, zero selects row 1. Rows 2–10 are never selected in this image. ✅ `0x08013B58`–`0x08013B62`
- `0x200005B9` is a debounced read of **GPIOC pin 15**: high for more than 10 samples gives 1 (`fn_0800DE10`). It also selects rows in two output-calibration tables (`0x08050190` with 81 halfwords per row, `0x080502D4` with 101 per row) and **directly selects the status-bar diffuser/wide-panel icon (`\xee\x98\x9d` when 0 vs. `\xee\x98\x9e` when 1 at `0x08045B0C`)**, confirming in code that `GPIOC pin 15` is the **built-in wide-angle diffuser switch**. ✅
- **Column** (0–21) is verified in `fn_080109BC` (`0x080109BC`–`0x08010A64`) and `fn_08013904` (`0x08013904`–`0x080139A4`): manual/HSS power byte `P` (`0x20000542`/`0x20000543`, range `0..70` in `0.1 EV` steps, formatted as `(70 - P) / 10` integer + `(70 - P) % 10` tenth-stop, with `P = 0` displaying `1/1` and `P = 70` displaying `1/128`) is mapped via 21 thresholds (`70, 67, 63, 60, 57, 53, 50, 47, 43, 40, 37, 33, 30, 27, 23, 20, 17, 13, 10, 7, 3`) to **Columns `0..21` (`1/128` to `1/1` in 1/3-stop steps, where Column 21 is `P < 3` = `1/1`)**. When the mode bits of `0x2000053A` are 0 (**TTL mode**), the column comes from 21 thresholds on the TTL pre-flash power index `0x200005C2` (`0..100`). ✅
- **Side flags in `0x2000007B` (bit 1 at `0x08013D44` and bit 2 at `0x08013EE2`/`0x08013F84`):** Verified across the entire disassembly as **dead/vestigial code**—`0x2000007B` is only ever modified by `read-ORR-write` in those three places and is never read or cleared anywhere in the binary. ✅

### Tables (points per flash), 11 × 22 halfwords

| Table | Row | Column 21 | Shots to primary 6000 | Shots to secondary 2000 (throttle starts) |
|---|---|---|---|---|
| `0x0804FDC8` | 1 (`0x5B9` = 0, diffuser retracted) | 200 | **30** | **10** |
| `0x0804FDC8` | 0 (`0x5B9` ≠ 0, diffuser extended) | 300 | **20** | **7** |
| `0x0804FFAC` (multi-pulse / HSS) | any | 150 | **40** | **14** |

Counts assume a continuous burst from empty with no drain. Recycle slows down well before the primary cooldown: the secondary throttle adds 0.5 s, growing to about 2–2.5 s, to every charge from shot 10 (or shot 7 with diffuser extended) onward.

## Drain (`fn_0801412C`)

| Claim | Status | Evidence |
|---|---|---|
| Called every 5 ms: the TIM4 ISR (`fn_08021918`, IRQ 30) counts 5 ticks, then `fn_0802D2D4` runs | ✅ | `0x0802194C`, `0x0802D308` |
| **TIM4 clock = 84 MHz → 1.000 ms tick:** `fn_08021534` configures HSI 16 MHz (`±1%`) → PLLM=16, PLLN=336, PLLP=2 → **168 MHz SYSCLK**, APB1 `/4` (42 MHz, `×2` = **84 MHz TIM4 clock**); `fn_0802220C(0x54, 0x3E8)` sets `PSC = 83, ARR = 999` → **1.000 ms** (dynamically rescaled to `PSC = 55` at 56 MHz in sleep `0x0802DFAE`) | ✅ | `fn_08021534` (`0x08021534`–`0x080215FA`), `fn_0802220C`, `0x0802DFAE` |
| Step = 20 calls (**0.100 s / 100 ms nominal**) | ✅ | `0x0801413A` |
| Every 60 steps (**6.0 s**), primary `[+8]` and secondary `[+0x10]` each lose **80** (**13.3 pts/s stock**, **26.7 pts/s Tier R/X**). Draining `[+0x10]` accelerates **pre-latch (`[+3] == 0`) recovery** between bursts; once `[+3]` is latched, it clears only when `[+0xE]` reaches 0 after 240 s without flashes (`0x080141D8`). | ✅ | `0x88888889` reciprocal gives `% 60`. `0x080141CC`–`0x080141EC` |

## Hardware temperature protection

| Path | Logic | Status |
|---|---|---|
| NTC A, ADC word `0x20000520` (`fn_08025B88`, called from `0x0804E8BE`) | > 970 → open (state 2). < 20 → short (state 3). **20–203 for more than 10 samples → forced cooldown** via `fn_0800FA1C`. Recovers at ≥ 235 | ✅ |
| NTC B, ADC word `0x20000522` (`fn_0801797C`) | ≥ 1004 → open. **< 183 for more than 10 samples → state 5 + forced cooldown** via `fn_0800FA1C` | ✅ |
| `fn_0800FA1C` | Starts the same 600 s cooldown as the accumulator does (`0x20000584`, `0x20000583`, `[+0xA]` = 6000). It does not depend on the accumulator | ✅ |
| No fan | No fan driver found | ⚠️ absence of evidence |

**Correction:** `fn_08010444` (thresholds 447/401/494 and floats 509.52/504.42 on ADC word `0x2000051C`) is a **charge-regulation loop**: it calls the charge gate `fn_0800D89C`. It is not a thermistor check. This README previously listed it as the NTC path.

## Version display (`0x0804A08A`)

`fn_0803B02A` is a variadic text formatter. For `V%d.%d%d` the arguments are r2 = `1` (`0x0804A094` imm), r3 = `0`, and [sp] = `2` (`0x0804A08A` imm). ✅ The Chinese string at `0x0804A17C` uses the same registers. (Unlike AD200Pro II and V100N, iT30ProN has no separate settings-menu `V%d.%d%d` readout).

How the patcher sets the version: the format strings are rewritten as fixed text, so the formatter prints them and ignores its arguments. The digit immediates stay stock.

| File offset | Stock | Patched (Tier R) |
|---|---|---|
| `0x3E1C4` | `Version: V%d.%d%d` | `Version: V1.02.02` |
| `0x3E214` | `固件版本: V%d.%d%d` (CN) | `固件版本: V1.02.02` |

## Custom firmware profiles

| Build | Version | SHA-256 | Changes |
|---|---|---|---|
| Tier R | `V1.02.02` | `13357697a6aa2c56afd15727f9f32148f5c11e6954e205337fa7031b0d317c27` | Drain 80 → 160 on **both** accumulators (2× primary + 2× pre-latch secondary recovery). Version text. MD5 footer |
| Tier X | `V1.02.03` | `eebbc0210a912dff953cff3a89a0cbba722ef847bc1b2400480676bb6f9afaac` | Tier R + multi-pulse (HSS) table −20% on all 11 rows (60/80/150 → 48/64/120). Version text. MD5 footer |

Bytes changed (34 for Tier R):
- 4 drain bytes at `0x81CC`, `0x81D0`, `0x81E2` and `0x81E6` (`50` → `A0`).
- 14 version-text bytes: `%d.%d%d` → `1.02.02` at `0x3E1CE` and `0x3E223`.
- 16 MD5 bytes at `0xA8000`.

Tier X (276 bytes) also changes 242 table bytes in `0x43FAC`–`0x4418F`. Superseded hashes are listed in the [build changelog](../README.md#8-build-changelog).

Notes:
- Tier R doubles the drain on both accumulators (`80 → 160` per 6.0 s). For the secondary accumulator `[+0x10]`, this halves pre-latch (`[+3] == 0`) recovery time between bursts so `[+0x10]` drains before reaching 2000; once latched (`[+3] == 1`), the latch clears after 240 s with zero flashes (`0x080141D8`).
- Tier X multi-pulse (HSS) limits at column 21: primary 40 → 50 shots, secondary throttle 14 → 17 shots.
- Neither tier touches the 6000/2000 thresholds, the NTC paths or `fn_0800FA1C`.

## Hardware verification & open questions

1. ✅ **[Confirmed] Footer name field & flashing:** Godox G3 accepted `iT30ProN_V1.02.03_super.bin` without requiring the file on disk to match the internal footer name string (`iT30ProN_V1.02.bin`). Disassembly of `Godox_G3_v1.1.exe` (`0x00404D1B`) also confirms G3 only checks `file_size <= 1 MB`.
2. ✅ **[Confirmed] MD5 integrity & version display:** The recomputed MD5 at `0xA8000` is accepted by the device, and the fixed-text version patch renders on the LCD as `V1.02.03`.
3. ✅ **[Verified in code] Timer clock, power mapping & GPIOC15 switch:** `fn_08021534` confirms the 168 MHz SYSCLK / 84 MHz TIM4 clock (`100 ms` step), `fn_080109BC` confirms Columns `0..21` map to `1/128..1/1` in 1/3-stop steps, and `0x08045B0C` confirms `GPIOC pin 15` (`0x200005B9`) drives the status-bar wide-angle diffuser icon.
4. ⚠️ **Remaining open questions:**
   - Long-term endurance of the iT30Pro's small, fanless body under faster recovery (Tier R) and lower multi-pulse heat cost (Tier X). Functional firing and thermal endurance tests are pending.
