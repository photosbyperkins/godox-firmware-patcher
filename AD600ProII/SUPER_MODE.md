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
| Effect | ✅ **Confirmed on hardware (2026-10-10):** `fn_08017480` forces fan level 2 in `0x20000106`, skipping only the fan-level decision tree (`0x080174BE`–`0x080174F8`: NTC states, cooldown `0x200000DC`, secondary latch `0x2000004C` = `[r5,#6]`, heat stage `0x2000004E` = `[r5,#8]`, and modeling lamp `[0x2000007B] != 0 && [0x20000007] > 20`). The chassis fan runs continuously at high speed, actively circulating cooling airflow over the heatsink. |
| Thermistor routines still run | ✅ `fn_080172D8` (NTC B: main board / IGBT) and `fn_08017120` (NTC A: flash head / modeling lamp) are called before the branch (`0x080174AE`, `0x080174B2`). |
| Fan driver still honors off flags | ✅ `fn_08010E74` forces the fan off when `0x200000A6` (low battery cutoff, gauge ≤ 3) or `0x20000080` (low-voltage power-down latch, raw ADC < 0x1BA) = 1. |
| Loosens any limit? | No. |

## 2. Heat-counter drain 40 → 80

| | |
|---|---|
| Change | Primary: file offset `0x76CC` (`28` → `50`, `cmp r1,#0x50`) and `0x76D0` (`28` → `50`, `subs r1,#0x50`). In Tier R+/X+, also secondary: `0x7744` and `0x7748` (`28` → `50`). |
| Effect | ✅ Primary: when `[+0xC]` idle timer is a multiple of 50 (every 5.0 s), 80 points are drained instead of 40 (plus the stock `-5 / 4.0 s` extra drain at `0x080136D8` when HSS is off `[0x20000E80+3] == 0` ✅). Secondary (Tier R+/X+): when `[+0x14]` is a multiple of 20 (every 2.0 s), 80 points are drained instead of 40, accelerating **pre-latch (`[r5,#6] == 0`) recovery between bursts**. Once the secondary latch `0x2000004C` (`[r5,#6]`) is set at 3000 pts, draining `[+0x16]` to 0 does not clear the latch—it only clears when `[+0x14]` expires after 30.0 s with zero flashes (`0x0801373A`), or is bypassed altogether in Tier X+ (`0x761D`: `D3` → `E0`). |
| During a continuous burst | ✅ **No effect.** Every flash resets the primary idle timer to 1200 (`0x0801357C`) outside cooldown and the secondary timer to 300 (`0x08013604`/`0x0801360C`). |
| After a long pause | ✅ The primary counter resets to zero after 1200 steps (120.0 s) with no flash outside cooldown (`0x080136C4`), and the secondary state resets after 300 steps (30.0 s) with no flash (`0x08013734`–`0x08013740`). |
| Time per step | ✅ **0.100 s (100 ms) nominal.** Derived from TIM14 200 µs base × 25 (`0x0801F4DC`) × 20 (`fn_08013694`), based on internal HSI 16 MHz PLL at 168 MHz ±1%, gated by `[0x2000016E] != 0` and `[0x200000A7] == 0`. The 50-step primary drain interval is **5.000 s nominal** (8.00 → 16.00 pts/s, or 9.25 → 17.25 pts/s when HSS is off). |
| Loosens any limit? | ⚠️ Yes, during pauses (and Tier X+ bypasses the 38-shot secondary pause). |

## 3. Second heat table lowered (HSS table `0x080398F0`)

| | |
|---|---|
| Change | 28 halfwords at file offset `0x2D8F0` (`0x080398F0`). |
| Original values | `25×6, 27×3, 30×4, 35×2, 45×3, 55×3, 70×3, 90×3, 100` |
| Patched values | `20×9, 25×6, 32×3, 40×3, 50×3, 64×3, 80` |
| When the table is used | ✅ Only when `0x200000DD` = 1 (`0x08013580`). |
| Is it HSS? | ✅ **Code verified end-to-end (🔶 physical optical train unverified on hardware).** The UI `'HSS'` icon (`fn_0801BD28` at `0x0801BD90`) is driven by `[0x20000E80,#3]` (`fn_0801BBE0` at `0x0801BDCC`) and bit 4 (`0x10`) of `0x2000009D`, which sets trigger mode `0x200000D5 = 0x1A` (`0x08010D28`/`0x0801FBC0`). In `fn_0801F6C0` (105-iteration pulse sequence at `0x0801F796`, `cmp r4, #0x69`) and `fn_0801F674` (`0x0801F692`), mode `0x1A` writes `1` to `0x200000DD` before calling `fn_080134E4`. Standard flash paths (`0x08016D4C`, `0x08016DB2`, and mode `0x0A`) write `0`. |
| Shots to threshold | ✅ Traced from power representation: $P=0$ corresponds to 1/1 power at top index 27. 6400 ÷ 100 = 64 shots stock, patched to 6400 ÷ 80 = 80 shots (+25%). |
| Loosens any limit? | ⚠️ Yes, in HSS mode. |

