# Godox iT30Pro (Nikon) — iT30ProN

Mini on-camera speedlite (~120 g) with a built-in wide-angle diffuser. Fanless. The only supported model whose image carries an integrity footer.

| | |
|---|---|
| OEM image | `iT30ProN_V1.02.bin` · 688,172 bytes · SHA-256 `a6920833d267834e7ff41f537ce8b897bab47234013731ae79b4affcbf41847e` |
| Platform | STM32F4-class Cortex-M4F, HSI 16 MHz → 168 MHz, APB1 timers 84 MHz · load `0x0800C000` · SP `0x2001F3F0` · reset `0x0800C279` |
| File offset | address − `0x0800C000` |
| Patcher | [`patch.py`](patch.py) → Tiers R, X (no fan, so no Tier S); always recomputes the MD5 footer |
| Disassembly | [`disasm/iT30ProN_V1.02.asm`](disasm/iT30ProN_V1.02.asm) |
| Hardware | `V1.02.03` flashed with G3; the recomputed MD5 was accepted and `V1.02.03` is displayed (2026-10-10). |

Status marks and notation: [architecture.md › Conventions](../../docs/architecture.md#conventions).

> [!IMPORTANT]
> Any change inside `file[0:0xA8000]` must refresh the MD5 in the footer. Never flash an image patched by other means without recomputing it.

## Image layout

| Item | Evidence |
|---|---|
| Vector table at `0x0800C000`; `--detect` scores 281 against 61 for the next candidate. `fn_08021660` writes `0x0800C000` to VTOR and enables the FPU (CPACR bits 20–23); VFP instructions are used (e.g. `0x08013E5E`). | vector table, `fn_08021660` |
| Code and data end at file offset `0xA48C8`, followed by `0xFF` padding up to `0xA8000`. | byte scan |
| **Footer at `0xA8000` (44 bytes):** `+0x00` MD5 of `file[0:0xA8000]` (16 B) · `+0x10` name `iT30ProN_V1.02.bin` (18 B, no NUL) · `+0x22` u16 name length `0x0012` · `+0x24` magic `AA 55 66 99 77 88 22 33`. | MD5 recomputed and matches |
| 🔶 Neither the application nor `Godox_G3_v1.1.exe` contains MD5 code (no `0x67452301`) or reads the footer; G3 only checks `size ≤ 0x100000` (`0x00404D1B`). The check, if any, is in the bootloader or a newer updater. G3 accepted a file whose name differs from the footer name. | disassembly, hardware |

## Builds

| Tier | File | Version | SHA-256 |
|---|---|---|---|
| R Recovery | `iT30ProN_V1.02.02_recovery.bin` | `V1.02.02` | `13357697a6aa2c56afd15727f9f32148f5c11e6954e205337fa7031b0d317c27` |
| X Super | `iT30ProN_V1.02.03_super.bin` | `V1.02.03` | `eebbc0210a912dff953cff3a89a0cbba722ef847bc1b2400480676bb6f9afaac` |

- **R** — 2× drain on both counters (80 → 160 per 6 s). Once latched, the secondary throttle still needs 240 s without a flash.
- **X** — R + multi-pulse (HSS) table −20 % on all 11 rows (60/80/150 → 48/64/120): 1/1 HSS burst 40 → 50 shots, secondary throttle 14 → 17.

Neither tier touches the 6000 / 2000 thresholds, the NTC paths or `fn_0800FA1C`. Superseded hashes: [CHANGELOG](../../CHANGELOG.md).

### Byte diff

| File offset | Address | Stock → patched | Effect | Tiers |
|---|---|---|---|---|
| `0x81CC`, `0x81D0` | `0x080141CC`, `0x080141D0` | `50` → `A0` | primary drain `cmp` / `subs r0,#80` → `#160` | R, X |
| `0x81E2`, `0x81E6` | `0x080141E2`, `0x080141E6` | `50` → `A0` | secondary drain `cmp` / `subs r0,#80` → `#160` | R, X |
| `0x43FAC`–`0x4418F` | `0x0804FFAC` | 11 × 22 halfwords | multi-pulse (HSS) table | X |
| `0x3E1CE`–`0x3E1D4` | `0x0804A1CE` | `%d.%d%d` → `1.02.TT` inside `Version: V%d.%d%d` (`0x3E1C4`, ADR `0x0804A09A`) | Device Info (EN) | all |
| `0x3E223`–`0x3E229` | `0x0804A223` | same inside `固件版本: V%d.%d%d` (`0x3E214`, ADR `0x0804A17C`) | Device Info (CN) | all |
| `0xA8000`–`0xA800F` | — | MD5 | footer | all |

Bytes changed: R 34 (4 drain + 14 version + 16 MD5), X 276 (+ 242 table bytes). `fn_0803B02A` formats `V%d.%d%d` with r2 = 1 (immediate at `0x0804A094`), r3 = 0 and `[sp]` = 2 (immediate at `0x0804A08A`); fixed text makes it ignore them. Unlike the AD200Pro II and V100N there is no separate settings-menu readout.

## Heat counter

### State (`0x200005F4`)

| Field | Meaning | Evidence |
|---|---|---|
| `[+0x0]` byte | Per-flash charge lockout (steps); clears `0x20000583` at 0 | `0x0801416E` |
| `[+0x1]` byte | Lockout length in cooldown: +10 per flash, cap 70 (7.0 s), then per-column cap 6/8/10/15/20/30/50 | `0x08013C8E`–`0x08013CA8`, `0x08013DC4`–`0x08013E56` |
| `[+0x2]` byte | Charge delay from the secondary throttle (steps; decremented at `0x080141F2` while `[+0] = 0`); read by the charge gate `fn_0800D89C` | `0x08013FE8` |
| `[+0x3]` byte | Secondary latch (`0x200005F7`) | `0x08013F2A` |
| `[+0x4]` byte | Prescaler: 20 × 5 ms = 100 ms | `0x08014132`–`0x0801413C` |
| `[+0x6]` half | Primary idle timer, 3000 (300 s) per flash outside cooldown; clears `[+8]` at 0 | `0x08013CEC`, `0x08014162` |
| `[+0x8]` half | **Primary accumulator**; cooldown at `≥ 6000` | `0x08013D54` |
| `[+0xA]` half | Cooldown window, 6000 (600 s), restarted by each flash in cooldown; `fn_080140F4` resets everything at 0 | `0x08013CBC`, `0x08013D60`, `0x0801418E` |
| `[+0xC]` half | HSS flag timeout, 10 × 5 ms | `0x0800D3AA`, `0x080141BA` |
| `[+0xE]` half | Secondary timer, 2400 (240 s), reloaded by every flash | `0x08013E9A`, `0x08013FEA` |
| `[+0x10]` half | **Secondary accumulator**; fed while `[+3] = 0`; latches at `≥ 2000` | `0x08013F20`, `0x08013F8A` |
| `[+0x14]` float | Throttle delay: starts at 5.0 (0.5 s), +1.0 / 2.0 / 3.0 / 5.0 per flash (+5.0 at row 0, column 21, `0x08014010`), cap 20.0 or 25.0 | `0x08013E96`, `0x08013F92`–`0x08014034` |

While `[+3] = 1`, every flash branches to `0x08013E6E` (skips `[+0x10]`, grows `[+0x14]`, reloads `[+0xE]`). The latch clears only when `[+0xE]` reaches 0 (`0x080141D8`) or the 600 s cooldown expires (`fn_080140F4`) — not when `[+0x10]` drains (`0x080141E8`).

| Flag | Meaning |
|---|---|
| `0x20000582` | Charge enable, mirrored to GPIOB pin 12 by the TIM2 ISR (`fn_08021894`) |
| `0x20000583` | Charge lockout; `fn_0800D89C` won't charge while set |
| `0x20000584` | Cooldown mode (600 s window): flashing works, each flash gets up to 7 s lockout |
| `0x20000585` | HSS table select. Set after an 80-pulse loop (`0x0800D3A8`, `0x0800D9CC`, `0x0802EF4E`), gated by bit 4 of `0x2000053A` (UI HSS sync, `[0x20000440+4] = 1` at `0x08014F7A`); cleared by single-pulse paths and the `[+0xC]` timeout. 🔶 Light output not scope-verified. |

### Add (`fn_08013B54`, 10 callers)

- **Row** from `0x200005B9`: non-zero → row 0, zero → row 1; rows 2–10 are never selected (`0x08013B58`–`0x08013B62`). `0x200005B9` is a debounced read of **GPIOC pin 15** (> 10 samples high → 1, `fn_0800DE10`), the built-in wide-angle diffuser switch: it also selects rows in two output-calibration tables (`0x08050190`, 81 halfwords per row; `0x080502D4`, 101) and the status-bar diffuser icon (`\xee\x98\x9d` / `\xee\x98\x9e`, `0x08045B0C`).
- **Column** 0–21 (`fn_080109BC`, `fn_08013904`): power `P` (`0x20000542` / `0x20000543`, 0–70 in tenths of a stop, shown as `(70 − P) / 10`) passes 21 thresholds `70, 67, 63, 60, 57, 53, 50, 47, 43, 40, 37, 33, 30, 27, 23, 20, 17, 13, 10, 7, 3` → column 0 (1/128) … 21 (`P < 3`, 1/1), one column per 1/3 stop. TTL (mode bits of `0x2000053A` = 0): 21 thresholds on `0x200005C2` (0–100).
- `0x2000007B` bits 1 and 2 (`0x08013D44`, `0x08013EE2`, `0x08013F84`) are only ever OR-written and never read anywhere: dead code.

### Tables (11 × 22 halfwords)

| Table | Row | Column 21 | Shots to 6000 | Shots to 2000 (throttle) |
|---|---|---|---|---|
| `0x0804FDC8` | 1 (`0x5B9 = 0`, diffuser retracted) | 200 | 30 | 10 |
| `0x0804FDC8` | 0 (`0x5B9 ≠ 0`, diffuser extended) | 300 | 20 | 7 |
| `0x0804FFAC` (HSS), stock: `60×16, 80×3, 150×3` | any | 150 | 40 | 14 |
| `0x0804FFAC`, Tier X: `48×16, 64×3, 120×3` | any | 120 | 50 | 17 |

The secondary throttle adds 0.5 s, growing to 2–2.5 s, to every charge from shot 10 (7 with the diffuser extended) — well before the primary cooldown.

### Drain (`fn_0801412C`)

| Action | Evidence |
|---|---|
| Called every 5 ms: TIM4 ISR (`fn_08021918`, IRQ 30) counts 5 ticks, then `fn_0802D2D4` runs. TIM4: `fn_08021534` sets HSI 16 MHz → PLLM 16, PLLN 336, PLLP 2 = 168 MHz, APB1 ÷4 (timer ×2 = 84 MHz); `fn_0802220C(0x54, 0x3E8)` sets PSC 83, ARR 999 = 1 ms. In sleep PSC becomes 55 at 56 MHz (`0x0802DFAE`). | `0x0802194C`, `0x0802D308` |
| Step = 20 calls (100 ms). | `0x0801413A` |
| Every 60 steps (6.0 s; reciprocal `0x88888889` → `% 60`): `[+8]` and `[+0x10]` each −80 (13.3 pts/s; Tier R/X 26.7 pts/s). | `0x080141CC`–`0x080141EC` |

## Thermal protection

| Path | Logic |
|---|---|
| NTC A, ADC word `0x20000520` (`fn_08025B88`, called from `0x0804E8BE`) | > 970 open (state 2), < 20 short (state 3); **20–203 for > 10 samples → forced cooldown** `fn_0800FA1C`; recovers at ≥ 235 |
| NTC B, ADC word `0x20000522` (`fn_0801797C`) | ≥ 1004 open; **< 183 for > 10 samples → state 5 + forced cooldown** `fn_0800FA1C` |
| `fn_0800FA1C` | Starts the same 600 s cooldown as the accumulator (`0x20000584`, `0x20000583`, `[+0xA]` = 6000), independent of the accumulator |
| Fan | ⚠️ No fan driver found (absence of evidence) |

`fn_08010444` (thresholds 447 / 401 / 494 and 509.52 / 504.42 on ADC word `0x2000051C`) is a **charge-regulation loop** that calls the charge gate `fn_0800D89C`, not a thermistor check. Earlier notes misidentified it.

## Open questions

- ⚠️ Long-term endurance of this small, fanless body under Tier R and Tier X. Firing and thermal endurance tests are pending.
- ⚠️ The "Hot Shoe Upgrading" screen (`0x0802F278`) suggests a separately updated hot-shoe subsystem; what V1.02 changed there is unknown.
