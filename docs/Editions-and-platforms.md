# Editions and platforms

## Editions

The scripts find the edition from the game ID in `sys/boot.bin` of your extracted disc. `projects/editions.json`
holds each edition:

| Game ID | Disc | Program on the disc | Project |
| --- | --- | --- | --- |
| `RZTP01` | Wii Sports Resort (PAL) | `sys/main.dol` | `projects/wsr` |
| `SP2E01` | Wii Sports + Wii Sports Resort (USA) | `files/US/sys/resort/WiiSports2P.dol` | `projects/wsr-sp2e01` |

`python3 scripts/editions.py list` shows the editions. `python3 scripts/editions.py check` checks your extracted disc:
the game ID must be in the table, and the program must have the sha256 of the table.

The USA program is the same code base as the PAL program, built later. Its functions and data sit at other
addresses, and it links a newer Mii library. The PAL runtime (`runtime/wsr`) is the single source. The build makes
the USA runtime from it (`work/runtime/wsr-sp2e01`, not committed):

- `projects/wsr-sp2e01/runtime_addresses.csv`: the USA address of each PAL address in the runtime.
- `projects/wsr-sp2e01/port_overrides.txt`: the addresses that the tables do not hold, each checked in the USA code.
- `projects/wsr-sp2e01/port_edits.json`: code differences that no address holds (the Mii library flag at +0x1B34).

A change to `runtime/wsr` goes to both editions at the next `configure_project.py`.

## Platforms

| Host | Setup | Shell for the build |
| --- | --- | --- |
| Linux x86-64 or aarch64 (Ubuntu, Mint) | `bash setup.sh` (apt) | any bash |
| Windows 10/11 x86-64 | `powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1` | `scripts\windows\shell.cmd` |
| macOS arm64 | WiiCompiled supports Apple Clang; this fork is not tested there | |

The Windows setup needs no admin rights, no WSL and no restart. It puts MSYS2 (CLANG64 toolchain) and the .NET 8
SDK in `tools\host` of the checkout. Give `-Tools <folder>` to put them in another folder; then give the same folder
to `shell.cmd`.

The build steps are the same on every host:

```bash
bash scripts/extract.sh /path/to/your/disc.rvz [--out /folder/for/the/game/files]
python3 scripts/configure_project.py
bash scripts/translate.sh
bash scripts/build.sh
```

The disc image can be in any folder. `--out` puts the extracted game files in another folder (for example a drive
with more free space); `work/data_root.txt` records that folder, and the later steps and `out/UserData/Config.toml`
use it. `scripts/windows/build.sh` (the Windows cross build on a Linux host) stays available for releases.

## Online play

Online play matches players by a simulation identity (`scripts/netplay_build_identity.py`): a hash of the runtime,
aurora and the translated code. Each edition has its own identity, because its translated code is different. A PAL
player and a USA player never join one session; a session of 2 editions would desync. The identity makes the line
ends equal (CRLF and LF) and removes the checkout path, so a Windows build and a Linux build of the same sources and
the same edition get the same identity and can play together.

## Adding another edition

The tools are general: the targets are arguments.

1. Extract the disc. Add a row to `projects/editions.json` (game ID, program path, program sha256, project folder).
2. Split the program with dtk (`dtk dol split`) to get its `symbols.txt`.
3. `python3 scripts/align_map.py --symbols <symbols.txt> --out projects/<new>` lines up the functions with the PAL
   map and moves the map, the hook table, the address table and the hand names. `ALIGN_REPORT.md` lists each address
   that did not move.
4. Data rows: `scripts/data_by_users.py` finds a data address from the functions that use the variable (a decomp's
   SDK source shows the users). Check each row in the new program's code; a block of data moves by 1 shift, so
   the shift of a checked row shows the shift of its neighbours.
5. Copy `projects/wsr/recomp.yml` to the new project and change its ID, game ID, region, r13 and r2 bases, program
   path and sha256.
6. `python3 scripts/port_runtime.py --to projects/<new> --make-table --symbols <symbols.txt>` writes the runtime
   address table. Put each UNRESOLVED address in `port_overrides.txt` after a check in the new program's code.
7. Compare the size of each hooked function in the 2 builds. A changed size can mean a changed struct; put such a
   difference in `port_edits.json`.
8. Set `"runtime": "work/runtime/wsr-<new>"` and `"ported_from": "projects/wsr"` in the edition row. Configure,
   translate, build, test.

No file from a disc goes in the repo: only addresses, names, hashes and tools.
`python3 scripts/check_no_game_data.py` checks every tracked file before a push (disc formats, programs, binaries).
