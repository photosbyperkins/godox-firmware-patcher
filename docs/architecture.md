# Architecture reference

Cross-model findings for the five supported firmwares: platform, update path, the shared heat-counter design, HSS detection and thermal protection. Model-specific routines, tables and byte diffs are in `models/<Model>/README.md`.

**Last audited:** 2026-10-13 · **Bases:** AD600Pro II v1.08, AD200Pro II V1.05, AD100Pro II V1.07, V100N V1.04, iT30ProN V1.02

## Conventions

| | |
|---|---|
| Status | Every claim is ✅ **verified in the disassembly** unless marked 🔶 **partial** (instructions confirmed, some values or meanings not traced) or ⚠️ **unverified** (inference, absence of evidence, or outside source). "Verified" never means hardware-tested; hardware results are stated with a date. |
| Addresses | Runtime addresses. File offset = address − load address. |
| Notation | `[+0xN]` is a field of the model's heat-state struct; `[0xADDR]` is a RAM variable; `fn_XXXXXXXX` / `loc_` names come from `tools/disasm.py`. |
| ADC values | Raw counts. The firmware converts the `u16` reading to `double` and compares it with constants (e.g. `271.0588 = 4608/17`); there is no °C conversion anywhere. Lower count = hotter. |
| Step | One 100 ms tick of the heat-counter timer (§3). |

## 1. Platform

| Model | MCU and clock | Load address | Initial SP | Reset | Image size (bytes) |
|---|---|---|---|---|---|
| AD600Pro II | STM32F4-class; HSI 16 MHz → PLL 168 MHz; APB1 timers 84 MHz | `0x0800C000` | `0x20018570` | `0x0800C1A1` | 407,384 |
| AD200Pro II | STM32F4-class; HSI 16 MHz → PLL 168 MHz | `0x0800C000` | `0x1000F000` (CCM RAM) | `0x0800C269` | 387,248 |
| AD100Pro II | STM32F4-class; HSI 16 MHz → PLL 168 MHz; APB1 timers 84 MHz | `0x0800C000` | `0x2001BC00` | `0x0800C249` | 357,004 |
| V100N | GD32F450/470; IRC16M → PLL 240 MHz; `TIMERSEL` set, timers 240 MHz | `0x08008000` | `0x200AD678` | `0x0800829D` | 1,001,676 |
| iT30ProN | STM32F4-class Cortex-M4F (FPU enabled); HSI 16 MHz → PLL 168 MHz; APB1 timers 84 MHz | `0x0800C000` | `0x2001F3F0` | `0x0800C279` | 688,172 |

- All five are plaintext Thumb-2 application images with no header and no encryption. Peripheral addresses (GPIO at `0x40020000`, `0x40020800`, …) follow the STM32F4 memory map.
- Load addresses were found with `tools/disasm.py --detect`, which scores candidate bases by how many embedded pointers hit function prologues or string starts; each vector table agrees.
- No crystal is configured; all timing derives from the internal RC oscillator (nominal ±1 %).

## 2. Update path and image integrity

- **Bootloader.** The USB bootloader occupies flash below the application (`0x08000000` up to the load address) and is not written by an update. A cross-model flash (AD100Pro II image onto an AD200Pro II) left the unit blinking with a blank screen; re-flashing the correct image with G3 restored it (hardware, 2026-10-14).
- **Godox G3.** `Godox_G3_v1.1.exe` checks only `file_size ≤ 0x100000` (`0x00404D1B`) and streams the file in 1 KB blocks over USB HID. It performs no checksum, MD5 or signature check, and does not compare the file name with anything.
- **Checksums.** The AD600Pro II, AD200Pro II, AD100Pro II and V100N images carry no checksum.
- **iT30ProN footer.** The last 44 bytes (`0xA8000`) hold the MD5 of `file[0:0xA8000]`, the name `iT30ProN_V1.02.bin`, its length, and the magic `AA 55 66 99 77 88 22 33`. Neither the application nor G3 verifies it, so the bootloader (or a newer updater) presumably does 🔶. The patcher recomputes it; a recomputed footer was accepted on hardware (2026-10-10).
- **Restore.** Flashing the OEM image with G3 returns the unit to stock (hardware, 2026-10-09).

## 3. Timer: one step = 100 ms