## 4. Version strings → 1.08.TT

| | |
|---|---|
| Change | File offsets `0xF738` and `0x123FC`. Each holds `v1.08` in an 8-byte slot (`v1.08` + 3 NUL bytes). The patcher replaces the whole slot with `1.08.TT` + NUL, where `TT` is the tier code (`01` S … `05` X+). The leading `v` is dropped because 7 characters is the most the slot can hold. [`tools/fwversion.py`](../tools/fwversion.py) refuses a version that doesn't fit. |
| Status | ✅ **Both screens verified in code & confirmed on hardware.** Offset `0xF738` (`0x0801B738`) is rendered inside the dedicated Device Info sub-screen (`fn_0801B6C0` at `0x0801B6FC`); offset `0x123FC` (`0x0801E3FC`) is rendered at `0x0801E25C` (EN) and `0x0801E49C` (CN) in `fn_0801DE80` as the right-aligned version preview on Row 15 (`'Device info'` / `'设备信息'`) of the Settings Menu (`MENU`) list. Restoring OEM firmware with G3 is confirmed by user. |

---

## Risks and open questions

- ⚠️ **Changes 2 and 3 loosen the shot-limit heat counter,** which covers fast IGBT die heating the thermistors can't detect in time. Error E2 is driven by those same slow sensors, so leaving it untouched doesn't make up for this. See [FINDINGS.md §4](../FINDINGS.md#4-why-the-heat-counter-matters-for-safety).
- ✅ **PC updater (`Godox_G3_v1.1.exe`) verified:** Disassembly at `0x00404D1B` confirms G3 only checks `file_size <= 0x100000` (1 MB) and does not compute or verify any checksum, hash, or signature on `.bin` files; AD600Pro II custom builds also flash and boot cleanly on hardware.
- ✅ Multi-pulse trigger train (`0x1A` → `0x200000DD = 1`) linked end-to-end to UI `'HSS'` mode in code; hardware optical confirmation remains open (🔶).
- ✅ Step timer period verified: 1 step = 0.100 s (100 ms) nominal. 50 steps = 5.000 s nominal.
- ✅ Standby/sleep flags verified: `0x200000A6` (low battery gauge ≤ 3) and `0x20000080` (low-voltage latch raw ADC < 0x1BA).
- ✅ Multi-mode table (`0x08039A65`) verified as stroboscopic limit table (7 rows × 13 columns, $P=20 \dots 80$).

## Byte diff by profile
 
| File offset | Old | New | Purpose | Profile |
|---|---|---|---|---|
| `0xB4BD` | `D0` | `E0` | Fan branch (Level 2) | S, R, X, R+, X+ |
| `0x76CC` | `28` | `50` | Drain compare (80 pts) | R, X, R+, X+ |
| `0x76D0` | `28` | `50` | Drain subtract (80 pts) | R, X, R+, X+ |
| `0x7744` | `28` | `50` | Secondary drain compare (80 pts, pre-latch) | R+, X+ |
| `0x7748` | `28` | `50` | Secondary drain subtract (80 pts, pre-latch) | R+, X+ |
| `0x761D` | `D3` | `E0` | Burst throttle `blo` → `b` (`0x0801361C`) | X+ only |
| `0x2D8F0`–`0x2D927` | see §3 | see §3 | Second heat table (28 halfwords) | X, X+ |
| `0xF738`–`0xF73F` | `v1.08` | `1.08.TT` | Device info sub-screen string (`fn_0801B6C0`) | all |
| `0x123FC`–`0x12403` | `v1.08` | `1.08.TT` | Settings menu Row 15 version string (`fn_0801DE80`) ✅ | all |

## Rebuilding

```
python AD600ProII\patch.py
```
