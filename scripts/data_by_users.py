#!/usr/bin/env python3
"""data_by_users.py: find the address of each UNMAPPED data row from the functions that use its variable.

A data row of the PAL table has a variable name (from a decomp's symbols, --names). A decompiled SDK source tree
(--source, for example a Wii decomp's src/revolution) shows which functions use that variable. This script finds
those functions in the other build's map, reads every data address each of them accesses in the other build's
code (lis + addi/load/store pairs, and r13/r2 relative accesses), and keeps the address that every user function
accesses, inside the shift band of its section. 1 such address fills the row ("+users"); more go to the report.
No game code is copied: the decomp source is read only for which function uses which variable.

    python3 scripts/data_by_users.py --target-dol <other main.dol> --map projects/wsr-sp2e01/MAP.txt \
        --names <data names file> --source <decomp>/src --table projects/wsr-sp2e01/address_map.csv
"""
import argparse
import bisect
import csv
import os
import re
import struct
from pathlib import Path

FUNC_DEF = re.compile(r"^(?:static\s+|inline\s+|extern\s+)*[\w\s\*]+?\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{?\s*$")
WORD = re.compile(r"[A-Za-z_@]\w*")


def users_in_source(root):
    """{variable name: set of function names whose body uses it}, from C and C++ files under root."""
    use = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            if not f.endswith((".c", ".cpp", ".cc")):
                continue
            cur, depth = None, 0
            for line in open(os.path.join(dp, f), encoding="utf-8", errors="replace"):
                if depth == 0:
                    m = FUNC_DEF.match(line.strip())
                    if m and m.group(1) not in ("if", "for", "while", "switch", "return", "sizeof"):
                        cur = m.group(1)
                if cur and depth > 0:
                    for w in WORD.findall(line):
                        use.setdefault(w, set()).add(cur)
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    depth, cur = 0, (cur if "{" not in line else cur)
    return use


def sext(v):
    return v - 0x10000 if v & 0x8000 else v