Every model drives the heat counter from a hardware timer through two prescalers to a 100 ms step. Drain intervals are therefore exact multiples of 100 ms (nominal ±1 %).

| Model | Base tick | → 5 ms task | → 100 ms step | Runs only while |
|---|---|---|---|---|
| AD600Pro II | TIM14, 200 µs (PSC 83, ARR 199; IRQ 45 → `fn_0801EE58`) | ÷25 at `0x0801F4DC` | ÷20 at `0x0801369A` | `[0x2000016E] ≠ 0` and `[0x200000A7] = 0` |
| AD200Pro II | SysTick, 1 ms (`fn_080193B8`) | ÷5 → `fn_08023CF8` | ÷20 at `0x08012376` | bits 0 and 2 of `[0x200001F8]` set |
| AD100Pro II | TIM14, 200 µs (PSC 83, ARR 199 at `0x0801297C`; ISR `0x08017000`) | ÷25 in `fn_080175D8` | ÷20 via `[+9]` | `[0x20000131] ≠ 0` |
| V100N | TIM5, 1 ms (PSC 239, CAR 999; IRQ 50 → `fn_0801E520`) | ÷5 | ÷20 at `0x0800F3FA` | bits 2 and 3 of `[0x20000034]` set |
| iT30ProN | TIM4, 1 ms (PSC 83, ARR 999 via `fn_0802220C`; IRQ 30 → `fn_08021918`) | ÷5 at `0x0802194C` → `fn_0802D2D4` | ÷20 at `0x0801413A` | — |

In sleep the AD100Pro II (`0x08016DE6`) and iT30ProN (`0x0802DFAE`) lower the system clock and rescale the prescaler to keep the same tick.

## 4. Heat counter

### 4.1 Mechanism

All five firmwares implement the same leaky-bucket design:

1. **Cost lookup.** A flash calls the *add* routine, which picks a column from the power setting and a row (zoom, head group or diffuser), then reads a cost from the normal table or, if the HSS flag is set, the HSS table.
2. **Accumulate.** Outside cooldown the idle timer is reloaded and the cost is added to the primary accumulator. Flashes during cooldown do not reload the idle timer.
3. **Trip.** At `≥ threshold` (`cmp` + `blo`) the firmware sets a charge-inhibit flag, a short hold counter and a long cooldown window. During the window each flash lengthens a per-flash charge lockout and reloads the window. It is a throttled window, not a hard lockout.
4. **Drain.** The *drain* routine runs every step. Every N steps it subtracts a fixed amount; when the idle timer reaches 0 it clears the accumulator; when the window expires it leaves cooldown.
5. **Secondary throttle.** A second accumulator fed from the same table trips at a lower threshold and *latches* a per-flash charge delay. Draining it does not clear the latch; only a full flash-free window does.

Because every flash reloads the idle timer and the drain waits for N idle steps, **the drain never runs during a continuous burst**. Burst limits from empty are exactly ⌈threshold ÷ cost⌉.

### 4.2 Parameters

