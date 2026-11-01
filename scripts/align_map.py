#!/usr/bin/env python3
"""align_map.py: carry the PAL (RZTP01) project files over to another build of Wii Sports Resort.

The PAL map and the other build come from the same source code, compiled in the same order, so their functions sit
in the same order with mostly the same sizes; a change in the code shifts every later function. This script lines up
the 2 function lists by their sizes (like a diff of 2 texts), then moves each PAL address that lands inside a lined-up
function to the same offset in the other build.

Inputs:
  --pal-map     projects/wsr/MAP.txt            (address and name of each PAL function, in order)
  --symbols     symbols.txt of `dtk dol split`  (each function of the other build, with its size)
  --project     projects/wsr                    (the PAL project files to carry over)
Output, in --out (for example projects/wsr-sp2e01):
  MAP.txt, hle_address_map.csv, address_map.csv, names.txt   the same files with the other build's addresses
  ALIGN_REPORT.md                                            how much lined up, and each address that did not

    python3 scripts/align_map.py --symbols <symbols.txt> --out projects/wsr-sp2e01
"""
import argparse
import csv
import difflib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYM = re.compile(r"^(\S+) = \.(\w+):0x([0-9A-Fa-f]+); // type:function size:0x([0-9A-Fa-f]+)")


def pal_functions(path):
    """[(address, name, size)] of the PAL map, sorted; a size is the gap to the next function."""
    rows = sorted((int(a, 16), n) for a, n in (l.split(None, 1) for l in path.read_text().splitlines() if l.strip()))
    out = []
    for i, (a, n) in enumerate(rows):
        nxt = rows[i + 1][0] if i + 1 < len(rows) else a + 4
        out.append((a, n.strip(), nxt - a))
    return out


def other_functions(path):
    """[(address, name, size)] of the dtk symbols of the other build (text sections only), sorted."""
    out = []
    for line in path.read_text().splitlines():
        m = SYM.match(line)
        if m and m.group(2) in ("init", "text"):
            out.append((int(m.group(3), 16), m.group(1), int(m.group(4), 16)))
    out.sort()
    # Like the PAL map, a size is the gap to the next function (padding counts on both sides).
    return [(a, n, (out[i + 1][0] - a) if i + 1 < len(out) else s) for i, (a, n, s) in enumerate(out)]


def line_up(pal, oth):
    """{PAL function start: other function start} for each pair of functions that line up."""
    sm = difflib.SequenceMatcher(None, [s for _, _, s in pal], [s for _, _, s in oth], autojunk=False)
    pairs = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                pairs[pal[i1 + k][0]] = oth[j1 + k][0]
        elif tag == "replace" and i2 - i1 == j2 - j1:
            # The same number of functions between 2 lined-up runs: a changed function keeps its place.
            for k in range(i2 - i1):
                pairs[pal[i1 + k][0]] = oth[j1 + k][0]
    return pairs


def gap_starts(pal, oth, pairs):
    """{other-build address: PAL function start} for each PAL function start that lies between 2 lined-up functions
    whose gap has the same length in both builds, where the other build's symbols have no function. A 4-byte stub
    (a lone blr that a table points at) is often merged into the function before it by dtk."""
    import bisect
    starts = [a for a, _, _ in pal]
    have = {a for a, _, _ in oth}
    lined = sorted(pairs)
    out = {}
    for p1, p2 in zip(lined, lined[1:]):
        u1, u2 = pairs[p1], pairs[p2]
        if p2 - p1 != u2 - u1:
            continue
        j = bisect.bisect_right(starts, p1)
        while j < len(starts) and starts[j] < p2:
            u = u1 + (starts[j] - p1)
            if u not in have:
                out[u] = starts[j]
            j += 1
    return out


