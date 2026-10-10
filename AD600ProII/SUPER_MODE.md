# AD600Pro II — Patch Reference (`1.08.0x` builds)

**Patched image:** `AD600PROII_v1.08.03_super.bin`, 407,384 bytes, SHA-256 `a9b4b0f5fc18a44d1e0af5a1e03db9da199fabfdcc4737c6a7f8f734cd780d27`
**Also available:** `AD600PROII_v1.08.01_studio.bin` (Tier S), `AD600PROII_v1.08.02_recovery.bin` (Tier R), `AD600PROII_v1.08.04_recovery_plus.bin` (Tier R+), `AD600PROII_v1.08.05_super_plus.bin` (Tier X+). All hashes: [root README §2.1](../README.md#21-godox-ad600pro-ii-focus-model).
**Patcher:** [`patch.py`](patch.py).
**Hardware testing:** Flashing, `1.08.04` screen display, and continuous Level 2 chassis fan operation **confirmed on hardware** (2026-10-10). Restoring OEM stock firmware via Godox G3 confirmed.

Status marks follow [FINDINGS.md](../FINDINGS.md#status-legend): ✅ verified in code · 🔶 partial · ⚠️ unverified.

---

## 1. Fan always at level 2

| | |
|---|---|
| Change | File offset `0xB4BD`: `D0` → `E0`. At `0x080174BC`, `beq 0x080174FA` becomes `b 0x080174FA`. |
| Effect | ✅ **Confirmed on hardware (2026-10-10):** `fn_08017480` forces fan level 2 in `0x20000106`. The chassis fan runs continuously at high speed, actively circulating cooling airflow over the heatsink. |
| Thermistor routines still run | ✅ `fn_080172D8` and `fn_08017120` are called before the branch (`0x080174AE`, `0x080174B2`). |
| Fan driver still honors off flags | ✅ `fn_08010E74` forces the fan off when `0x200000A6` (low battery cutoff, gauge ≤ 3) or `0x20000080` (low-voltage power-down latch, raw ADC < 0x1BA) = 1. |
| Loosens any limit? | No. |

## 2. Heat-counter drain 40 → 80

| | |
|---|---|
| Change | File offset `0x76CC`: `28` → `50` (`cmp r1,#0x50`). File offset `0x76D0`: `28` → `50` (`subs r1,#0x50`). |
| Effect | ✅ When the idle timer is a multiple of 50, 80 points are drained instead of 40. |
| During a continuous burst | ✅ **No effect.** Every flash resets the idle timer to 1200 (`0x0801357C`) outside cooldown. The drain only fires after 50 timer steps with no flash. |
| After a long pause | ✅ The counter resets to zero after 1200 steps (120.0 s) with no flash outside cooldown (`0x080136C4`). |
| Time per step | ✅ **0.100 s (100 ms) nominal.** Derived from TIM14 200 µs base × 25 (`0x0801F4DC`) × 20 (`fn_08013694`), based on internal HSI 16 MHz PLL at 168 MHz ±1%, gated by `[0x2000016E] != 0` and `[0x200000A7] == 0`. The 50-step drain interval is **5.000 s nominal**. Drain rate doubles from 8.00 pts/s (stock) to 16.00 pts/s (patched). |
| Loosens any limit? | ⚠️ Yes, during pauses. |

## 3. Second heat table lowered (HSS table `0x080398F0`)

| | |
|---|---|
| Change | 28 halfwords at file offset `0x2D8F0` (`0x080398F0`). |
| Original values | `25×6, 27×3, 30×4, 35×2, 45×3, 55×3, 70×3, 90×3, 100` |
| Patched values | `20×9, 25×6, 32×3, 40×3, 50×3, 64×3, 80` |
| When the table is used | ✅ Only when `0x200000DD` = 1 (`0x08013580`). |
| Is it HSS? | 🔶 **Code verified multi-pulse loop.** In `fn_0801F6C0`, trigger mode `0x1A` executes a 105-iteration pulse sequence (`0x0801F796`, `cmp r4, #0x69`), then writes 1 to `0x200000DD` (`0x0801F7C2`) before calling `fn_080134E4`. Standard flash paths (`0x08016D4C`, `0x08016DB2`, and `fn_0801F6C0` mode `0x0A`) write 0. Physical optical train unverified on hardware. |
| Shots to threshold | ✅ Traced from power representation: $P=0$ corresponds to 1/1 power at top index 27. 6400 ÷ 100 = 64 shots stock, patched to 6400 ÷ 80 = 80 shots (+25%). |
| Loosens any limit? | ⚠️ Yes, in HSS mode. |

## 4. Version strings → 1.08.TT

| | |
|---|---|
| Change | File offsets `0xF738` and `0x123FC`. Each holds `v1.08` in an 8-byte slot (`v1.08` + 3 NUL bytes). The patcher replaces the whole slot with `1.08.TT` + NUL, where `TT` is the tier code (`01` S … `05` X+). The leading `v` is dropped because 7 characters is the most the slot can hold. [`tools/fwversion.py`](../tools/fwversion.py) refuses a version that doesn't fit. |
| Status | ✅ Bytes verified. Offset `0xF738` (`0x0801B738`) is on Device Info screen; display screen for `0x123FC` (`0x0801E3FC`) unverified (⚠️). Restoring OEM firmware with G3 is confirmed by user. |

---

## Risks and open questions

- ⚠️ **Changes 2 and 3 loosen the shot-limit heat counter,** which covers fast IGBT die heating the thermistors can't detect in time. Error E2 is driven by those same slow sensors, so leaving it untouched doesn't make up for this. See [FINDINGS.md §4](../FINDINGS.md#4-why-the-heat-counter-matters-for-safety).
- ⚠️ Unknown whether the update image is checksummed or signed by the bootloader/G3.
- 🔶 Multi-pulse trigger train matches HSS in code; hardware optical confirmation remains open.
- ✅ Step timer period verified: 1 step = 0.100 s (100 ms) nominal. 50 steps = 5.000 s nominal.
- ✅ Standby/sleep flags verified: `0x200000A6` (low battery gauge ≤ 3) and `0x20000080` (low-voltage latch raw ADC < 0x1BA).
- ✅ Multi-mode table (`0x08039A65`) verified as stroboscopic limit table (7 rows × 13 columns, $P=20 \dots 80$).

## Byte diff by profile
 
| File offset | Old | New | Purpose | Profile |
|---|---|---|---|---|
| `0xB4BD` | `D0` | `E0` | Fan branch (Level 2) | S, R, X, R+, X+ |
| `0x76CC` | `28` | `50` | Drain compare (80 pts) | R, X, R+, X+ |
| `0x76D0` | `28` | `50` | Drain subtract (80 pts) | R, X, R+, X+ |
| `0x7744` | `28` | `50` | Secondary drain compare (80 pts) | R+, X+ |
| `0x7748` | `28` | `50` | Secondary drain subtract (80 pts) | R+, X+ |
| `0x761D` | `D3` | `E0` | Burst throttle `blo` → `b` (`0x0801361C`) | X+ only |
| `0x2D8F0`–`0x2D927` | see §3 | see §3 | Second heat table (28 halfwords) | X, X+ |
| `0xF738`–`0xF73F` | `v1.08` | `1.08.TT` | Device info screen string | all |
| `0x123FC`–`0x12403` | `v1.08` | `1.08.TT` | Alternate version string (⚠️ screen unconfirmed) | all |

## Rebuilding

```
python AD600ProII\patch.py
```
