#!/usr/bin/env python3
"""
Godox firmware disassembler (ARM Cortex-M / Thumb-2).

The images are application images that sit behind a bootloader. They are NOT
loaded at 0x08000000, so the load address has to be right or every absolute
address, literal-pool reference and cross-reference will be wrong.

Features
  * Known load address for each model, plus auto-detection for new images (--detect)
  * Recursive-descent code discovery seeded from the vector table, then a
    heuristic pass that looks for push{..,lr} prologues in areas not yet reached
  * Code and data are kept apart (literal pools and strings aren't decoded as instructions)
  * fn_/loc_ labels, literal-pool values, string previews, ADR targets, caller lists
  * Side outputs: <name>.functions.csv and <name>.strings.txt

Usage
  python tools/disasm.py                       # every model in MODELS
  python tools/disasm.py AD600ProII            # one model
  python tools/disasm.py --file X.bin --base 0x0800C000 [--out DIR]
  python tools/disasm.py --file X.bin --detect # list candidate load addresses

Requires capstone >= 5 (pip install capstone).
"""
import argparse
import csv
import os
import struct
import sys
from collections import defaultdict

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_MCLASS, CS_OP_IMM, CS_OP_MEM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# model -> (stock image path relative to repo root, load address)
MODELS = {
    "AD600ProII": ("AD600ProII/AD600PROII_v1.08.bin", 0x0800C000),
    "AD200ProII": ("AD200ProII/AD200ProII_V1.05.bin", 0x0800C000),
    "AD100ProII": ("AD100ProII/AD100ProII_RF433V1_07.bin", 0x0800C000),
    "V100N":      ("V100N/V100N_V1.04.bin",           0x08008000),
    "it30ProN":   ("it30ProN/iT30ProN_V1.02.bin",     0x0800C000),
}

FLASH_LO, FLASH_HI = 0x08000000, 0x08200000


def detect_base(d, step=0x400, lo=FLASH_LO, hi=FLASH_LO + 0x40000):
    """Score each candidate base by counting Thumb pointers (odd 0x08xxxxxx words)
    that land on a push{..,lr} prologue and even pointers that land on the start of
    an ASCII string. The real base scores far higher than any other."""
    ptrs = [w for w in (struct.unpack_from('<I', d, i)[0] for i in range(0, len(d) - 3, 4))
            if FLASH_LO <= w < FLASH_HI]
    res = []
    for base in range(lo, hi + 1, step):
        code = s = 0
        for w in ptrs:
            off = (w & ~1) - base
            if not (0 <= off < len(d) - 4):
                continue
            if w & 1:
                hw = struct.unpack_from('<H', d, off)[0]
                if (hw & 0xff00) == 0xb500 or hw == 0xe92d:
                    code += 1
            elif (off == 0 or d[off - 1] == 0) and all(32 <= c < 127 for c in d[off:off + 4]):
                s += 1
        res.append((code + s, code, s, base))
    res.sort(reverse=True)
    return res


