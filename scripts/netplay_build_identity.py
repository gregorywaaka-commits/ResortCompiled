#!/usr/bin/env python3
"""Identify shared simulation sources independently of ELF/PE binaries and paths."""
import argparse
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import editions  # noqa: E402

def identity():
    digest = hashlib.sha256(b'Riisorted simulation v2; PPC FP no-fast-math,ffp-contract=off; x86_64; input wire v1\0')
    # The runtime of the extracted edition: each edition (game ID) gets its own identity, so players of 2
    # editions never join one session. Line ends and workspace paths are made equal, so a Windows checkout
    # (CRLF) and a Linux checkout (LF) of the same sources give the same identity.
    trees = [('runtime', ROOT / editions.get_runtime_path()),
             ('aurora', ROOT / 'external/wiicompiled/aurora-main'),
             ('runtime-third-party', ROOT / 'external/wiicompiled/runtime/third_party'),
             ('translated', ROOT / 'work/generated')]
    for label, folder in trees:
        if not folder.is_dir(): raise ValueError(f'Missing build input: {label}')
        for p in sorted(folder.rglob('*')):
            rel = p.relative_to(folder)
            if any(part in ('.git', '__pycache__', 'build', 'target') for part in rel.parts): continue
            if not p.is_file() or p.suffix not in ('.cpp', '.c', '.h', '.hpp', '.inl', '.S', '.bin', '.cmake', '.txt'): continue
            # Normalize workspace paths emitted by the translator. Object files,
            # caches and platform dependency binaries do not enter this identity.
            data = p.read_bytes().replace(b'\r\n', b'\n')
            for spelling in (str(ROOT), ROOT.as_posix(), str(ROOT).replace('\\', '\\\\')):
                data = data.replace(spelling.encode(), b'<workspace>')
            digest.update(f'{label}/{rel.as_posix()}\0'.encode())
            digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = identity()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.is_file() or args.output.read_text().strip() != value:
        args.output.write_text(value + '\n')
    print(value)
