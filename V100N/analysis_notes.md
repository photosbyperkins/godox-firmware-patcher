# V100N Firmware Analysis (v1.04)

## Image layout

- Load address: **`0x08008000`** (application behind a bootloader)
- Initial SP `0x200AD678`, reset handler `0x0800829D`
- Listing: [`disasm/V100N_V1.04.asm`](disasm/V100N_V1.04.asm). About 80% of the image is GUI and font data.

## Version info

- Format string `0x416E8`: "Version: V%d.%d%d"
- Model string `0x416DF`: "Model: V100 N"