| | AD600Pro II | AD200Pro II | AD100Pro II | V100N | iT30ProN |
|---|---|---|---|---|---|
| Add / drain routine | `fn_080134E4` / `fn_08013694` | `fn_08012018` / `fn_08012370` | `fn_08010FEC` / `fn_080111F4` | `fn_0800EFBC` / `fn_0800F3F4` | `fn_08013B54` / `fn_0801412C` |
| State struct · primary acc. | `0x20000046` · `[+0xE]` | `0x2000015C` · `[+0xC]` | `0x20000028` · `[+0x20]` | `0x20000594` · `[+8]` | `0x200005F4` · `[+8]` |
| Tables | 1 row × 28, normal + HSS | 1 row × 25, 2 head groups × normal/HSS | 11 rows (zoom) × 25, normal + HSS | 11 rows (zoom) × 22, normal + HSS | 11 rows (diffuser) × 22, normal + HSS |
| Normal / HSS table | `0x080398B8` / `0x080398F0` | `0x0804149A`, `0x080414CC` / `0x080414FE`, `0x08041530` | `0x08032D22` / `0x08032F48` | `0x0805174C` / `0x08051930` | `0x0804FDC8` / `0x0804FFAC` |
| Primary threshold | 6400 | 6000; 7500 with H200 II | 6000 | 6000 | 6000 |
| Idle timeout | 1200 (120 s) | 3000 (300 s) | 3000 (300 s) | 3000 (300 s) | 3000 (300 s) |
| Drain | −40 / 50 steps; −5 / 40 steps more with HSS off | −125 (group A) or −100 (group B) / 50 steps | −25 / 50 steps | −50 / 50 steps | −80 / 60 steps |
| Cooldown window | 3000 (300 s) | 3000 (300 s) | 3000 (300 s) | 3000 (300 s) | 6000 (600 s) |
| Lockout growth in cooldown (steps) | +3 (+1 above 40), cap 80 | +3, cap 100; then per-index cap 5–40 (HSS 50–90) | +3, cap 50; lower at low power | +5, cap 50; then per-column cap 10–50 | +10, cap 70; then per-column cap 6–50 |
| Secondary acc. · threshold | `[+0x16]` · 3000 | `[+0x18]` · 6000 (H200 II only) | `[+0x28]` · 3200 | `[+0x10]` · 3000 | `[+0x10]` · 2000 |
| Secondary drain | −40 / 20 steps | −165 / 50 steps | −30 / 50 steps | −50 / 50 steps | −80 / 60 steps |
| Secondary unlatch (steps without a flash) | 300 (30 s) | 1800 (180 s) | 1800 (180 s) | 1200 (120 s) | 2400 (240 s) |
| Delay while latched | 0.5 s charge pause per flash at index ≥ 24 or HSS | 0.5–1.7 s recycle delay | 0.5 s, +0.1 s per flash (+0.5 s HSS), cap 1.5 s | 0.5–1.5 s hard charge inhibit (charger-off GPIO) | 0.5 s, +0.1–0.5 s per flash, cap 2.0–2.5 s |

### 4.3 Stock burst limits at 1/1

| Model | Normal | HSS | Secondary throttle starts |
|---|---|---|---|
| AD600Pro II | 80 | 64 | shot 38 (normal), 30 (HSS) |
| AD200Pro II | A 40, B 60; H200 II 50 | A 33, B 50; H200 II 41 | H200 II only: shot 41 (normal), 34 (HSS) |
| AD100Pro II | 60 (28 mm) … 100 (85 mm) | 60 | shot 32 (28 mm / HSS) … 54 (85 mm) |
| V100N | 70 (20–28 mm) … 100 (80–200 mm) | 60 | shot 35 (wide) / 30 (HSS) |
| iT30ProN | 30 (diffuser retracted), 20 (extended) | 40 | shot 10 / 7 / 14 |

### 4.4 Power → column

Power is stored as tenths of a stop below full: `P = 0` is 1/1, `P = 10` is 1/2, `P = 20` is 1/4. Each model maps `P = 0` to its top column; except where marked, this is confirmed by tracing the UI formatter.

| Model | UI formatter | Map | Top column | Range |
|---|---|---|---|---|
| AD600Pro II | `fn_08016AAC` | `0x0803985C[P]` | 27 | 1/1–1/512 |
| AD200Pro II | `0x080148BE` / `0x08014914` | `0x0804143E[P]` | 24 | 1/1–1/256 (1/512 on heads 1–3) |
| AD100Pro II | 🔶 not traced; inferred from the map (one column per ~3⅓ tenths, like the others) | `0x08032CD0[P]` | 24 | — |
| V100N | `fn_08011670` | `fn_0800EC4C` (21 compares; `P < 3` → 21) | 21 | 1/1–1/256 |
| iT30ProN | `fn_080109BC` | 21 thresholds (`fn_08013904`) | 21 | 1/1–1/128 (1/1–1/16 in HSS) |

In TTL mode (mode bits = 0) the column comes from a 0–100 TTL power value, computed from pre-flash metering and FEC, through a 40/50/…/100 threshold ladder: `0x20000048` (AD600), `0x2000015C` (AD200), `0x2000002A` (AD100), `0x2000055B` (V100N), `0x200005C2` (iT30).

## 5. HSS detection

Selecting HSS sets bit 4 (`0x10`) of a mode byte. The trigger dispatcher turns this into trigger mode `0x1A`, which runs a multi-pulse loop and then sets the HSS-table flag before calling the add routine. Single-pulse paths write 0 to the flag, and some models also clear it on a short timeout.

