@echo off
rem Opens the CLANG64 build shell in the checkout, with .NET 8 on PATH (after scripts\windows\setup.ps1).
rem   scripts\windows\shell.cmd [TOOLS_FOLDER]
setlocal
set "ROOT=%~dp0..\.."
set "TOOLS=%~1"
if "%TOOLS%"=="" set "TOOLS=%ROOT%\tools\host"
set MSYSTEM=CLANG64
set CHERE_INVOKING=1
cd /d "%ROOT%"
"%TOOLS%\msys64\usr\bin\bash.exe" -l -c "source \"$(cygpath -u '%TOOLS%\env.sh')\"; exec bash -i"
