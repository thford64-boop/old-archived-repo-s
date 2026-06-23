@echo off
echo Rewriting run_analysis.bat ...

echo @echo off>run_analysis.bat
echo :: ============================================================>>run_analysis.bat
echo ::  Hardware Tier Analysis Tool v3 -- Build ^& Run Pipeline>>run_analysis.bat
echo ::  run_analysis.bat>>run_analysis.bat
echo ::>>run_analysis.bat
echo ::  Requirements:>>run_analysis.bat
echo ::    - MinGW-w64 / GCC on PATH>>run_analysis.bat
echo ::    - Python 3.8+ on PATH>>run_analysis.bat
echo :: ============================================================>>run_analysis.bat
echo.>>run_analysis.bat
echo setlocal EnableDelayedExpansion>>run_analysis.bat
echo title Hardware Tier Analysis Tool v3>>run_analysis.bat
echo.>>run_analysis.bat
echo echo.>>run_analysis.bat
echo echo  +----------------------------------------------------------+>>run_analysis.bat
echo echo  ^^^|   HARDWARE TIER ANALYSIS TOOL v3  --  Pipeline         ^^^|>>run_analysis.bat
echo echo  ^^^|   Now with systeminfo: richer data, more detail         ^^^|>>run_analysis.bat
echo echo  +----------------------------------------------------------+>>run_analysis.bat
echo echo.>>run_analysis.bat
echo.>>run_analysis.bat
echo :: ---- 0. Check GCC ---------------------------------------->>run_analysis.bat
echo where gcc ^>nul 2^>^&1>>run_analysis.bat
echo if %%ERRORLEVEL%% NEQ 0 (>>run_analysis.bat
echo     echo  [ERROR] gcc not found on PATH.>>run_analysis.bat
echo     echo.>>run_analysis.bat
echo     echo  Fix options:>>run_analysis.bat
echo     echo    Option A (MSYS2 -- recommended):>>run_analysis.bat
echo     echo      1. Download MSYS2 from https://www.msys2.org/>>run_analysis.bat
echo     echo      2. In MSYS2 shell run: pacman -S mingw-w64-ucrt-x86_64-gcc>>run_analysis.bat
echo     echo      3. Add C:\msys64\ucrt64\bin to your Windows PATH>>run_analysis.bat
echo     echo.>>run_analysis.bat
echo     echo    Option B (winlibs standalone):>>run_analysis.bat
echo     echo      Download from https://winlibs.com/ -- extract and add bin\ to PATH>>run_analysis.bat
echo     echo.>>run_analysis.bat
echo     pause>>run_analysis.bat
echo     exit /b 1>>run_analysis.bat
echo )>>run_analysis.bat
echo gcc --version>>run_analysis.bat
echo.>>run_analysis.bat
echo :: ---- 1. Compile ------------------------------------------>>run_analysis.bat
echo echo.>>run_analysis.bat
echo echo  [Step 1/3]  Compiling scanner.c ...>>run_analysis.bat
echo echo.>>run_analysis.bat
echo.>>run_analysis.bat
echo gcc scanner.c -o scanner.exe -O2>>run_analysis.bat
echo.>>run_analysis.bat
echo if %%ERRORLEVEL%% NEQ 0 (>>run_analysis.bat
echo     echo.>>run_analysis.bat
echo     echo  [ERROR] Compilation failed with the simple flags. Trying extended flags...>>run_analysis.bat
echo     gcc scanner.c -o scanner.exe -lole32 -loleaut32 -lwbemuuid -lws2_32 -DUNICODE -D_UNICODE -O2>>run_analysis.bat
echo     if !ERRORLEVEL! NEQ 0 (>>run_analysis.bat
echo         echo  [ERROR] Both compile attempts failed. See messages above.>>run_analysis.bat
echo         echo  Make sure you have MinGW-w64 (not MinGW-32) installed.>>run_analysis.bat
echo         pause>>run_analysis.bat
echo         exit /b 1>>run_analysis.bat
echo     )>>run_analysis.bat
echo )>>run_analysis.bat
echo echo  [Step 1/3]  OK  --^^^>  scanner.exe>>run_analysis.bat
echo.>>run_analysis.bat
echo :: ---- 2. Run scanner -------------------------------------->>run_analysis.bat
echo echo.>>run_analysis.bat
echo echo  [Step 2/3]  Running hardware scanner (systeminfo may take ~15 sec)...>>run_analysis.bat
echo echo  ---------------------------------------------------------->>run_analysis.bat
echo scanner.exe>>run_analysis.bat
echo if %%ERRORLEVEL%% NEQ 0 (>>run_analysis.bat
echo     echo.>>run_analysis.bat
echo     echo  [ERROR] Scanner exited with error code %%ERRORLEVEL%%.>>run_analysis.bat
echo     pause>>run_analysis.bat
echo     exit /b 1>>run_analysis.bat
echo )>>run_analysis.bat
echo echo  ---------------------------------------------------------->>run_analysis.bat
echo.>>run_analysis.bat
echo if not exist local_specs.json (>>run_analysis.bat
echo     echo  [ERROR] local_specs.json was not created.>>run_analysis.bat
echo     pause>>run_analysis.bat
echo     exit /b 1>>run_analysis.bat
echo )>>run_analysis.bat
echo echo  [Step 2/3]  OK  --^^^>  local_specs.json>>run_analysis.bat
echo.>>run_analysis.bat
echo :: ---- 3. Python analyzer ---------------------------------->>run_analysis.bat
echo echo.>>run_analysis.bat
echo echo  [Step 3/3]  Running Python analyzer...>>run_analysis.bat
echo echo  ==========================================================>>run_analysis.bat
echo.>>run_analysis.bat
echo set PYTHON_CMD=>>run_analysis.bat
echo where python ^>nul 2^>^&1 ^&^& set PYTHON_CMD=python>>run_analysis.bat
echo if "!PYTHON_CMD!"=="" (>>run_analysis.bat
echo     where python3 ^>nul 2^>^&1 ^&^& set PYTHON_CMD=python3>>run_analysis.bat
echo )>>run_analysis.bat
echo if "!PYTHON_CMD!"=="" (>>run_analysis.bat
echo     echo  [ERROR] Python not found on PATH.>>run_analysis.bat
echo     echo  Download Python 3 from https://python.org/downloads/>>run_analysis.bat
echo     echo  Make sure to check "Add Python to PATH" during install.>>run_analysis.bat
echo     pause>>run_analysis.bat
echo     exit /b 1>>run_analysis.bat
echo )>>run_analysis.bat
echo.>>run_analysis.bat
echo !PYTHON_CMD! analyzer.py>>run_analysis.bat
echo if %%ERRORLEVEL%% NEQ 0 (>>run_analysis.bat
echo     echo.>>run_analysis.bat
echo     echo  [ERROR] Analyzer failed with code %%ERRORLEVEL%%.>>run_analysis.bat
echo     pause>>run_analysis.bat
echo     exit /b 1>>run_analysis.bat
echo )>>run_analysis.bat
echo.>>run_analysis.bat
echo :: ---- Done ------------------------------------------------>>run_analysis.bat
echo echo.>>run_analysis.bat
echo echo  +----------------------------------------------------------+>>run_analysis.bat
echo echo  ^^^|  Done!  Report saved to: hardware_report.txt            ^^^|>>run_analysis.bat
echo echo  +----------------------------------------------------------+>>run_analysis.bat
echo echo.>>run_analysis.bat
echo.>>run_analysis.bat
echo set /p OPEN="  Open hardware_report.txt now? [Y/N]: ">>run_analysis.bat
echo if /i "!OPEN!"=="Y" start notepad hardware_report.txt>>run_analysis.bat
echo.>>run_analysis.bat
echo endlocal>>run_analysis.bat

echo Done! run_analysis.bat has been rewritten.
echo Now run:  run_analysis.bat
