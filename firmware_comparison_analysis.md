# Cross-Model Firmware Comparison

**Last audited:** 2026-10-09. Status marks: ✅ verified in code · ⚠️ unverified ([legend](FINDINGS.md#status-legend)).

## Shared Architectural Design

✅ All three target flash models (AD600Pro II, AD200Pro II, and V100N) run plaintext Thumb-2 code behind a factory bootloader. AD600Pro II and AD200Pro II run on STM32F4-class MCUs (HSI 16 MHz PLL at 168 MHz). V100N runs on a GD32F450/470 MCU (IRC16M PLL at 240 MHz, TIMERSEL bit set). All three utilize a synchronized algorithmic heat-accumulation engine: pre-calibrated points are accumulated per shot from firmware lookup tables, while an independent timer ISR drains accumulated points during pauses once every 20 calls and on timer % 50.

Across all three models, timer steps execute at **0.100 s (100 ms)** nominal (derived from hardware timer ISRs with dual-stage prescalers, based on internal RC oscillators ±1%; GD32F4 IRC16M at 240 MHz on V100N), gated by active run flags. The 50-step drain interval is **5.000 s** nominal.

| Feature / Parameter | Godox AD600Pro II | Godox AD200Pro II | Godox AD100Pro II | Godox V100N | Godox iT30ProN |
|---|---|---|---|---|---|
| **Base Load Address** | `0x0800C000` | `0x0800C000` | `0x0800C000` | `0x08008000` | `0x0800C000` |
| **Step Timing** | ✅ 0.100 s (100 ms) nominal | ✅ 0.100 s (100 ms) nominal | ✅ 0.100 s (100 ms) nominal | ✅ 0.100 s (100 ms) nominal | ✅ 0.100 s (100 ms) nominal |
| **Heat Accumulator** | ✅ `0x20000054` (RAM) | ✅ `[0x2000015C,#0xC]` | ✅ `[0x20000028,#0x20]` (+ secondary `[+0x28]`) | ✅ `[0x20000594,#8]` (+ secondary `[+0x10]`) | ✅ `[0x200005F4,#8]` (+ secondary `[+0x10]`) |
| **Point Addition Routine** | ✅ `fn_080134E4` | ✅ `fn_08012018` | ✅ `fn_08010fec` | ✅ `fn_0800EFBC` (10 callers) | ✅ `fn_08013B54` |
| **Point Decay Routine** | ✅ `fn_08013694` | ✅ `fn_08012370` | ✅ `fn_080111f4` | ✅ `fn_0800F3F4` | ✅ `fn_0801412C` |
| **Stock Decay Rate** | ✅ 40 pts / 5.0 s (8.0 pts/s) | ✅ Heads {0, 1}: 125 / 5.0 s (25 pts/s)<br>Heads {2, 3, 4}: 100 / 5.0 s (20 pts/s) | ✅ Primary: 25 / 5.0 s (5.0 pts/s)<br>Secondary: 30 / 5.0 s (6.0 pts/s) | ✅ 50 pts / 5.0 s (10 pts/s on each accumulator) | ✅ 80 pts / 6.0 s (13.33 pts/s on both accumulators) |
| **Tier R / X Patched Decay** | ✅ 80 pts / 5.0 s (16.0 pts/s) | ✅ Heads {0, 1}: 250 / 5.0 s (50 pts/s)<br>Heads {2, 3, 4}: 200 / 5.0 s (40 pts/s) | ✅ Primary: 50 / 5.0 s (10.0 pts/s)<br>Secondary: 60 / 5.0 s (12.0 pts/s) | ✅ 100 pts / 5.0 s (20 pts/s on each accumulator) | ✅ 160 pts / 6.0 s (26.67 pts/s on both accumulators) |
| **Cooldown Threshold** | ✅ 6400 points | ✅ 6000 points (7500 with H200 II / H200J II heads, `0x20000095` in {6, 7}) | ✅ 6000 points (primary cooldown) / 3200 (secondary burst delay) | ✅ 6000 points (primary cooldown) / 3000 (secondary drives 0–1.5 s charge delay) | ✅ 6000 points (primary, 600 s throttled-cooldown window) / 2000 (secondary drives 0.5–2.5 s charge inhibit) |
| **Idle / Reset Timeout** | ✅ 3000 steps (300 s) post-trip window; 1200 (120 s) idle reset outside cooldown | ✅ 3000 steps (300 s) idle reset outside cooldown; 1800 (180 s) secondary timer | ✅ 3000 steps (300 s) idle reset outside cooldown; 1800 (180 s) secondary timer | ✅ 3000 steps (300 s) idle reset outside cooldown; secondary clears at 1200 (120 s) | ✅ 3000 steps (300 s) idle reset outside cooldown; secondary clears at 2400 (240 s) |
| **Active Fan Control** | ✅ `fn_08017480` (Level 0, 1, 2) | ⚠️ None located in body firmware. The `H200 II` fresnel head has a fan (confirmed on hardware); control path unidentified | ✅ `fn_08014370` (GPIOC Pin 4 on/off, trips at > 1200 pts) | ⚠️ None located in firmware (absence of evidence) | ⚠️ None located in firmware (fanless 120g body) |
| **Hardware Thermal Protection** | ✅ Dual NTC thermistors (raw ADC: NTC B < 49.69 trips E2; NTC A/B < 132 trips 9 s forced cooldown; fan stages at < 271 / < 356) | 🔶 ADC1 IN2 float < 541.42 sets `0x20000124`; counter sets `0x2000005E` (sensor type unverified ⚠️) | ✅ One NTC, raw ADC `0x20000010` (`fn_08014234`): < 114.59 forces cooldown (recovers ≥ 204.14); fan states 2 / 1 at < 271.06 / < 356.03 | ✅ Real NTC path via ADC0 DMA (`0x200004B6`): < 98.98 raw count trips forced cooldown (`fn_0800D544`) | ✅ Two NTCs: `0x20000520` raw 20–203 and `0x20000522` raw < 183 (10-sample debounce) force the 600 s cooldown via `fn_0800FA1C` |
| **HSS Multi-Pulse Table** | 🔶 `0x080398F0` (28 halfwords) | 🔶 Tables C & D (`0x080414FE`/`530`) | 🔶 Table Set 2 (`0x08032F48`, 11×25; flag `0x20000035` setter not located) | 🔶 ALT Matrix (`0x08051930`, 11×22) | 🔶 Multi-pulse matrix (`0x0804FFAC`, 11×22; 80-pulse loop) |
| **Tier X Reduction** | 🔶 ~20% (64 → 80 shots at 1/1) | 🔶 ~20% (33 → 40, 50 → 62 shots) | 🔶 ~20% across all 11 modes (60 → 75 shots at 1/1) | 🔶 20% across all 11 rows (60 → 75) | 🔶 ~20% across all 11 rows (40 → 50 shots at 1/1) |

---

## Architectural Distinctions

1. **Active vs. Passive Cooling:**
   - The **AD600Pro II** features a PWM-driven active cooling fan with physical hardware thermistor monitoring. Tier S, R, and X firmware profiles latch this fan to continuous 100% duty cycle (Level 2) for maximum continuous heat dissipation.
   - The **AD100Pro II** features an internal chassis cooling fan driven by GPIOC Pin 4 (`fn_08014370`). In factory stock firmware, it only engages once heat points exceed 1200 (`0x4B0`) or elevated thermistor limits trip. In custom profiles (Tier S, R, X), the fan runs continuously while awake to actively exhaust tube heat.
   - The **AD200Pro II** body has no internal fan, but its `H200 II` fresnel head has a built-in cooling fan (confirmed on hardware). No routine that controls it has been located in the body firmware, so it's unknown whether the body or the head drives it. With other heads, the AD200Pro II relies on passive cooling.
   - The **V100N** and **iT30ProN** have no fan driver routines in firmware and rely on passive thermal dissipation through the chassis and head. On the ultra-compact ~120g iT30ProN, thermal density is particularly high, making Tier R (stock single-burst limits + 2× recovery drain) the safest recommended upgrade profile.

2. **Per-Shot Table Architectures:**
   - **AD600Pro II:** Utilizes a single 1D table of 28 halfwords (indexed by power level 0–27).
   - **AD200Pro II:** Utilizes dual modular selectors across 4 distinct 25-entry halfword tables (Tables A, B, C, D) depending on attached head code (`0x20000093` / `0x95`: 1=H200, 2=H200R, 3=H200J, 4=R200, 5=AD-L, 6=H200 II, 7=H200J II) and whether HSS is active.
   - **AD100Pro II:** Utilizes two sets of 11-mode × 25-power tables (Table Set 1 at `0x08032D22` for standard/manual, Table Set 2 at `0x08032F48`, probably HSS 🔶). Row = `[0x20000001] & 7` (rows 8–10 unreachable; meaning untraced ⚠️). Row 0 full power is 100 points ($6000/100 = 60$ shots); rows 4–7 are 60 points ($6000/60 = 100$ shots).
   - **V100N:** Utilizes a full 2D matrix (11 rows × 22 columns) indexed by zoom focal length (Row = index + 1 from table `0x08051694`: Row 0 = special `0x200004DE` flag; Rows 1–10 = 20, 24, 28, 35, 50, 70, 80, 105, 135, 200 mm) and output power level (columns 0–21).
   - **iT30ProN:** Utilizes a 2D matrix (11 rows × 22 columns). Only rows 0 and 1 are used, selected by a debounced GPIOC pin 15 input (`0x200005B9`; physical meaning unverified ⚠️). Row 0 = 300 pts at the top column (20 shots), row 1 = 200 pts (30 shots). HSS uses table `0x0804FFAC` (150 pts at 1/1 = 40 shots).
3. **Image Integrity Footer:**
   - The **iT30ProN** image ends with an MD5 footer (MD5 of `file[0:0xA8000]`, filename, length, magic `AA 55 66 99 77 88 22 33`). None of the other models have one. Patchers must recompute it. The app also shows a "Hot Shoe Upgrading" screen (`0x0802F278`), which suggests a separately updated hot-shoe subsystem (purpose of the V1.02 changes unverified ⚠️).
