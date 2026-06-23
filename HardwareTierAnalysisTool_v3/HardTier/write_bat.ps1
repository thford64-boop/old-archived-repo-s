# Run this in PowerShell from your project folder.
# It writes run_analysis.bat directly -- no download needed.

$content = @'
@echo off
:: ============================================================
::  Hardware Tier Analysis Tool v3 -- Build & Run Pipeline
::  run_analysis.bat
::
::  Requirements:
::    - MinGW-w64 / GCC on PATH
::    - Python 3.8+ on PATH
:: ============================================================

setlocal EnableDelayedExpansion
title Hardware Tier Analysis Tool v3

echo.
echo  +----------------------------------------------------------+
echo  ^|   HARDWARE TIER ANALYSIS TOOL v3  --  Pipeline         ^|
echo  ^|   Now with systeminfo: richer data, more detail         ^|
echo  +----------------------------------------------------------+
echo.

:: ---- 0. Check GCC ----------------------------------------
where gcc >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] gcc not found on PATH.
    echo.
    echo  Fix options:
    echo    Option A (MSYS2 -- recommended):
    echo      1. Download MSYS2 from https://www.msys2.org/
    echo      2. In MSYS2 shell run: pacman -S mingw-w64-ucrt-x86_64-gcc
    echo      3. Add C:\msys64\ucrt64\bin to your Windows PATH
    echo.
    echo    Option B (winlibs standalone):
    echo      Download from https://winlibs.com/ -- extract and add bin\ to PATH
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%V in ('gcc --version 2^>^&1 ^| findstr /i "gcc"') do (
    echo  [GCC]  %%V
    goto :gcc_done
)
:gcc_done

:: ---- 1. Compile ------------------------------------------
echo.
echo  [Step 1/3]  Compiling scanner.c ...
echo.

gcc scanner.c -o scanner.exe -O2

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] Compilation failed with the simple flags. Trying extended flags...
    gcc scanner.c -o scanner.exe -lole32 -loleaut32 -lwbemuuid -lws2_32 -DUNICODE -D_UNICODE -O2
    if !ERRORLEVEL! NEQ 0 (
        echo  [ERROR] Both compile attempts failed. See messages above.
        echo  Make sure you have MinGW-w64 (not MinGW-32) installed.
        pause
        exit /b 1
    )
)
echo  [Step 1/3]  OK  --^>  scanner.exe

:: ---- 2. Run scanner --------------------------------------
echo.
echo  [Step 2/3]  Running hardware scanner (systeminfo may take ~15 sec)...
echo  ----------------------------------------------------------
scanner.exe
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] Scanner exited with error code %ERRORLEVEL%.
    pause
    exit /b 1
)
echo  ----------------------------------------------------------

if not exist local_specs.json (
    echo  [ERROR] local_specs.json was not created.
    pause
    exit /b 1
)
echo  [Step 2/3]  OK  --^>  local_specs.json

:: ---- 3. Python analyzer ----------------------------------
echo.
echo  [Step 3/3]  Running Python analyzer...
echo  ==========================================================

set PYTHON_CMD=
where python >nul 2>&1 && set PYTHON_CMD=python
if "!PYTHON_CMD!"=="" (
    where python3 >nul 2>&1 && set PYTHON_CMD=python3
)
if "!PYTHON_CMD!"=="" (
    echo  [ERROR] Python not found on PATH.
    echo  Download Python 3 from https://python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

!PYTHON_CMD! analyzer.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] Analyzer failed with code %ERRORLEVEL%.
    pause
    exit /b 1
)

:: ---- Done ------------------------------------------------
echo.
echo  +----------------------------------------------------------+
echo  ^|  Done!  Report saved to: hardware_report.txt            ^|
echo  +----------------------------------------------------------+
echo.

set /p OPEN="  Open hardware_report.txt now? [Y/N]: "
if /i "!OPEN!"=="Y" start notepad hardware_report.txt

endlocal
'@

$content | Set-Content -Path 'run_analysis.bat' -Encoding ASCII
Write-Host 'Done. run_analysis.bat written.' -ForegroundColor Green
Write-Host ''
Write-Host 'Now run:  .\run_analysis.bat'