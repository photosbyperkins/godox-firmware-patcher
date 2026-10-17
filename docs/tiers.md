# Tiers

What each custom build changes, what it leaves alone, and what that means per model. Addresses and byte diffs are in each model's README; the shared mechanism is described in [architecture.md](architecture.md).

## What the tiers act on

Every supported model limits heat in the same three independent ways (verified in the disassembly of all five):

1. **Single-burst limit.** Each flash adds a cost from a power-indexed table to a *primary accumulator*. At the threshold (6000, 6400 or 7500 points) the strobe enters a cooldown window with a per-flash charge lockout. The limit is set by the **table values** and the **threshold**.
2. **Repeated-burst recovery.** While the strobe is idle, a leaky-bucket routine drains the accumulator every 5 s (6 s on the iT30Pro), and an idle timeout clears it completely. Recovery speed is set by the **drain amount**. Most models also have a *secondary* short-window accumulator ("burst throttle") that adds a 0.5–2.5 s charge delay per flash once tripped.
3. **Thermistors.** Raw-ADC thresholds force a cooldown or raise an error (E2 on the AD600Pro II). **No tier changes this layer.**

## Tier definitions

| Code | Tier | Patches (cumulative) | Single-burst limit | Repeated-burst recovery | Intended use |
|---|---|---|---|---|---|
| `.01` | **S** Studio | Fan forced on | Stock | Stock, with extra cooling | AC power, modelling lamp, studio work |
| `.02` | **R** Recovery | S + drain amount doubled | Stock | ⚠️ 2× faster | Fast turnaround: portraits, events |
| `.03` | **X** Super | R + HSS cost table lowered ~20 % | ⚠️ +24–26 % HSS shots | ⚠️ 2× faster | Action and HSS bursts |
| `.04` | **R+** Recovery+ | R + secondary-counter drain doubled | Stock | ⚠️ 2× faster on both counters | Repeated short bursts below the throttle |
| `.05` | **X+** Super+ | R+ + X + secondary throttle bypassed | ⚠️ 80 shots at 1/1 with no mid-burst stutter | ⚠️ 2× faster on both counters | Maximum continuous bursts |

⚠️ marks a loosened protection. Every tier also rewrites the on-screen version strings ([README › Version scheme](../README.md#version-scheme)).

On the AD100Pro II, V100N and iT30Pro, Tier R already doubles both the primary and the secondary drain, because both live in the same routine; R+ and X+ exist only for the AD600Pro II, whose secondary drain is separate.

## Availability

| Model | S `.01` | R `.02` | X `.03` | R+ `.04` | X+ `.05` |
|---|---|---|---|---|---|
| AD600Pro II | `1.08.01` | `1.08.02` | `1.08.03` | `1.08.04` | `1.08.05` |
| AD200Pro II | `V1.05.01` | `V1.05.02` | `V1.05.03` | — | — |
| AD100Pro II | `1.07.01` | `1.07.02` | `1.07.03` | — | — |
| V100N | — (fanless) | `V1.04.02` | `V1.04.03` | — | — |
| iT30Pro (Nikon) | — (fanless) | `V1.02.02` | `V1.02.03` | — | — |

The AD600Pro II and AD100Pro II store the version as an 8-byte text slot, so their builds drop the leading `v`/`V`.

## Effect by model

Shots are counted from an empty counter in a continuous burst at 1/1 power until the primary cooldown: ⌈threshold ÷ cost⌉ (the firmware trips at `≥ threshold`). "Throttle from N" is the shot at which the secondary burst throttle starts adding a charge delay.

| Model | Stock 1/1 burst: normal / HSS | Tier X (HSS) | Primary drain, stock → R | Secondary drain, stock → R | Idle timeout |
|---|---|---|---|---|---|
| AD600Pro II | 80 / 64 (throttle from 38 / 30) | 80 (throttle from 38); **X+**: 80 / 80, no throttle | 8.0 → 16.0 pts/s (+1.25 pts/s with HSS off, unchanged) | 20 → 40 pts/s (R+, X+ only) | 120 s (secondary 30 s) |
| AD200Pro II | Group A 40 / 33; group B 60 / 50; H200 II 50 / 41 (throttle from 41 / 34) | A 41, B 63; H200 II 51 | A 25 → 50 pts/s; B 20 → 40 pts/s | H200 II only: 33 pts/s, unchanged | 300 s (H200 II secondary 180 s) |
| AD100Pro II | 60–100 by zoom (28 → 85 mm) / 60 (throttle from 32) | 75 (throttle from 40) | 5.0 → 10.0 pts/s | 6.0 → 12.0 pts/s | 300 s (secondary 180 s) |
| V100N | 70–100 by zoom (20 → 200 mm) / 60 (throttle from 35 / 30) | 75 (throttle from 38) | 10 → 20 pts/s | 10 → 20 pts/s | 300 s (secondary 120 s) |
| iT30Pro (Nikon) | 30 (diffuser retracted) or 20 (extended) / 40 (throttle from 10 / 7 / 14) | 50 (throttle from 17) | 13.3 → 26.7 pts/s | 13.3 → 26.7 pts/s | 300 s (secondary 240 s) |

AD200Pro II head groups: **A** = H200, H200 II, AD-L; **B** = H200R, H200J, H200J II, R200 (see [its README](../models/AD200ProII/README.md#table-selection)). The H200 II raises the primary threshold to 7500 but adds a 6000-point secondary throttle, so shots past 40 (normal) or 33 (HSS) get a 0.5–1.7 s recycle delay.

### What no tier changes

- Primary thresholds, cooldown windows, per-flash lockouts and idle timeouts.
- Secondary thresholds and unlatch timeouts (apart from the AD600Pro II X+ bypass).
- Thermistor paths, forced cooldowns, error codes, low-battery and low-voltage cutoffs. The fan patches run *after* the thermistor reads and keep the low-battery fan-off checks.
- **Continuous bursts.** Every flash outside cooldown resets the idle timer, and the drain only runs after 50 steps (60 on the iT30Pro) without a flash. Tiers R/R+ therefore change nothing during a burst and nothing after a pause longer than the idle timeout; they only matter for pauses in between.
- **Latched throttles.** Doubling the secondary drain only helps *before* the throttle trips. Once latched, it clears only after its full flash-free window.

## Safety

⚠️ Engineering reasoning, not a measurement.

- **What the counter covers.** In a burst, especially HSS, the IGBT die heats within milliseconds. Heat takes seconds to reach a thermistor on the board or heatsink, so the counter limits shots before the sensors can react.
- **Why the thermistors don't replace it.** Error E2 and the forced cooldowns are driven by those same slow sensors. Raising the counter's limits removes margin they can't make up.
- **Why the fan doesn't replace it.** A fan cools the heatsink. Over milliseconds, die temperature depends on the die-to-case path, which airflow barely changes.
- **Why AC power doesn't change it.** The IGBT heats from the discharge itself, whatever the power source.
- **What's at stake.** These units switch a 350–450 V capacitor bank. A failed IGBT can short, damage the board or start a fire.
- **Fanless models.** The V100N and especially the ~120 g iT30Pro have little thermal mass and no fan. Tier R (stock single-burst limit) is the conservative choice there.

Lower-risk options that change no protection logic:

- Tier S on models with a fan (AD600Pro II branch patch at `0x080174BC`, AD100Pro II at `0x080143A2`, AD200Pro II with an H200 II head).
- An extension head (e.g. H600P) to move the tube away from the body electronics.
- Turning the modelling lamp off during bursts.
- Two strobes at lower power instead of one at full power.
- Renewing the IGBT/diode thermal interface material.
