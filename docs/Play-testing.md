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

## 5. What is tested so far

The USA edition was built and started on Windows 11: it boots, passes the MotionPlus check, and plays the opening
scene at 60 FPS. The sports, the menus, saving, Miis and online play are not tested yet; the PAL edition, Linux and
macOS were not built in this round.
