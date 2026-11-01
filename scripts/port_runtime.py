#!/usr/bin/env python3
"""port_runtime.py: make the runtime of another edition from the PAL runtime (runtime/wsr).

The PAL runtime holds PAL addresses: hook addresses, guest data addresses, r13/r2 offsets, and function names with an
address suffix. This script copies runtime/wsr to --out and changes each PAL address to the address of the other
edition. The address of each PAL address comes from the edition's runtime_addresses.csv ("pal,other,how").

Make that table once, from the 2 projects (needs the other edition's dtk symbols.txt):

    python3 scripts/port_runtime.py --to projects/wsr-sp2e01 --make-table --symbols work/dtk/symbols.txt

The table takes, in order:
  1. a line of <project>/port_overrides.txt ("<PAL hex> <other hex|KEEP>  # reason"),
  2. a row of the address tables (address_map.csv and hle_address_map.csv of both projects, joined on the MKW key),
  3. low memory (below 0x80004000): the same address,
  4. a code address: the same offset inside the lined-up function (align_map.py),
  5. a data address between 2 table rows with the same shift: that shift.
Every other address goes to the table as UNRESOLVED. A hook registration at an UNRESOLVED address is disabled in an
"#if 0 // RESORT-UNMAPPED" block, as rekey.py does. Lines inside such blocks stay as they are.

A code difference that no address holds (for example a struct field at another offset) goes in
<project>/port_edits.json, applied after the address change.

Then make the runtime (no disc data needed, only the table):

    python3 scripts/port_runtime.py --to projects/wsr-sp2e01 --out work/runtime/wsr-sp2e01
"""
import argparse
import bisect
import csv
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import align_map  # noqa: E402

ADDR_RE = re.compile(r"(?<![0-9A-Fa-fxX])(0x|0X)?(8[01][0-9A-Fa-f]{6})(?![0-9A-Fa-f])")
REG_EXPR = re.compile(r"(\br13\b|gpr\[13\]|\br2\b|gpr\[2\])(\s*)([-+])(\s*)(\(?)(0x[0-9A-Fa-f]+|\d+)(u?)")
NAMED_USE = re.compile(r"(\br13\b|gpr\[13\]|\br2\b|gpr\[2\])\s*([-+])\s*(k[A-Za-z0-9_]+)")
NAMED_DEF = r"(\b{name}\s*=\s*)(0x[0-9A-Fa-f]+|\d+)(u?)"
REG_LINE_RE = re.compile(r"^\s*[A-Z][A-Z0-9_]{5,}\(\s*(?:0x)?8[01][0-9A-Fa-f]{6}\b")
UNMAPPED_MACRO_RENAMES = (
    ("PPC_NATIVE_OVERRIDE", "RESORT_UNMAPPED_OVERRIDE"),
    ("REGISTER_NATIVE_FUNCTION", "RESORT_UNMAPPED_REGISTRATION"),
    ("REGISTER_TRANSLATED_FUNCTION", "RESORT_UNMAPPED_TRANSLATED"),
    ("GX_FATAL_STUB", "RESORT_UNMAPPED_GX_STUB"),
)
TEXT_EXT = {".cpp", ".h", ".hpp", ".inc", ".c", ".cc"}
LOW_MEMORY_END = 0x80004000
MAX_DATA_GAP = 0x2000
BLOCK_START = "#if 0 // RESORT-UNMAPPED"
BLOCK_END = "#endif // RESORT-UNMAPPED"


def sda_bases(project):
    """(r13, r2) from <project>/recomp.yml."""
    text = (project / "recomp.yml").read_text()
    r13 = re.search(r"^\s*sda_base:\s*(0x[0-9A-Fa-f]+)", text, re.M)
    r2 = re.search(r"^\s*sda2_base:\s*(0x[0-9A-Fa-f]+)", text, re.M)
    if not (r13 and r2):
        sys.exit("%s/recomp.yml has no sda_base or sda2_base" % project)
    return int(r13.group(1), 16), int(r2.group(1), 16)


