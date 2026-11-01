#!/usr/bin/env python3
"""bridge_data.py: fill the data and bss addresses of another build's address_map.csv (after align_map.py).

align_map.py moves code addresses, but data does not sit inside functions. The PAL project found its data addresses
by votes against Mario Kart Wii (PAL). For another build, this script:
  1. pairs the functions of a Mario Kart Wii of any region (--ref-dol, with its own map --ref-map, for example made
     by align_map.py from WiiCompiled's PAL map) with the other Resort build (xmatch.run),
  2. collects the data votes of those pairs (xmatch.map_data): ref data address -> other-build data address,
  3. finds, for each data area, the 1 shift that carries the PAL Mario Kart Wii data addresses of the PAL table onto
     the ref data addresses (the most hits wins; a shift needs 2 or more hits),
  4. fills each UNMAPPED data or bss row of --table with the voted address, and checks that the shift from the PAL
     Resort address to the new one is one of the shifts that the other rows show.

    python3 scripts/bridge_data.py --ref-dol <mkw main.dol> --ref-map <its MAP.txt> \
        --target-dol <other main.dol> --target-symbols <dtk symbols.txt> --table projects/wsr-sp2e01/address_map.csv
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import analyze  # noqa: E402
import xmatch  # noqa: E402

WINDOW = 0x40000      # the largest shift between 2 regional builds that the fit tries
AREA = 0x8000         # PAL data addresses closer than this share 1 shift (they sit in the same part of a section)


def fit_shifts(pal_addrs, keys):
    """{PAL address: shift} for each PAL address whose area has a shift with 2 or more hits."""
    import bisect
    keys = sorted(keys)
    areas = {}
    for a in sorted(pal_addrs):
        areas.setdefault(a // AREA, []).append(a)
    out = {}
    for _area, addrs in areas.items():
        votes = Counter()
        for a in addrs:
            lo, hi = bisect.bisect_left(keys, a - WINDOW), bisect.bisect_right(keys, a + WINDOW)
            for k in keys[lo:hi]:
                votes[k - a] += 1
        if votes:
            shift, hits = votes.most_common(1)[0]
            if hits >= 2 or len(addrs) == 1 and hits == 1:
                for a in addrs:
                    out[a] = shift
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref-dol", type=Path, required=True)
    ap.add_argument("--ref-map", type=Path, required=True)
    ap.add_argument("--target-dol", type=Path, required=True)
    ap.add_argument("--target-symbols", type=Path, required=True)
    ap.add_argument("--pal-table", type=Path, default=ROOT / "projects" / "wsr" / "address_map.csv")
    ap.add_argument("--table", type=Path, required=True)
    a = ap.parse_args()

    rd, td = xmatch.Dol(a.ref_dol), xmatch.Dol(a.target_dol)
    ref_sda = analyze.find_sda_bases(analyze.Dol.load(a.ref_dol))[:2]
    tgt_sda = analyze.find_sda_bases(analyze.Dol.load(a.target_dol))[:2]
    pairs, ref, tgt, _score = xmatch.run(a.ref_dol, a.ref_map, a.target_dol, a.target_symbols)
    dmap = xmatch.map_data(rd, td, pairs, ref, tgt, ref_sda, tgt_sda)
    good = {k: v[0] for k, v in dmap.items() if not v[2]}
    print("%d function pairs, %d data votes" % (len(pairs), len(good)))

    pal = {r["mkw_symbol"] + "|" + r["mkw_addr"]: r for r in csv.DictReader(open(a.pal_table, newline=""))}
    rows = list(csv.DictReader(open(a.table, newline="")))
    want = [r for r in rows if r["wsr_addr"].startswith("UNMAPPED") and r["how"].startswith(("data", "bss"))]
    shifts = fit_shifts([int(r["mkw_addr"], 16) for r in want], good.keys())

    # The shifts PAL -> other build that the rows moved already show, by section (to check each new row).
    seen = Counter()
    for r in rows:
        p = pal.get(r["mkw_symbol"] + "|" + r["mkw_addr"])
        if p and r["wsr_addr"].startswith("0x") and p["wsr_addr"].startswith("0x")                 and r["how"].startswith(("data", "bss")):
            seen[int(r["wsr_addr"], 16) - int(p["wsr_addr"], 16)] += 1

    filled, deltas = 0, Counter()
    for r in want:
        m = int(r["mkw_addr"], 16)
        k = m + shifts[m] if m in shifts else None
        if k in good:
            pal_wsr = int(r["wsr_addr"].split("_", 1)[1], 16)
            r["wsr_addr"] = "0x%08X" % good[k]
            r["how"] = r["how"] + "+bridge"
            deltas[good[k] - pal_wsr] += 1
            filled += 1
    with open(a.table, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("filled %d of %d data and bss rows" % (filled, len(want)))
    print("PAL -> new shifts of the filled rows (each should repeat; a lone shift is suspect):")
    for d, n in deltas.most_common():
        print("  %+#08x  %d" % (d, n))


if __name__ == "__main__":
    main()
