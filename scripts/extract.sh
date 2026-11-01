#!/usr/bin/env bash
# Extract a Wii Sports Resort disc image into work/extracted/ and check its game ID and program
# (supported editions: projects/editions.json).
#   ./scripts/extract.sh <image> [--out <folder>] [--verify]
# <image> can be in any folder. --out puts the extracted game files in another folder (for example another drive;
# default work/extracted); the later steps find it through work/data_root.txt.
# --verify also hashes the image against dtk's built-in Redump database (slow, but confirms a clean dump).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DTK="$ROOT/tools/bin/dtk"
[[ -x "$DTK" ]] || { echo "dtk missing - run ./setup.sh first" >&2; exit 1; }
[[ $# -ge 1 ]] || { echo "usage: $0 <image> [--out <folder>] [--verify]" >&2; exit 2; }

IMAGE="$(realpath "$1")"; shift
OUT="$ROOT/work/extracted"
VERIFY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) mkdir -p "$2"; OUT="$(realpath "$2")"; shift 2 ;;
    --verify) VERIFY=1; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
mkdir -p "$ROOT/work"
if [[ "$OUT" == "$ROOT/work/extracted" ]]; then rm -f "$ROOT/work/data_root.txt"; else echo "$OUT" > "$ROOT/work/data_root.txt"; fi

echo "==> Disc info"
"$DTK" disc info "$IMAGE"

if [[ $VERIFY -eq 1 ]]; then
  echo "==> Verifying against Redump"
  "$DTK" disc verify "$IMAGE"
fi

if [[ -d "$OUT" ]]; then
  echo "==> Removing previous extraction"
  rm -rf "$OUT"
fi
echo "==> Extracting data partition to work/extracted"
"$DTK" disc extract "$IMAGE" "$OUT"

BOOT="$OUT/sys/boot.bin"
[[ -f "$BOOT" ]] || { echo "extraction layout unexpected: $BOOT not found" >&2; exit 1; }
ID="$(head -c 6 "$BOOT")"
echo "==> Game ID: $ID"
python3 "$ROOT/scripts/editions.py" check "$OUT"
PROGRAM="$(python3 "$ROOT/scripts/editions.py" get program "$OUT")"
sha256sum "$OUT/$PROGRAM" | tee "$ROOT/work/main.dol.sha256"
echo "==> REL modules on disc:"
find "$OUT/files" -iname '*.rel' -printf '   %P\n' | sort || true
echo "==> Archives that may contain RELs (check with: tools/bin/dtk vfs ls -r <arc>:)"
find "$OUT/files" -iname '*rel*.arc' -printf '   %P\n' | sort || true
echo "Done. Next: ./scripts/analyze.sh"
