@echo off
:: install_plugin.bat
:: Run this after a successful build to install FXPack into DaVinci Resolve.
:: Run as ADMINISTRATOR — the OFX plugin folder requires admin rights.

setlocal enabledelayedexpansion

echo ============================================================
echo  FXPack OFX Plugin Installer
echo ============================================================
echo.

:: ── Resolve's OFX plugin folder (Windows, all versions) ──────────────────
set OFX_DIR=C:\Program Files\Common Files\OFX\Plugins

:: ── Bundle source (built by VS, relative to this script) ─────────────────
set BUNDLE_SRC=%~dp0bundle\FXPack.ofx.bundle

:: ── Destination ──────────────────────────────────────────────────────────
set BUNDLE_DST=%OFX_DIR%\FXPack.ofx.bundle

echo Source bundle : %BUNDLE_SRC%
echo Destination   : %BUNDLE_DST%
echo.

:: Check the .ofx binary exists (Release build)
if not exist "%BUNDLE_SRC%\Contents\Win64\FXPack.ofx" (
    echo [ERROR] FXPack.ofx not found!
    echo         Build the project in Visual Studio first (Release or Debug).
    echo         Expected: %BUNDLE_SRC%\Contents\Win64\FXPack.ofx
    pause
    exit /b 1
)

:: Create OFX Plugins folder if it doesn't exist
if not exist "%OFX_DIR%" (
    echo Creating OFX Plugins directory...
    mkdir "%OFX_DIR%"
    if errorlevel 1 (
        echo [ERROR] Could not create %OFX_DIR%
        echo         Are you running as Administrator?
        pause
        exit /b 1
    )
)

:: Remove old installation
if exist "%BUNDLE_DST%" (
    echo Removing existing installation...
    rd /s /q "%BUNDLE_DST%"
)

:: Copy the bundle
echo Installing FXPack.ofx.bundle...
xcopy /E /I /Y "%BUNDLE_SRC%" "%BUNDLE_DST%"
if errorlevel 1 (
    echo [ERROR] Copy failed. Run this script as Administrator.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SUCCESS! FXPack installed to:
echo  %BUNDLE_DST%
echo.
echo  Next steps:
echo    1. Close DaVinci Resolve completely
echo    2. Re-launch DaVinci Resolve
echo    3. Open Effects Library ^> OpenFX ^> FXPack
echo ============================================================
echo.
pause
