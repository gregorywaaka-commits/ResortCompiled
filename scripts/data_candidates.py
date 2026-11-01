#!/usr/bin/env python3
"""data_candidates.py: find the data and bss addresses of another build for the UNMAPPED rows of its address_map.csv.

Data does not move with the functions. It moves with its section: from the PAL build to another build, every data
address shifts forward by an amount that only grows along the address range (inserted data pushes all later data).
This script:
  1. reads every data address that the other build's code uses (lis + addi/load/store pairs, and loads, stores and
     addi relative to r13 and r2),
  2. gives each UNMAPPED PAL data address its candidates: used addresses that lie PAL + a shift inside --band,
  3. picks, in address order, the shift path that changes as few times as possible and never goes down,
  4. writes the result to --table: a row with 1 candidate on the path is filled ("+cand"); every other row gets
     its candidates in the report for a check by hand.

    python3 scripts/data_candidates.py --target-dol <other main.dol> --table projects/wsr-sp2e01/address_map.csv
"""
import argparse
import csv
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sext(v):
    return v - 0x10000 if v & 0x8000 else v


def load_dol(path):
    d = path.read_bytes()
    off = struct.unpack(">18I", d[:72])
    addr = struct.unpack(">18I", d[72:144])
    size = struct.unpack(">18I", d[144:216])
    return d, off, addr, size


def sda_bases(words):
    """(r13, r2) from the first lis/addi or lis/ori pairs into r13 and r2."""
    regs = {}
    for i in range(len(words) - 1):
        w = words[i]
        if w >> 26 == 15 and (w >> 16) & 31 == 0 and (w >> 21) & 31 in (2, 13):
            r = (w >> 21) & 31
            n = words[i + 1]
            hi = (w & 0xFFFF) << 16
            if n >> 26 == 24 and (n >> 21) & 31 == r:
                regs.setdefault(r, hi | (n & 0xFFFF))
            elif n >> 26 == 14 and (n >> 21) & 31 == r:
                regs.setdefault(r, hi + sext(n & 0xFFFF))
        if 2 in regs and 13 in regs:
            break
    return regs.get(13), regs.get(2)


MEM_OPS = set(range(32, 56)) | {14}   # lwz..stfdu, and addi


def used_addresses(path):
    d, off, addr, size = load_dol(path)
    words = []
    for i in range(7):
        if size[i]:
            words += list(struct.unpack(">%dI" % (size[i] // 4), d[off[i]:off[i] + size[i]]))
    r13, r2 = sda_bases(words)
    used = set()
    hi = {}
    for w in words:
        op = w >> 26
        rd, ra, imm = (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        if op == 15 and ra == 0:             # lis rd, hi
            hi[rd] = imm << 16
            continue
        if op in MEM_OPS or op == 24:         # a load, a store, addi or ori through a base register
            if ra == 13 and r13:
                used.add(r13 + sext(imm))
            elif ra == 2 and r2:
                used.add(r2 + sext(imm))
            elif ra in hi:
                used.add((hi[ra] | imm) if op == 24 else hi[ra] + sext(imm))
        if op == 18 or op == 16 or (op == 19 and (w >> 1) & 0x3FF in (16, 528)):
            hi.clear()                        # a branch ends the reach of a lis
    return sorted(a for a in used if 0x80000000 <= a < 0x81800000), r13, r2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-dol", type=Path, required=True)
    ap.add_argument("--table", type=Path, required=True)
    ap.add_argument("--band", default="0x1100,0x2100", help="the lowest and highest shift PAL -> other build")
    ap.add_argument("--report", type=Path, help="the candidates of each row (default: next to --table)")
    a = ap.parse_args()
    lo, hi = (int(x, 16) for x in a.band.split(","))
    used, r13, r2 = used_addresses(a.target_dol)
    import bisect
    rows = list(csv.DictReader(open(a.table, newline="")))
    want = sorted((int(r["wsr_addr"].split("_", 1)[1], 16), r) for r in rows
                  if r["wsr_addr"].startswith("UNMAPPED") and r["how"].startswith(("data", "bss")))
    cands = []
    for p, _r in want:
        i, j = bisect.bisect_left(used, p + lo), bisect.bisect_right(used, p + hi)
        cands.append([u - p for u in used[i:j]])

    # The shift path: never goes down, changes as few times as possible (a row with no candidate is skipped).
    best = {}            # shift -> (changes, path)
    for k, cs in enumerate(cands):
        if not cs:
            continue
        nxt = {}
        for s in cs:
            opts = [(c + (0 if t == s else 1), path) for t, (c, path) in best.items() if t <= s]
            c, path = min(opts, key=lambda o: o[0]) if opts else (0, [])
            if s not in nxt or c < nxt[s][0]:
                nxt[s] = (c, path + [(k, s)])
        best = {**{t: v for t, v in best.items()}, **nxt} if False else nxt
    chosen = dict(min(best.values(), key=lambda v: v[0])[1]) if best else {}

    filled = 0
    lines = ["# Data candidates", "", "r13 0x%08X, r2 0x%08X, %d used data addresses, band %s." % (
        r13 or 0, r2 or 0, len(used), a.band), "", "| PAL address | symbol | how | path shift | candidates |",
        "|---|---|---|---|---|"]
    for k, (p, r) in enumerate(want):
        s = chosen.get(k)
        lines.append("| 0x%08X | %s | %s | %s | %s |" % (p, r["mkw_symbol"], r["how"], ("%+#x" % s) if s is not None
                     else "-", ", ".join("%+#x" % c for c in cands[k][:8]) or "none"))
        if s is not None and len(cands[k]) == 1:
            r["wsr_addr"] = "0x%08X" % (p + s)
            r["how"] = r["how"] + "+cand"
            filled += 1
    with open(a.table, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    rep = a.report or a.table.with_name("DATA_CANDIDATES.md")
    rep.write_text("\n".join(lines) + "\n")
    print("used data addresses %d; rows %d; filled with 1 candidate on the path %d; report %s" % (
        len(used), len(want), filled, rep))
    shifts = sorted({chosen[k] for k in chosen})
    print("path shifts:", ", ".join("%+#x" % s for s in shifts))


if __name__ == "__main__":
    main()
