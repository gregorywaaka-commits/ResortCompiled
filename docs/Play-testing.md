# Play testing

Thank you for testing. You need your own Wii Sports Resort disc image: PAL `RZTP01`, or the USA
"Wii Sports + Wii Sports Resort" disc `SP2E01`. This repository has no game files, and the build never downloads one.

## 1. Set up (once)

**Windows 10/11 (no admin rights, no WSL):**

```
git clone -b us-sp2e01 https://github.com/gregorywaaka-commits/ResortCompiled.git
cd ResortCompiled
powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1
scripts\windows\shell.cmd
```

The setup puts MSYS2 and .NET 8 in `tools\host` (about 3 GB). `shell.cmd` opens the build shell for the next steps.

**Linux (Ubuntu or Mint):** `git clone -b us-sp2e01 ...`, then `bash setup.sh`.

## 2. Build (in the build shell, about 1 to 2 hours the first time)

```
bash scripts/extract.sh /path/to/your/disc.rvz        # add --out <folder> to put the game files elsewhere
python3 scripts/configure_project.py
bash scripts/translate.sh
bash scripts/build.sh
```

The game is `out/Resortcompiled` (`out/Resortcompiled.exe` on Windows).

## 3. Controls (keyboard and mouse, or a DualSense)

| Wii Remote | Keyboard and mouse |
| --- | --- |
| pointer | the mouse |
| A | left click or Z |
| B | right click or X |
| 1 / 2 | 1 / 2 |
| + / - | Enter or = / Backspace or - |
| Home | H |
| D-pad | the arrows or WASD |
| tilt (MotionPlus) | hold Left Shift or the middle mouse button and move the mouse; the wheel rolls |
| shake | Space |
| recenter | R |

## 4. What to report

For each problem: your edition (PAL or USA), your system (Windows or Linux, the graphics card), the sport and the
screen, and what you did just before. Attach the newest folder of `out/UserData/Logs/` (a crash writes
`crash_panic.txt` there).

For a problem with a missing or wrong file, start the game with the file trace on and attach the console output:

```
RESORT_DVD_TRACE=1 ./out/Resortcompiled.exe 2> trace.txt
```

## 5. Miis

The sports need at least 1 Mii. A real Wii keeps them in its NAND; this build keeps them in
`out/UserData/NAND/shared2/menu/FaceLib/` (`RFL_Res.dat`, the face parts, and `RFL_DB.dat`, the Miis). Copy both
files from a Dolphin NAND or a Wii NAND dump, use `bash scripts/seed_nand.sh`, or use the launcher's Mii editor.
The face parts are also inside the System Menu package of your disc's update partition (the launcher reads them
from there; it needs a dtk that accepts `wad extract -q`).

## 6. What is tested so far

The USA edition was built and played on Windows 11 with keyboard and mouse: the safety screen, the MotionPlus
check, the opening skydive, the title screen, the main menu with all 12 sports, the Bowling menu, the player count,
Mii selection with a drawn Mii, the throwing style and the hand, and the saved player list. All ran at about 60 FPS.

A full Bowling Standard Game (10 frames, 1 player, Automatic style) was played to the end on the USA edition: the
throws, the pins, the replays, the score of each frame, the final ranking (69) and the saved high score. The log has
no panic and no crash.

The checks that need no game disc run on every push on Linux and on Windows (GitHub Actions, `checks.yml`): no game
data in the repository, the editions, the shell scripts, the rollback, netplay pipeline and motion math tests, and
`scripts/check_pal_unchanged.py`. That check proves the PAL edition plays as upstream: its project is unchanged, and
the runtime changes only by added code that the PAL program never runs.

Not tested yet on a real disc: the other sports, online play, the PAL edition (no PAL disc here), and Linux and
macOS beyond the checks above.

### Bowling with keyboard and mouse

Choose Automatic style. On the lane: press A, hold B (X or the right button) and keep it held, then hold Left Shift
and move the mouse down (the back swing) and then up, a little longer and quicker (the forward swing). Let go of B
after the ball rolls. "Try not to swing the ball too abruptly" means the swing was too quick; "do not release B" with
B held means the game saw no swing (too slow or too small). Press R to recenter the remote between throws.

Known: the log can show "unmapped guest touch" warnings during the opening skydive (one function reads a few
wrong addresses; the runtime gives zeros and the game goes on). Report it if you see it at another place.
