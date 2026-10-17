# Build changelog

The on-screen version encodes only the Godox base version and the tier, so a patcher fix that keeps the tier also keeps the version. Builds are therefore identified by SHA-256. Add a row whenever any output hash changes; current hashes are in each model's README and in [`tools/patcher_core.py`](tools/patcher_core.py).

| Date | Model | Tiers | Change | Superseded SHA-256 |
|---|---|---|---|---|
| 2026-10-14 | AD200Pro II | S, R, X | Added Tier S (`V1.05.01`): continuous H200 II head fan via I2C slave `0x5C` reg `0x01` in `fn_080237B0`. Tiers R and X now include the same fan patch; other heads are unaffected. Confirmed on hardware. | R `c1cb659d626d054e74943d1cf2513e503f31a11c8d97db697336caff16937bf0`<br>X `8da2612a2f2ea0f201f4d33f444ff708d259cfcd736ffcf1899dc4fa06ee450f` |
| 2026-10-11 | AD100Pro II | S, R, X | Initial release: S (`1.07.01`, fan on GPIOC pin 4), R (`1.07.02`, + 2× drain on both counters), X (`1.07.03`, + HSS table −20 %). | — |
| 2026-10-10 | All | All | Unified `<Godox version>.<tier code>` scheme and `patch.py` naming. Versions are patched as fixed text (digit immediates stay stock); the AD200Pro II and V100N settings-menu readouts are now patched too. Thermal patches unchanged. | Early experimental images |
| 2026-10-10 | iT30ProN | R, X | The patcher now recomputes the MD5 footer at `0xA8000`. Earlier images kept the stock MD5, which the on-chip bootloader (or a newer updater) may reject; `Godox_G3_v1.1.exe` itself only checks `size ≤ 1 MB`. | R `b9454658f204a4bf3a3cce4abb1b5f715132564b4925b7f638bc432e57ad5e78`<br>X `cee4c7bd45f6e30d44efc1f43b4eec0cd19443ecdefbbba08580f602125e8093` |
