#!/usr/bin/env python3
"""check_no_game_data.py: refuse a commit or a push that holds data from a game disc.

Checks every file that git tracks (or the files named on the command line):
  - the magic of a Wii or GameCube file: Yaz0, U8 archives, RARC, BRRES, BRSAR, RSTM, TPL, BMG, THP, WBFS, RVZ, WIA,
    CISO, a DOL header, a REL header, an ISO with a Wii or GameCube disc magic;
  - a binary file (a NUL byte in the first 8 KiB) that is not on the allow list below (the project's own images);
  - a text file larger than 16 MiB.
Exit 0 when nothing is found; exit 1 and a list of the files when something is.

    python3 scripts/check_no_game_data.py            # every tracked file
    python3 scripts/check_no_game_data.py FILE ...   # only these files
"""
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED_BINARY = {".png", ".ico", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ttf", ".otf", ".woff", ".woff2"}
MAX_TEXT = 16 << 20
MAGICS = [
    (b"Yaz0", "Yaz0 compressed file"), (b"Yaz1", "Yaz1 compressed file"), (b"\x55\xaa\x38\x2d", "U8 archive"),
    (b"RARC", "RARC archive"), (b"bres", "BRRES model"), (b"RSAR", "BRSAR sound archive"), (b"RSTM", "RSTM stream"),
    (b"RWSD", "RWSD sound"), (b"MESGbmg1", "BMG messages"), (b"\x00\x20\xaf\x30", "TPL texture"),
    (b"THP\x00", "THP video"), (b"WBFS", "WBFS image"), (b"RVZ\x01", "RVZ image"), (b"WIA\x01", "WIA image"),
    (b"CISO", "CISO image"),
]
WII_DISC_MAGIC = (0x18, b"\x5d\x1c\x9e\xa3")
GC_DISC_MAGIC = (0x1C, b"\xc2\x33\x9f\x3d")


def tracked_files():
    out = subprocess.run(["git", "-c", "core.fsmonitor=false", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                         check=True).stdout
    return [ROOT / p for p in out.decode("utf-8", "replace").split("\0") if p]


def looks_like_dol(head):
    """A DOL header: 18 section offsets, 18 addresses in 0x80000000-0x81800000 or 0, the entry point at 0xE0."""
    if len(head) < 0x100:
        return False
    addrs = struct.unpack(">18I", head[0x48:0x90])
    entry = struct.unpack(">I", head[0xE0:0xE4])[0]
    used = [a for a in addrs if a]
    return bool(used) and all(0x80000000 <= a < 0x81800000 for a in used) and 0x80000000 <= entry < 0x81800000


def problem(path):
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            head = fh.read(8192)
    except OSError:
        return None
    for magic, what in MAGICS:
        if head.startswith(magic):
            return what
    for offset, magic in (WII_DISC_MAGIC, GC_DISC_MAGIC):
        if head[offset:offset + 4] == magic:
            return "a disc image"
    if path.suffix.lower() in (".dol", ".rel", ".iso", ".gcm", ".elf") or looks_like_dol(head):
        return "a game program"
    binary = b"\0" in head
    if binary and path.suffix.lower() not in ALLOWED_BINARY:
        return "a binary file"
    if not binary and size > MAX_TEXT:
        return "a text file over 16 MiB"
    return None


def main():
    files = [Path(p).resolve() for p in sys.argv[1:]] or tracked_files()
    found = [(p, why) for p in files if p.is_file() for why in [problem(p)] if why]
    for p, why in found:
        print("REFUSED %s: %s" % (p.relative_to(ROOT) if p.is_relative_to(ROOT) else p, why))
    print("check_no_game_data: %d file(s) checked, %d refused" % (len(files), len(found)))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