def mover(pal, pairs):
    """A function that moves 1 PAL address: to the same offset inside the lined-up function, or None."""
    starts = [a for a, _, _ in pal]
    sizes = {a: s for a, _, s in pal}
    import bisect

    def move(addr):
        i = bisect.bisect_right(starts, addr) - 1
        if i < 0:
            return None
        f = starts[i]
        if f not in pairs or addr - f >= sizes[f]:
            return None
        return pairs[f] + (addr - f)
    return move


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pal-map", type=Path, default=ROOT / "projects" / "wsr" / "MAP.txt")
    ap.add_argument("--project", type=Path, default=ROOT / "projects" / "wsr")
    ap.add_argument("--symbols", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--map-only", action="store_true",
                    help="write only MAP.txt (keeps the hand-mapped tables of --out); names of the old MAP.txt stay")
    a = ap.parse_args()
    pal, oth = pal_functions(a.pal_map), other_functions(a.symbols)
    pairs = line_up(pal, oth)
    move = mover(pal, pairs)
    a.out.mkdir(parents=True, exist_ok=True)
    missed = {}

    # MAP.txt: every function of the other build, plus the PAL starts inside equal gaps (gap_starts); a lined-up
    # function takes its PAL name. With --map-only, a name of the old MAP.txt stays where PAL gives none.
    back = {o: p for p, o in pairs.items()}
    gaps = gap_starts(pal, oth, pairs)
    back.update(gaps)
    names = {ad: n for ad, n, _ in pal}
    old = {}
    if a.map_only and (a.out / "MAP.txt").exists():
        for line in (a.out / "MAP.txt").read_text().splitlines():
            p = line.split(None, 1)
            if len(p) == 2 and not p[1].startswith("0x"):
                old[int(p[0], 16)] = p[1].strip()
    with open(a.out / "MAP.txt", "w") as fh:
        for ad in sorted({ad for ad, _n, _s in oth} | set(gaps)):
            pn = names.get(back.get(ad)) or old.get(ad)
            fh.write("%08x %s\n" % (ad, pn if pn and not pn.startswith("0x") else "0x%08x" % ad))
    if a.map_only:
        print("MAP.txt: %d functions, %d from equal gaps" % (len(oth) + len(gaps), len(gaps)))
        return

    def fix_csv(name, cols):
        src = a.project / name
        if not src.exists():
            return 0, 0
        rows = list(csv.DictReader(open(src, newline="")))
        done = 0
        for r in rows:
            for c in cols:
                if r.get(c, "").startswith("0x"):
                    new = move(int(r[c], 16))
                    if new is None:
                        missed.setdefault(name, []).append("%s %s" % (r[c], r.get("symbol") or r.get("mkw_symbol") or ""))
                        r[c] = "UNMAPPED_" + r[c]
                    else:
                        r[c] = "0x%08X" % new
                        done += 1
        with open(a.out / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else cols)
            w.writeheader()
            w.writerows(rows)
        return done, len(rows)

    hooks = fix_csv("hle_address_map.csv", ["wsr_addr"])
    amap = fix_csv("address_map.csv", ["wsr_addr"])

    # names.txt: hand-identified functions, "<hex address> <name>" after the comment lines.
    nm_done = nm_all = 0
    src = a.project / "names.txt"
    if src.exists():
        lines = []
        for l in src.read_text().splitlines():
            m = re.match(r"^(0x)?([0-9A-Fa-f]{8})\s+(\S.*)$", l)
            if not m:
                lines.append(l)
                continue
            nm_all += 1
            new = move(int(m.group(2), 16))
            if new is None:
                missed.setdefault("names.txt", []).append(l)
                lines.append("# UNMAPPED " + l)
            else:
                nm_done += 1
                lines.append("0x%08X %s" % (new, m.group(3)))
        (a.out / "names.txt").write_text("\n".join(lines) + "\n")

    named = sum(1 for ad, n, _ in pal if not n.startswith("0x"))
    named_moved = sum(1 for ad, n, _ in pal if not n.startswith("0x") and ad in pairs)
    rep = ["# Alignment report", "",
           "PAL functions %d; other build functions %d; lined up %d (%.1f %%)." % (
               len(pal), len(oth), len(pairs), 100 * len(pairs) / max(1, len(pal))),
           "Named PAL functions carried over: %d of %d." % (named_moved, named),
           "Hooks (hle_address_map.csv) moved: %d of %d." % hooks,
           "Address map (address_map.csv) entries moved: %d of %d." % amap,
           "Hand names (names.txt) moved: %d of %d." % (nm_done, nm_all), ""]
    for f, items in missed.items():
        rep += ["## Not moved: %s (%d)" % (f, len(items)), ""] + ["- %s" % i for i in items] + [""]
    (a.out / "ALIGN_REPORT.md").write_text("\n".join(rep) + "\n")
    print("\n".join(rep[:8]))


if __name__ == "__main__":
    main()
