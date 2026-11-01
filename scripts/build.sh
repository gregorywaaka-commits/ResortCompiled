#!/usr/bin/env bash
# Native build of Resortcompiled: WiiCompiled's runtime (re-keyed, runtime/wsr) + the translated game
# (work/generated) + aurora, compiled with clang into one executable.
#
#   bash scripts/build.sh [--jobs N] [--target NAME] [--clean] [--configure-only]
#
# Layout: WiiCompiled's CMake expects <root>/{runtime,generated,aurora-main}. We assemble that in
# work/tree/ (runtime copied with rsync so incremental builds stay incremental; generated and aurora-main
# are symlinks) and build into work/build/. The finished game lands in out/.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WC="$ROOT/external/wiicompiled"
TREE="$ROOT/work/tree"
BUILD="$ROOT/work/build"
OUT="$ROOT/out"

JOBS="$(nproc)"
TARGET="WiiCompiled"
CLEAN=0
CONFIGURE_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --jobs|-j) JOBS="$2"; shift 2 ;;
    --target) TARGET="$2"; shift 2 ;;
    --clean) CLEAN=1; shift ;;
    --configure-only) CONFIGURE_ONLY=1; shift ;;
    -h|--help) sed -n 2,10p "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

die() { echo "[error] $*" >&2; exit 1; }
# Linux, or Windows in an MSYS2 CLANG64 shell (docs/Editions-and-platforms.md).
WINDOWS_HOST=0
if [[ "$(uname -o 2>/dev/null)" == "Msys" ]]; then
  WINDOWS_HOST=1
  # CMake takes CMAKE_SYSTEM_PROCESSOR from this variable; an MSYS2 login shell can drop it.
  export PROCESSOR_ARCHITECTURE="${PROCESSOR_ARCHITECTURE:-AMD64}"
fi
HOST_CMAKE=()
# The MSYS2 MinGW headers announce the Windows 11 SDK level, and abseil then takes a WinRT time zone path that
# these headers do not declare. The Windows 10 21H2 level keeps abseil on its portable time zone code.
[[ $WINDOWS_HOST -eq 1 ]] && HOST_CMAKE+=(-DCMAKE_C_FLAGS=-DNTDDI_VERSION=0x0A00000B -DCMAKE_CXX_FLAGS=-DNTDDI_VERSION=0x0A00000B)
# C++/WinRT headers (the media-session volume code): the UCRT64 package of MSYS2. Only its winrt/ folder is copied,
# so the 2 MinGW header trees do not mix.
if [[ $WINDOWS_HOST -eq 1 ]]; then
  [[ -f /ucrt64/include/winrt/base.h ]] || die "C++/WinRT missing - run: pacman -S mingw-w64-ucrt-x86_64-cppwinrt"
  mkdir -p "$ROOT/work/windows/cppwinrt"
  rsync -a --delete /ucrt64/include/winrt/ "$ROOT/work/windows/cppwinrt/winrt/"
  HOST_CMAKE+=(-DMKW_CPPWINRT_INCLUDE_DIR="$(cygpath -m "$ROOT/work/windows/cppwinrt")")
fi
link_dir() {  # link_dir <target> <link>: a symlink, or on Windows a junction (no admin rights needed)
  if [[ $WINDOWS_HOST -eq 1 ]]; then
    # rmdir removes only the junction, never the folder it points to.
    if [[ -L "$2" ]]; then MSYS2_ARG_CONV_EXCL="*" cmd.exe /c rmdir "$(cygpath -w "$2")"; elif [[ -e "$2" ]]; then rm -rf "$2"; fi
    MSYS2_ARG_CONV_EXCL="*" cmd.exe /c mklink /J "$(cygpath -w "$2")" "$(cygpath -w "$1")" >/dev/null
  else
    ln -sfn "$1" "$2"
  fi
}
RUNTIME="$ROOT/$(python3 "$ROOT/scripts/editions.py" get runtime)"
[[ -f "$RUNTIME/CMakeLists.txt" ]] || die "${RUNTIME#$ROOT/} missing - run: python3 scripts/configure_project.py"
[[ -f "$ROOT/work/generated/build_shards/shards.cmake" ]] || die "no translated code - run: bash scripts/translate.sh"
[[ -d "$WC/aurora-main" ]] || die "WiiCompiled checkout missing - run: bash setup.sh"
for t in clang clang++ cmake ninja rsync; do command -v "$t" >/dev/null || die "$t not found (run setup.sh)"; done

