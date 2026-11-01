#!/usr/bin/env python3
"""check_pal_unchanged.py: the PAL edition (RZTP01) builds and plays as upstream, with no PAL disc at hand.

The US edition is a port: its project folder (projects/wsr-sp2e01) is new and its runtime is made by
scripts/port_runtime.py. The PAL files may change only where the US port needs it, and then only by added lines
that the PAL program never reaches:
  - projects/wsr (the PAL project) is unchanged;
  - runtime/wsr changes only in ALLOWED, and only by added lines;
  - the PAL start arguments stay empty (kBootArguments = {nullptr}), so the argument block is never written;
  - the DVD trace runs only when RESORT_DVD_TRACE is set.
The base is the merge base with the upstream branch (default origin/main).

    python3 scripts/check_pal_unchanged.py [--base REF]
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {"runtime/wsr/src/system_bridge.cpp", "runtime/wsr/src/hle/storage/dvd.cpp"}


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main")
    a = ap.parse_args(argv)
    base = git("merge-base", "HEAD", a.base).strip()
    faults = []
    for line in git("diff", "--numstat", base, "HEAD", "--", "projects/wsr", "runtime/wsr").splitlines():
        added, removed, path = line.split("\t", 2)
        if path.startswith("projects/wsr/"):
            faults.append("%s: the PAL project changed" % path)
        elif path not in ALLOWED:
            faults.append("%s: a PAL runtime file outside the allowed list changed" % path)
        elif removed not in ("0", "-"):
            faults.append("%s: %s line(s) of the PAL runtime removed or changed" % (path, removed))
    bridge = (ROOT / "runtime/wsr/src/system_bridge.cpp").read_text(encoding="utf-8")
    if not re.search(r"kBootArguments\[\]\s*=\s*\{\s*nullptr\s*\}", bridge):
        faults.append("runtime/wsr/src/system_bridge.cpp: the PAL start arguments are not empty")
    dvd = (ROOT / "runtime/wsr/src/hle/storage/dvd.cpp").read_text(encoding="utf-8")
    if "RESORT_DVD_TRACE" in dvd and 'std::getenv("RESORT_DVD_TRACE")' not in dvd:
        faults.append("runtime/wsr/src/hle/storage/dvd.cpp: the DVD trace does not wait for RESORT_DVD_TRACE")
    for f in faults:
        print("FAULT", f)
    print("check_pal_unchanged: base %s, %d fault(s)" % (base[:9], len(faults)))
    return 1 if faults else 0


if __name__ == "__main__":
    sys.exit(main())