def accesses(dol_path, funcs):
    """{function start: set of data addresses its code accesses}, and the r13 and r2 bases."""
    d = Path(dol_path).read_bytes()
    off = struct.unpack(">18I", d[:72])
    addr = struct.unpack(">18I", d[72:144])
    size = struct.unpack(">18I", d[144:216])
    starts = sorted(funcs)
    r13 = r2 = None
    out = {}
    words = []
    for s in range(7):
        for k in range(size[s] // 4):
            words.append((addr[s] + 4 * k, struct.unpack(">I", d[off[s] + 4 * k: off[s] + 4 * k + 4])[0]))
    for i in range(len(words) - 1):          # r13 and r2 from their first lis/addi or lis/ori pair
        pc, w = words[i]
        if w >> 26 == 15 and (w >> 16) & 31 == 0 and (w >> 21) & 31 in (2, 13):
            n = words[i + 1][1]
            v = ((w & 0xFFFF) << 16) | (n & 0xFFFF) if n >> 26 == 24 else ((w & 0xFFFF) << 16) + sext(n & 0xFFFF)
            if (w >> 21) & 31 == 13 and r13 is None:
                r13 = v
            if (w >> 21) & 31 == 2 and r2 is None:
                r2 = v
        if r13 and r2:
            break
    hi = {}
    for pc, w in words:
        op, rd, ra, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 0xFFFF
        if op == 15 and ra == 0:
            hi[rd] = imm << 16
            continue
        t = None
        if op in set(range(32, 56)) | {14, 24}:
            if ra == 13:
                t = r13 + sext(imm)
            elif ra == 2:
                t = r2 + sext(imm)
            elif ra in hi:
                t = (hi[ra] | imm) if op == 24 else hi[ra] + sext(imm)
        if t is not None:
            i = bisect.bisect_right(starts, pc) - 1
            if i >= 0:
                out.setdefault(starts[i], set()).add(t)
        if op in (16, 18) or (op == 19 and (w >> 1) & 0x3FF in (16, 528)):
            hi.clear()
    return out, r13, r2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-dol", required=True)
    ap.add_argument("--map", type=Path, required=True)
    ap.add_argument("--names", type=Path, required=True, help="lines: <mkw_addr> <section> <name> +0x<offset>")
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--table", type=Path, required=True)
    ap.add_argument("--bands", required=True, help="PAL address ranges and shift ranges: lo-hi:slo-shi,...")
    ap.add_argument("--pal-table", type=Path, default=Path(__file__).resolve().parent.parent / "projects" / "wsr"
                    / "address_map.csv")
    ap.add_argument("--min-users-band", type=lambda x: int(x, 0), default=0x2000,
                    help="a band wider than this needs 2 or more agreeing user functions")
    ap.add_argument("--near", type=lambda x: int(x, 0), default=0x100, help="the reach of an exact row's shift")
    a = ap.parse_args()
    bands = []
    for part in a.bands.split(","):
        rng, sh = part.split(":")
        lo, hi = (int(x, 16) for x in rng.split("-"))
        slo, shi = (int(x, 16) for x in sh.split("-"))
        bands.append((lo, hi, slo, shi))
    names = {}
    for line in open(a.names):
        p = line.split()
        if len(p) >= 4 and p[1] != "?" and p[3] == "+0x0":
            names[p[0].upper()] = p[2]
    funcs = {}
    for line in open(a.map):
        p = line.split(None, 1)
        if len(p) == 2:
            funcs[int(p[0], 16)] = p[1].strip()
    by_name = {}
    for ad, n in funcs.items():
        by_name.setdefault(n.split("::")[-1], []).append(ad)
    use = users_in_source(a.source)
    acc, _r13, _r2 = accesses(a.target_dol, funcs)
    rows = list(csv.DictReader(open(a.table, newline="")))
    filled = 0
    report = []
    for r in rows:
        if not (r["wsr_addr"].startswith("UNMAPPED") and r["how"].startswith(("data", "bss"))):
            continue
        p = int(r["wsr_addr"].split("_", 1)[1], 16)
        var = names.get(r["mkw_addr"].upper())
        band = next(((slo, shi) for lo, hi, slo, shi in bands if lo <= p < hi), None)
        if not var or not band:
            report.append("%s %s: no name or no band" % (r["mkw_addr"], var))
            continue
        users = [f for f in sorted(use.get(var, ())) if f in by_name]
        sets = []
        for f in users:
            s = set()
            for ad in by_name[f]:
                s |= {t for t in acc.get(ad, ()) if band[0] <= t - p <= band[1]}
            if s:
                sets.append((f, s))
        common = set.intersection(*[s for _, s in sets]) if sets else set()
        line = "%s %-24s users %s -> %s" % (r["mkw_addr"], var, ",".join(f for f, _ in sets) or "-",
                                            " ".join("%08X" % c for c in sorted(common)) or "none")
        report.append(line)
        wide = band[1] - band[0] > a.min_users_band
        if len(common) == 1 and len(sets) >= (2 if wide else 1):
            c = common.pop()
            r["wsr_addr"] = "0x%08X" % c
            r["how"] += "+users(%d)" % len(sets)
            filled += 1
    # Pass 2: a row next to an exact row (within --near, same section band) takes that row's shift, when the other
    # build's code accesses the resulting address. Rows with an offset from a base follow the base the same way.
    used = set().union(*acc.values()) if acc else set()
    anchors = []
    pal_rows = {r["mkw_symbol"] + "|" + r["mkw_addr"]: r for r in csv.DictReader(open(a.pal_table, newline=""))}
    for r in rows:
        pr = pal_rows.get(r["mkw_symbol"] + "|" + r["mkw_addr"], {})
        if "+users" in r["how"] and pr.get("wsr_addr", "").startswith("0x"):
            p = int(pr["wsr_addr"], 16)
            anchors.append((p, int(r["wsr_addr"], 16) - p))
    anchors.sort()
    near_filled = 0
    for r in rows:
        if not (r["wsr_addr"].startswith("UNMAPPED") and r["how"].startswith(("data", "bss"))):
            continue
        p = int(r["wsr_addr"].split("_", 1)[1], 16)
        band = next(((lo, hi) for lo, hi, _s, _t in bands if lo <= p < hi), None)
        near = [(abs(q - p), s) for q, s in anchors if band and band[0] <= q < band[1] and abs(q - p) <= a.near]
        if not near:
            continue
        s = min(near)[1]
        if p + s in used or "offset+" in r["how"]:
            r["wsr_addr"] = "0x%08X" % (p + s)
            r["how"] += "+near"
            near_filled += 1
            report.append("%s near an exact row: shift %+#x -> %08X" % (r["mkw_addr"], s, p + s))
    print("pass 2 filled %d rows from their exact neighbours" % near_filled)
    with open(a.table, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    a.table.with_name("DATA_BY_USERS.md").write_text("\n".join(report) + "\n")
    print("filled %d rows; report %s" % (filled, a.table.with_name("DATA_BY_USERS.md")))


if __name__ == "__main__":
    main()