def runtime_files(root):
    return [f for f in sorted(list((root / "src").rglob("*")) + list((root / "include").rglob("*")))
            if f.is_file() and f.suffix in TEXT_EXT]


def is_comment(line):
    return line.lstrip().startswith(("//", "*", "/*"))


def active_lines(text):
    """(index, line) of each line outside the disabled RESORT-UNMAPPED blocks."""
    inactive = False
    for n, line in enumerate(text.splitlines(keepends=True)):
        if line.startswith(BLOCK_START):
            inactive = True
        if inactive:
            inactive = not line.startswith(BLOCK_END)
            continue
        yield n, line


def named_offsets(files):
    """{constant name: (is r13, sign)} of each named constant that the runtime adds to or subtracts from r13 or r2."""
    named = {}
    for f in files:
        for m in NAMED_USE.finditer(f.read_text(errors="replace")):
            named[m.group(3)] = ("13" in m.group(1), m.group(2))
    return named


def reg_offset(m):
    return int(m.group(6), 0) * (1 if m.group(3) == "+" else -1)


def used_addresses(root, pal_sda):
    """Every PAL guest address that the active runtime code spells: literal, r13/r2 relative, or a named offset."""
    files = runtime_files(root)
    named = named_offsets(files)
    found = set()
    for f in files:
        for _n, line in active_lines(f.read_text(errors="replace")):
            for m in ADDR_RE.finditer(line):
                found.add(int(m.group(2), 16))
            if is_comment(line):
                continue
            for m in REG_EXPR.finditer(line):
                if abs(reg_offset(m)) <= 0x10000:
                    found.add((pal_sda[0 if "13" in m.group(1) else 1] + reg_offset(m)) & 0xFFFFFFFF)
            for name, (is13, sign) in named.items():
                for m in re.finditer(NAMED_DEF.format(name=re.escape(name)), line):
                    off = int(m.group(2), 0) * (1 if sign == "+" else -1)
                    found.add((pal_sda[0 if is13 else 1] + off) & 0xFFFFFFFF)
    return found