class Image:
    def __init__(self, data, base):
        self.d = data
        self.base = base
        self.end = base + len(data)
        self.md = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_MCLASS)
        self.md.detail = True
        self.insns = {}                    # addr -> capstone insn
        self.data = set()                  # byte addrs known to be literal data
        self.funcs = set()
        self.labels = set()
        self.callers = defaultdict(set)    # func addr -> call sites
        self.dxref = defaultdict(set)      # data addr -> referencing insns

    # ---- helpers --------------------------------------------------------- #
    def inside(self, a):
        return self.base <= a < self.end

    def u32(self, a):
        o = a - self.base
        return struct.unpack_from('<I', self.d, o)[0] if 0 <= o <= len(self.d) - 4 else None

    def cstring(self, a, maxlen=64):
        o = a - self.base
        if not (0 <= o < len(self.d)):
            return None
        raw = self.d[o:o + maxlen].split(b'\0')[0]
        if len(raw) < 3:
            return None
        try:
            s = raw.decode('utf-8')
        except UnicodeDecodeError:
            return None
        return s if all(c.isprintable() or c in '\n\r\t' for c in s) else None

    def decode(self, a):
        o = a - self.base
        if not (0 <= o < len(self.d) - 1):
            return None
        for ins in self.md.disasm(self.d[o:o + 4], a, 1):
            return ins
        return None

    @staticmethod
    def is_return(ins):
        m, ops = ins.mnemonic, ins.op_str.strip()
        return ((m.startswith('pop') and 'pc' in ops) or
                (m.startswith('bx') and ops == 'lr') or
                (m.startswith(('ldr', 'mov')) and ops.startswith('pc')))

    def pc_ref(self, ins):
        """(target, size) for pc-relative loads and ADR, else None. size 0 = ADR."""
        m = ins.mnemonic
        if m.startswith('adr'):
            for op in ins.operands:
                if op.type == CS_OP_IMM:
                    return ((ins.address + 4) & ~3) + op.imm, 0
            return None
        if not m.startswith(('ldr', 'vldr')):
            return None
        for op in ins.operands:
            if op.type == CS_OP_MEM and ins.reg_name(op.mem.base) == 'pc':
                disp = op.mem.disp
                if getattr(op, 'subtracted', False) and disp > 0:
                    disp = -disp
                if m.startswith('ldrd') or (m.startswith('vldr') and ins.op_str.startswith('d')):
                    size = 8
                elif m.startswith(('ldrh', 'ldrsh')):
                    size = 2
                elif m.startswith(('ldrb', 'ldrsb')):
                    size = 1
                else:
                    size = 4
                return ((ins.address + 4) & ~3) + disp, size
        return None

    @staticmethod
    def imm_target(ins):
        for op in ins.operands:
            if op.type == CS_OP_IMM:
                return op.imm
        return None

    # ---- recursive descent ----------------------------------------------- #
    def explore(self, entry, is_func=True):
        entry &= ~1
        if not self.inside(entry) or entry in self.data:
            return
        if is_func:
            self.funcs.add(entry)
        self.labels.add(entry)
        work = [entry]
        while work:
            a = work.pop()
            while self.inside(a) and a not in self.insns and a not in self.data:
                ins = self.decode(a)
                if ins is None:
                    break
                self.insns[a] = ins
                m = ins.mnemonic
                ref = self.pc_ref(ins)
                if ref:
                    t, size = ref
                    self.dxref[t].add(a)
                    if size:
                        self.data.update(range(t, t + size))
                    if size == 4:
                        v = self.u32(t)
                        # literal that points at code? note it as a possible function pointer
                        if v and (v & 1) and self.inside(v & ~1):
                            self.pending.add(v & ~1)
                if m in ('bl', 'blx') and ins.op_str.startswith('#'):
                    t = self.imm_target(ins)
                    if t is not None and self.inside(t):
                        self.callers[t].add(a)
                        self.pending.add(t)
                elif m.startswith(('cbz', 'cbnz')) or (m.startswith('b') and not m.startswith(('bl', 'bx', 'bic', 'bfc', 'bfi', 'bkpt'))):
                    t = self.imm_target(ins)
                    if t is not None and self.inside(t):
                        self.labels.add(t)
                        work.append(t)
                    unconditional = m in ('b', 'b.w')
                    if unconditional:
                        break
                elif m.startswith(('tbb', 'tbh')):
                    self.walk_table(ins, work)
                    break
                if self.is_return(ins):
                    break
                if m in ('udf', 'bkpt'):
                    break
                a += ins.size

    def walk_table(self, ins, work):
        """Follow a tbb/tbh jump table placed directly after the instruction."""
        half = ins.mnemonic.startswith('tbh')
        tbl = ins.address + 4
        entries = []
        o = tbl - self.base
        esz = 2 if half else 1
        limit = None                       # lowest target seen = where the table must end
        i = 0
        while i < 256 and o + esz * (i + 1) <= len(self.d):
            pos = tbl + esz * i
            if limit is not None and pos >= limit:
                break
            e = struct.unpack_from('<H', self.d, o + 2 * i)[0] if half else self.d[o + i]
            tgt = tbl + 2 * e
            if tgt <= pos:                 # target inside the table -> not a real entry
                break
            entries.append(tgt)
            limit = tgt if limit is None else min(limit, tgt)
            i += 1
        size = (2 * len(entries)) if half else len(entries)
        self.data.update(range(tbl, tbl + size + (size & 1)))
        for t in entries:
            if self.inside(t):
                self.labels.add(t)
                work.append(t)

    def run(self):
        self.pending = set()
        # 1) vector table: initial SP, then handler pointers
        o = 0
        self.data.update(range(self.base, self.base + 4))
        for i in range(1, 256):
            v = self.u32(self.base + 4 * i)
            if v is None:
                break
            if v != 0 and not ((v & 1) and self.inside(v & ~1)):
                break
            self.data.update(range(self.base + 4 * i, self.base + 4 * i + 4))
            if v:
                self.pending.add(v & ~1)
        self.vector_end = self.base + 4 * i
        # 2) drain discovered functions
        self._drain()
        # 3) heuristic: push{..,lr} prologues in unexplored regions
        for _ in range(3):
            added = 0
            for off in range(0, len(self.d) - 4, 2):
                a = self.base + off
                if a in self.insns or a in self.data:
                    continue
                hw = struct.unpack_from('<H', self.d, off)[0]
                if (hw & 0xff00) == 0xb500 or (hw == 0xe92d and
                                                struct.unpack_from('<H', self.d, off + 2)[0] & 0x4000):
                    self.pending.add(a)
                    added += 1
            if not added:
                break
            self._drain()

    def _drain(self):
        while self.pending:
            a = self.pending.pop()
            if a not in self.insns:
                self.explore(a, True)
            else:
                self.funcs.add(a)
                self.labels.add(a)

    # ---- output ---------------------------------------------------------- #
    def name(self, a):
        if a in self.funcs:
            return f"fn_{a:08x}"
        if a in self.labels:
            return f"loc_{a:08x}"
        return None

    def comment(self, ins):
        parts = []
        ref = self.pc_ref(ins)
        if ref:
            t, size = ref
            if size == 4:
                v = self.u32(t)
                if v is not None:
                    parts.append(f"=0x{v:08x}")
                    if self.inside(v & ~1):
                        n = self.name(v & ~1)
                        if n:
                            parts.append(n)
                        s = self.cstring(v)
                        if s:
                            parts.append(repr(s))
            elif size == 0:
                parts.append(f"-> 0x{t:08x}")
                s = self.cstring(t)
                if s:
                    parts.append(repr(s))
        elif ins.mnemonic.startswith('b') or ins.mnemonic.startswith(('cbz', 'cbnz')):
            t = self.imm_target(ins)
            if t is not None:
                n = self.name(t)
                if n:
                    parts.append(n)
        return ('  ; ' + ' '.join(parts)) if parts else ''

    def write_asm(self, path, title):
        out = []
        w = out.append
        w(f"; {title}")
        w(f"; Load address 0x{self.base:08x}, size 0x{len(self.d):x}")
        w(f"; Functions: {len(self.funcs)}  Instructions: {len(self.insns)}")
        w("; Generated by tools/disasm.py")
        w("")
        a = self.base
        while a < self.end:
            if a in self.insns:
                ins = self.insns[a]
                if a in self.funcs:
                    cs = sorted(self.callers.get(a, ()))
                    w("")
                    w(f"; ---------------- {self.name(a)} ----------------")
                    if cs:
                        shown = ', '.join(f"0x{c:08x}" for c in cs[:12])
                        more = f" (+{len(cs) - 12} more)" if len(cs) > 12 else ""
                        w(f"; called from: {shown}{more}")
                    w(f"{self.name(a)}:")
                elif a in self.labels:
                    w(f"{self.name(a)}:")
                w(f"    {a:08x}  {ins.bytes.hex():<10} {ins.mnemonic:<9} {ins.op_str}{self.comment(ins)}")
                a += ins.size
                continue
            # data run: up to next instruction
            start = a
            while a < self.end and a not in self.insns:
                a += 1
            self._write_data(w, start, a)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out) + '\n')

    def _write_data(self, w, start, stop):
        a = start
        while a < stop:
            s = self.cstring(a, 256)
            if s and (a == start or self.d[a - self.base - 1] == 0) and a + len(s.encode()) <= stop:
                n = len(s.encode()) + 1
                w(f"    {a:08x}  .asciz {s!r}")
                a += n
                continue
            if a % 4 == 0 and a + 4 <= stop:
                v = self.u32(a)
                note = ''
                if self.inside(v & ~1):
                    nm = self.name(v & ~1)
                    if nm:
                        note = f"  ; {nm}"
                    else:
                        st = self.cstring(v)
                        if st:
                            note = f"  ; {st!r}"
                w(f"    {a:08x}  .word 0x{v:08x}{note}")
                a += 4
                continue
            w(f"    {a:08x}  .byte 0x{self.d[a - self.base]:02x}")
            a += 1

    def write_functions_csv(self, path):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            cw = csv.writer(f)
            cw.writerow(['address', 'file_offset', 'name', 'num_callers'])
            for a in sorted(self.funcs):
                cw.writerow([f"0x{a:08x}", f"0x{a - self.base:x}", self.name(a), len(self.callers.get(a, ()))])

    def write_strings(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            o = 0
            n = len(self.d)
            while o < n:
                if (o == 0 or self.d[o - 1] == 0):
                    s = self.cstring(self.base + o, 256)
                    if s and len(s) >= 4 and (self.base + o) not in self.insns:
                        refs = sorted(self.dxref.get(self.base + o, ()))
                        r = (' refs: ' + ', '.join(f"0x{x:08x}" for x in refs[:6])) if refs else ''
                        f.write(f"0x{self.base + o:08x} (+0x{o:x}): {s!r}{r}\n")
                        o += len(s.encode()) + 1
                        continue
                o += 1


def process(path, base, outdir, title):
    with open(path, 'rb') as f:
        data = f.read()
    img = Image(data, base)
    img.run()
    os.makedirs(outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(path))[0]
    img.write_asm(os.path.join(outdir, stem + '.asm'), title)
    img.write_functions_csv(os.path.join(outdir, stem + '.functions.csv'))
    img.write_strings(os.path.join(outdir, stem + '.strings.txt'))
    code_bytes = sum(i.size for i in img.insns.values())
    print(f"{title}: base=0x{base:08x} funcs={len(img.funcs)} insns={len(img.insns)} "
          f"code={100 * code_bytes / len(data):.1f}% -> {outdir}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('models', nargs='*', help='model names from MODELS (default: all)')
    ap.add_argument('--file', help='disassemble an arbitrary image')
    ap.add_argument('--base', type=lambda s: int(s, 0), help='load address for --file')
    ap.add_argument('--detect', action='store_true', help='print best candidate load addresses')
    ap.add_argument('--out', help='output directory')
    args = ap.parse_args()

    if args.file:
        with open(args.file, 'rb') as f:
            data = f.read()
        if args.detect or args.base is None:
            cands = detect_base(data)
            print("score  code  str   base")
            for sc, c, s, b in cands[:5]:
                print(f"{sc:5d} {c:5d} {s:4d}   0x{b:08x}")
            if args.detect:
                return
            args.base = cands[0][3]
            print(f"using detected base 0x{args.base:08x}")
        out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.file)), 'disasm')
        process(args.file, args.base, out, os.path.basename(args.file))
        return

    names = args.models or list(MODELS)
    for m in names:
        if m not in MODELS:
            sys.exit(f"unknown model {m}; known: {', '.join(MODELS)}")
        rel, base = MODELS[m]
        path = os.path.join(ROOT, rel)
        out = args.out or os.path.join(ROOT, m, 'disasm')
        process(path, base, out, f"{m} ({os.path.basename(rel)})")


if __name__ == '__main__':
    main()