| Model | Mode byte | Pulse loop | Table flag | Flag timeout |
|---|---|---|---|---|
| AD600Pro II | `0x2000009D` | 105 (`fn_0801F6C0`, `cmp r4,#0x69` at `0x0801F796`) | `0x200000DD` | — |
| AD200Pro II | `0x20000004` | 100 (`0x08013F1C`); 105 wireless (`0x08019E80`) | `0x2000004B` | `[+0x12]` = 3 × 5 ms |
| AD100Pro II | `0x20000034` | 100 (`fn_08012334`); 105 wireless (`fn_08017A8C`) | `0x20000035` (`[+0xD]`) | `[+0x24]` = 3 × 5 ms |
| V100N | `0x200004D3` | 80 (`0x0800A2D0`, `fn_0801F698`) | `0x2000051F` | `[+0xC]` = 10 × 5 ms |
| iT30ProN | `0x2000053A` | 80 | `0x20000585` | `[+0xC]` = 10 × 5 ms |

🔶 The code path from the UI's HSS setting to the table flag is traced end to end on all five. That these pulse trains are the HSS light output has not been confirmed with an oscilloscope.

## 6. Thermal protection and fans

The thermistor paths are independent of the heat counter, and no tier modifies them.

| Model | Sensor(s) | Forced cooldown | Further trip | Recovers at |
|---|---|---|---|---|
| AD600Pro II | NTC A `0x2000002C` (`fn_08017120`, head / modelling lamp, −10 counts while the lamp is on); NTC B `0x2000002E` (`fn_080172D8`, board / IGBT) | Either < 132 (NTC B: < 86 shortly after a flash) → 9.0 s hold (`fn_080103B4`) | NTC B < 49.69 → **Error E2** | timed (9 s hold, 300 s window) |
| AD200Pro II | Analog head NTC `0x200000AE` (`fn_08015C78`); H200 II digital NTC via I2C `0x5C` reg `0x06` (`[0x200001E6]`) | < 132 / < 396 → `fn_0800E1E4` | < 75 / < 260 → severe state 5 (blinking thermometer; H200 II also shuts the modelling lamp off) | ≥ 235 / ≥ 816 |
| AD100Pro II | One NTC `0x20000010` (`fn_08014234`) | < 114.59 → 300 s throttled cooldown (`fn_0800E178`) | > 950 / < 20 → sensor fault (`NTC:E1` / `NTC:E2`) | ≥ 204.14 |
| V100N | NTC via ADC0 DMA average `0x200004B6` (`fn_08022F30`) | < 98.98 for > 100 samples → `fn_0800D544` | > 970 open / < 20 short | ≥ 176.3 |
| iT30ProN | NTC A `0x20000520` (`fn_08025B88`); NTC B `0x20000522` (`fn_0801797C`) | 20–203 (A) or < 183 (B) for > 10 samples → 600 s cooldown (`fn_0800FA1C`) | > 970 / ≥ 1004 open, < 20 short | ≥ 235 (A) |

| Model | Fan | Control |
|---|---|---|
| AD600Pro II | Internal, two speeds | `fn_08017480` picks level 0/1/2; `fn_08010E74` drives PC14 (L1) or PC14 + PA4 + PA7 (L2) |
| AD200Pro II | In the H200 II head only | Body switches it over bit-banged I2C (slave `0x5C`, reg `0x01`) in `fn_080237B0` |
| AD100Pro II | Internal, on/off | `fn_08014370` drives GPIOC pin 4 |
| V100N, iT30ProN | None | ⚠️ No fan driver found (absence of evidence) |

## 7. Open questions

1. 🔶 Confirm with an oscilloscope that the multi-pulse paths (§5) are the HSS light output.
2. ⚠️ Endurance of every non-S tier, especially on the fanless V100N and iT30Pro.
3. 🔶 Which component checks the iT30ProN MD5 footer (bootloader or a newer updater).
4. ⚠️ Physical location of the AD100Pro II thermistor.
5. ⚠️ The iT30ProN app has a "Hot Shoe Upgrading" screen (`0x0802F278`), suggesting a separately updated hot-shoe subsystem; what V1.02 changed there is unknown.
6. ⚠️ Whether AD600Pro II hardware tolerates AD600BM II limits ([AD600Pro II › Comparison with AD600BM II](../models/AD600ProII/README.md#comparison-with-ad600bm-ii-v102)).