# The translated code is ~500 MB of C++; each clang job can take 1-2 GB of RAM on the big shards.
MEM_GB=$(awk '/MemTotal/{printf "%d", $2/1048576}' /proc/meminfo 2>/dev/null || echo 8)
MAX_BY_MEM=$(( MEM_GB / 2 > 0 ? MEM_GB / 2 : 1 ))
TRANSLATED_JOBS=$(( JOBS < MAX_BY_MEM ? JOBS : MAX_BY_MEM ))

if [[ $CLEAN -eq 1 ]]; then rm -rf "$TREE" "$BUILD"; fi

echo "==> Assembling build tree in work/tree"
mkdir -p "$TREE/runtime"
rsync -a --delete --exclude third_party --exclude assets "$RUNTIME/" "$TREE/runtime/"
rsync -a "$WC/runtime/third_party" "$WC/runtime/assets" "$TREE/runtime/"
link_dir "$ROOT/work/generated" "$TREE/generated"
link_dir "$WC/aurora-main" "$TREE/aurora-main"

python3 "$ROOT/scripts/netplay_build_identity.py" --output "$ROOT/work/netplay-simulation-id.txt"
SIMULATION_ID="$(cat "$ROOT/work/netplay-simulation-id.txt")"
echo "==> Configuring (first time downloads aurora's dependencies: Dawn, SDL3, imgui, ...)"
  cmake -S "$TREE/runtime" -B "$BUILD" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ -DCMAKE_ASM_COMPILER=clang \
    -DCMAKE_EXE_LINKER_FLAGS="-fuse-ld=lld" \
    -DRIISORTED_SIMULATION_ID="$SIMULATION_ID" \
    -DMKW_TRANSLATED_COMPILE_JOBS="$TRANSLATED_JOBS" \
    -DMKW_TRANSLATED_SHARD_MANIFEST="$TREE/generated/build_shards/shards.cmake" "${HOST_CMAKE[@]}"
[[ $CONFIGURE_ONLY -eq 1 ]] && { echo "Configured."; exit 0; }

echo "==> Building $TARGET with $JOBS jobs ($TRANSLATED_JOBS for translated shards; ${MEM_GB} GB RAM)"
mkdir -p "$ROOT/work/logs"
LOG="$ROOT/work/logs/build-$(date +%Y%m%d-%H%M%S).log"
set +e
cmake --build "$BUILD" --target "$TARGET" --parallel "$JOBS" 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e
if [[ $rc -ne 0 ]]; then
  echo
  echo "Build failed (log: ${LOG#$ROOT/}). First errors:"
  grep -m 20 -E "error:|undefined reference|undefined symbol" "$LOG" || true
  exit $rc
fi

EXE=""
[[ -f "$BUILD/$TARGET.exe" ]] && EXE=".exe"
if [[ -f "$BUILD/$TARGET$EXE" ]]; then
  mkdir -p "$OUT"
  cp -f "$BUILD/$TARGET$EXE" "$OUT/Resortcompiled$EXE"
  if [[ -n "$EXE" ]]; then
    # The DLLs of the build (Dawn, SDL) and of the CLANG64 C++ runtime go next to the exe.
    find "$BUILD" -maxdepth 1 -name '*.dll' -exec cp -f {} "$OUT/" \;
    for dll in $(ldd "$OUT/Resortcompiled$EXE" | awk '$3 ~ /clang64/ {print $3}'); do cp -f "$dll" "$OUT/"; done
  fi
  for f in dsp_coef.bin initial_pipeline_cache.db cacert.pem; do
    [[ -f "$BUILD/$f" ]] && cp -f "$BUILD/$f" "$OUT/"
  done
  [[ -d "$BUILD/wii_bootstrap" ]] && cp -rf "$BUILD/wii_bootstrap" "$OUT/"
  # Portable layout: portable.txt next to the exe keeps config/saves in out/UserData instead of
  # ~/.local/share/WiiCompiled, and Config.toml points the DVD HLE at the extracted disc.
  # IPL system fonts served by the __OSReadROM HLE (downloaded by setup.sh)
  for f in font_western.bin font_japanese.bin; do
    [[ -f "$ROOT/tools/fonts/$f" ]] && cp -f "$ROOT/tools/fonts/$f" "$OUT/"
  done
  touch "$OUT/portable.txt"
  mkdir -p "$OUT/UserData"
  if [[ ! -f "$OUT/UserData/Config.toml" ]]; then
    printf '%s\n' \
      "# Resortcompiled user configuration (WiiCompiled runtime format; F10 in-game edits this file)" \
      "[paths]" \
      "dvd_root = \"$(python3 "$ROOT/scripts/editions.py" root)\"" > "$OUT/UserData/Config.toml"
  fi
  echo "==> Built out/Resortcompiled$EXE  (run: ./out/Resortcompiled$EXE ; config and logs in out/UserData/)"
fi