def make_table(a, pal_sda):
    overrides = {}
    path = a.to / "port_overrides.txt"
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split("#", 1)[0].split()
            if len(parts) >= 2:
                overrides[int(parts[0], 16)] = parts[1]
    table = {}
    for name, key in (("address_map.csv", "mkw_symbol"), ("hle_address_map.csv", "symbol")):
        pal = {r["mkw_addr"] + "|" + r[key]: r for r in csv.DictReader(open(a.frm / name, newline=""))}
        for r in csv.DictReader(open(a.to / name, newline="")):
            p = pal.get(r["mkw_addr"] + "|" + r[key])
            if p and p["wsr_addr"].startswith("0x"):
                if r["wsr_addr"].startswith("0x"):
                    table[int(p["wsr_addr"], 16)] = int(r["wsr_addr"], 16)
                elif r["wsr_addr"] == "ABSENT":
                    table[int(p["wsr_addr"], 16)] = None
    pal_funcs = align_map.pal_functions(a.frm / "MAP.txt")
    move = align_map.mover(pal_funcs, align_map.line_up(pal_funcs, align_map.other_functions(a.symbols)))
    text_end = pal_funcs[-1][0] + pal_funcs[-1][2]
    data_rows = sorted((p, o - p) for p, o in table.items() if p >= text_end and o is not None)
    data_keys = [p for p, _ in data_rows]

    def resolve(addr):
        if addr in overrides:
            return (addr if overrides[addr] == "KEEP" else int(overrides[addr], 16)), "override"
        if addr in table:
            return (table[addr], "table") if table[addr] is not None else (None, "absent in this edition")
        if addr < LOW_MEMORY_END:
            return addr, "low memory"
        if addr < text_end:
            new = move(addr)
            return (new, "code") if new is not None else (None, "code: no lined-up function")
        i = bisect.bisect_right(data_keys, addr)
        if 0 < i < len(data_keys):
            (lo, slo), (hi, shi) = data_rows[i - 1], data_rows[i]
            if slo == shi and hi - lo <= MAX_DATA_GAP:
                return addr + slo, "data between %08X and %08X" % (lo, hi)
            return None, "data: shift %+#x below, %+#x above" % (slo, shi)
        return None, "outside the program"

    rows = [(addr,) + resolve(addr) for addr in sorted(used_addresses(a.runtime, pal_sda))]
    with open(a.to / "runtime_addresses.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["pal", "other", "how"])
        for addr, new, how in rows:
            w.writerow(["0x%08X" % addr, "0x%08X" % new if new is not None else "UNRESOLVED", how])
    bad = [(addr, how) for addr, new, how in rows if new is None]
    print("%d addresses; %d unresolved -> %s" % (len(rows), len(bad), a.to / "runtime_addresses.csv"))
    for addr, how in bad:
        print("  %08X %s" % (addr, how))


def apply_edits(path, out):
    """Apply <project>/port_edits.json: [{"file", "old", "new", "why"}], each "old" found exactly once after the
    address change. An edit holds a code difference of the edition that no address holds (a changed struct field)."""
    if not path.exists():
        return 0
    edits = json.loads(path.read_text())
    for e in edits:
        f = out / e["file"]
        with open(f, encoding="utf-8", newline="") as fh:
            text = fh.read()
        eol = "\r\n" if "\r\n" in text else "\n"
        old, new = e["old"].replace("\n", eol), e["new"].replace("\n", eol)
        if text.count(old) != 1:
            sys.exit("%s: edit '%s' finds its text %d times in %s" % (path, e["why"], text.count(old), f))
        f.write_text(text.replace(old, new), encoding="utf-8", newline="")
    return len(edits)


def sync_tree(src, dst):
    """Makes dst equal to src. Writes only the files whose bytes differ and removes the files that src does not
    have, so an unchanged file keeps its time. Returns the number of files written."""
    written = 0
    want = {p.relative_to(src) for p in src.rglob("*") if p.is_file()}
    for rel in sorted(want):
        new = (src / rel).read_bytes()
        target = dst / rel
        if not target.is_file() or target.read_bytes() != new:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(new)
            written += 1
    if dst.exists():
        for p in sorted(dst.rglob("*"), reverse=True):
            if p.is_file() and p.relative_to(dst) not in want:
                p.unlink()
            elif p.is_dir() and not any(p.iterdir()):
                p.rmdir()
    return written


def port(a, pal_sda, oth_sda):
    table = {}
    for r in csv.DictReader(open(a.to / "runtime_addresses.csv", newline="")):
        table[int(r["pal"], 16)] = int(r["other"], 16) if r["other"].startswith("0x") else None
    # The port is made in a staging folder; sync_tree then copies only the changed files to --out, so a build sees
    # new times only on the files whose text changed.
    out = a.out.with_name(a.out.name + ".staging")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for sub in ("src", "include", "cmake", "tests"):
        if (out / sub).exists():
            shutil.rmtree(out / sub)
        if (a.runtime / sub).exists():
            shutil.copytree(a.runtime / sub, out / sub)
    for name in ("CMakeLists.txt", "README.md"):
        if (a.runtime / name).exists():
            shutil.copyfile(a.runtime / name, out / name)
    files = runtime_files(out)
    named = named_offsets(files)
    unresolved, disabled, changed = [], [], 0

    def new_offset(is13, off):
        new = table.get((pal_sda[0 if is13 else 1] + off) & 0xFFFFFFFF)
        return None if new is None else new - oth_sda[0 if is13 else 1]

    for f in files:
        text = f.read_bytes().decode("utf-8", errors="surrogateescape")
        lines = text.splitlines(keepends=True)
        rel = f.relative_to(out)
        disable_at = []
        for n, line in active_lines(text):
            orig, comment, missing = line, is_comment(line), []

            def sub_reg(m):
                if abs(reg_offset(m)) > 0x10000:
                    return m.group(0)
                new = new_offset("13" in m.group(1), reg_offset(m))
                if new is None:
                    missing.append(m.group(0))
                    return m.group(0)
                val = ("0x%x" % abs(new)) if m.group(6).startswith("0x") else str(abs(new))
                return m.group(1) + m.group(2) + ("+" if new >= 0 else "-") + m.group(4) + m.group(5) + val + m.group(7)

            def sub_named(m, is13, sign):
                off = int(m.group(2), 0) * (1 if sign == "+" else -1)
                new = new_offset(is13, off)
                if new is None or (new >= 0) != (off >= 0):
                    missing.append(m.group(0))
                    return m.group(0)
                val = ("0x%X" % abs(new)) if m.group(2).startswith("0x") else str(abs(new))
                return m.group(1) + val + m.group(3)

            def sub_addr(m):
                new = table.get(int(m.group(2), 16))
                if new is None:
                    missing.append(m.group(2))
                    return m.group(0)
                # A spelling with letters keeps its case. A spelling of digits only becomes upper case, as the
                # translator's names (func_801FF8EC): so 1 spelling gives 1 result in every file, and a name that a
                # macro pastes from an address stays the same name at its definition and at each use.
                lower = m.group(2) != m.group(2).upper()
                return (m.group(1) or "") + ("%08x" % new if lower else "%08X" % new)

            if not comment:
                line = REG_EXPR.sub(sub_reg, line)
                for name, (is13, sign) in named.items():
                    line = re.sub(NAMED_DEF.format(name=re.escape(name)),
                                  lambda m, is13=is13, sign=sign: sub_named(m, is13, sign), line)
            line = ADDR_RE.sub(sub_addr, line)
            if missing and not comment:
                unresolved.append("%s:%d %s" % (rel, n + 1, " ".join(missing)))
                if REG_LINE_RE.match(orig):
                    line = orig
                    disable_at.append(n)
                    disabled.append("%s:%d: %s" % (rel, n + 1, orig.strip()[:140]))
            if line != orig:
                changed += 1
                lines[n] = line
        for start in sorted(disable_at, reverse=True):
            depth, end = 0, start
            for k in range(start, len(lines)):
                depth += lines[k].count("(") - lines[k].count(")")
                end = k
                if depth <= 0:
                    break
            for k in range(start, end + 1):
                for old, new in UNMAPPED_MACRO_RENAMES:
                    lines[k] = lines[k].replace(old, new)
            lines.insert(end + 1, BLOCK_END + "\n")
            lines.insert(start, BLOCK_START + ": PAL address with no match in this edition\n")
        new_text = "".join(lines)
        if new_text != text:
            f.write_bytes(new_text.encode("utf-8", errors="surrogateescape"))
    edits = apply_edits(a.to / "port_edits.json", out)
    copied = sync_tree(out, a.out)
    shutil.rmtree(out)
    rep = ["# Port report", "", "Changed lines: %d. Disabled registrations: %d. Lines with an unresolved address: %d."
           % (changed, len(disabled), len(unresolved)), "Code edits of this edition: %d." % edits, "",
           "## Disabled registrations", ""]
    rep += ["- " + d for d in disabled] + ["", "## Unresolved", ""] + ["- " + u for u in unresolved]
    (a.to / "PORT_REPORT.md").write_text("\n".join(rep) + "\n")
    print("changed %d lines; disabled %d registrations; %d lines unresolved; %d files written (report %s)" % (
        changed, len(disabled), len(unresolved), copied, a.to / "PORT_REPORT.md"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="frm", type=Path, default=ROOT / "projects" / "wsr")
    ap.add_argument("--to", type=Path, required=True)
    ap.add_argument("--runtime", type=Path, default=ROOT / "runtime" / "wsr")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--make-table", action="store_true")
    ap.add_argument("--symbols", type=Path, default=ROOT / "work" / "dtk" / "symbols.txt")
    a = ap.parse_args()
    pal_sda, oth_sda = sda_bases(a.frm), sda_bases(a.to)
    if a.make_table:
        make_table(a, pal_sda)
    elif a.out:
        port(a, pal_sda, oth_sda)
    else:
        ap.error("give --make-table or --out")


if __name__ == "__main__":
    main()
