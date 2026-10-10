# AD200ProII Firmware Analysis (v1.05)

## Image layout

- Load address: **`0x0800C000`** (application behind a bootloader)
- Initial SP `0x1000F000` (stack in CCM-style RAM at `0x10000000`), reset handler `0x0800C269`
- Listing: [`disasm/AD200ProII_V1.05.asm`](disasm/AD200ProII_V1.05.asm)

## Version info

- Format string `0x2EDCC`: "Version: V%d.%d%d" (the version digits are numeric constants in code)
- Model string `0x2EDDF`: "Model: AD200ProII"
