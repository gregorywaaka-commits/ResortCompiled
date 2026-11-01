# Resortcompiled - one-time setup for a native Windows build. No admin rights, no WSL, no restart.
#
#   powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1 [-Tools <folder>]
#
# What it does:
#   1. Unpacks MSYS2 (base archive, not the installer) into <Tools>\msys64 and installs the CLANG64 toolchain
#      (clang, lld, cmake, ninja, python) and rsync, git, patch, curl, unzip with pacman
#   2. Installs the .NET 8 SDK for this user into <Tools>\dotnet (Microsoft's dotnet-install.ps1)
#   3. Runs setup.sh in the CLANG64 shell (WiiCompiled checkout, patches, dtk, fonts, translator)
# <Tools> is tools\host inside the checkout by default. Safe to re-run.
param([string]$Tools = (Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "tools\host"))
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
New-Item -ItemType Directory -Force $Tools | Out-Null
$Msys = Join-Path $Tools "msys64"
$Bash = Join-Path $Msys "usr\bin\bash.exe"

if (-not (Test-Path $Bash)) {
    Write-Host "==> Downloading MSYS2"
    $Archive = Join-Path $Tools "msys2-base.tar.xz"
    Invoke-WebRequest "https://repo.msys2.org/distrib/msys2-x86_64-latest.tar.xz" -OutFile $Archive
    tar -xf $Archive -C $Tools
    Remove-Item $Archive
}
$env:MSYSTEM = "CLANG64"
$env:CHERE_INVOKING = "1"
Write-Host "==> First start of MSYS2 (keys) and package update"
& $Bash -lc "true"
& $Bash -lc "pacman -Syu --noconfirm"
& $Bash -lc "pacman -Syu --noconfirm"
Write-Host "==> Installing the CLANG64 toolchain"
& $Bash -lc ("pacman -S --noconfirm --needed mingw-w64-clang-x86_64-clang mingw-w64-clang-x86_64-lld " +
    "mingw-w64-clang-x86_64-cmake mingw-w64-clang-x86_64-ninja mingw-w64-clang-x86_64-python " +
    "mingw-w64-clang-x86_64-python-yaml mingw-w64-clang-x86_64-python-pip rsync git patch curl unzip")
if ($LASTEXITCODE -ne 0) { throw "pacman failed" }

$Dotnet = Join-Path $Tools "dotnet"
if (-not (Test-Path (Join-Path $Dotnet "dotnet.exe"))) {
    Write-Host "==> Installing the .NET 8 SDK for this user"
    $Installer = Join-Path $Tools "dotnet-install.ps1"
    Invoke-WebRequest "https://dot.net/v1/dotnet-install.ps1" -OutFile $Installer
    & $Installer -Channel 8.0 -InstallDir $Dotnet -NoPath
}

# The shell for every later step: CLANG64 tools first, then .NET.
$DotnetPosix = (& (Join-Path $Msys "usr\bin\cygpath.exe") -u $Dotnet).Trim()
$RootPosix = (& (Join-Path $Msys "usr\bin\cygpath.exe") -u $Root).Trim()
$Profile = "export PATH=`"$DotnetPosix`:`$PATH`" DOTNET_CLI_TELEMETRY_OPTOUT=1"
Set-Content -Encoding ascii (Join-Path $Tools "env.sh") $Profile
Write-Host "==> setup.sh"
& $Bash -lc "source '$((& (Join-Path $Msys 'usr\bin\cygpath.exe') -u (Join-Path $Tools 'env.sh')).Trim())' && cd '$RootPosix' && bash setup.sh"
if ($LASTEXITCODE -ne 0) { throw "setup.sh failed" }
Write-Host ""
Write-Host "Setup complete. Start the build shell with:  scripts\windows\shell.cmd"
