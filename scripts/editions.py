#!/usr/bin/env python3
"""editions.py: the game editions that this project builds (projects/editions.json), found by the disc's game ID.

    python3 scripts/editions.py detect [DATA_ROOT]     the game ID of an extracted disc (default: the data root)
    python3 scripts/editions.py root                   the data root: work/data_root.txt (extract.sh --out), or
                                                       work/extracted
    python3 scripts/editions.py check [DATA_ROOT]      the game ID is known and its program has the right sha256
    python3 scripts/editions.py get FIELD [DATA_ROOT]  a field of that edition (name, project, program, runtime, ...)
    python3 scripts/editions.py runtime [DATA_ROOT]    the runtime folder; makes it first when the edition is ported
    python3 scripts/editions.py list                   every known edition

Each edition gives its project folder (map, address tables, recomp.yml), the path of its program inside the
extracted data partition, the sha256 of that program, and its runtime folder. An edition with "ported_from" gets its
runtime from scripts/port_runtime.py (the PAL runtime with the edition's addresses).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / "projects" / "editions.json"


def data_root():
    chosen = ROOT / "work" / "data_root.txt"
    if chosen.is_file() and chosen.read_text().strip():
        return Path(chosen.read_text().strip())
    return ROOT / "work" / "extracted"


def editions():
    return json.loads(TABLE.read_text())


def detect(root):
    boot = Path(root) / "sys" / "boot.bin"
    if not boot.is_file():
        sys.exit("%s not found - extract your disc with scripts/extract.sh first" % boot)
    return boot.read_bytes()[:6].decode("ascii", "replace")


def edition(root):
    gid = detect(root)
    known = editions()
    if gid not in known:
        sys.exit("game ID %s is not supported; supported: %s" % (
            gid, ", ".join("%s (%s)" % (k, v["name"]) for k, v in known.items())))
    return gid, known[gid]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def check(root):
    gid, e = edition(root)
    program = Path(root) / e["program"]
    if not program.is_file():
        sys.exit("%s: program %s not found" % (gid, program))
    if sha256(program) != e["program_sha256"]:
        sys.exit("%s: %s does not match the supported revision" % (gid, e["program"]))
    return gid, e


def get_runtime_path(root=None):
    """The runtime folder of the edition, relative to the checkout (no port run)."""
    return edition(root or data_root())[1]["runtime"]


def runtime(root):
    _gid, e = edition(root)
    out = ROOT / e["runtime"]
    if "ported_from" in e:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "port_runtime.py"), "--from",
                        str(ROOT / e["ported_from"]), "--to", str(ROOT / e["project"]), "--out", str(out)],
                       check=True, stdout=sys.stderr)
    return out


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    cmd, rest = args[0], args[1:]
    default = data_root()
    if cmd == "root":
        print(default.as_posix())
    elif cmd == "list":
        for gid, e in editions().items():
            print("%s  %s  (%s)" % (gid, e["name"], e["project"]))
    elif cmd == "detect":
        print(detect(rest[0] if rest else default))
    elif cmd == "check":
        gid, e = check(rest[0] if rest else default)
        print("%s %s: program OK" % (gid, e["name"]))
    elif cmd == "get" and rest:
        _gid, e = edition(rest[1] if len(rest) > 1 else default)
        print(e[rest[0]])
    elif cmd == "runtime":
        print(runtime(rest[0] if rest else default))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
