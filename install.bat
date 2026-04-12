@echo off
setlocal

rem ============================================================
rem  RST - Dependency Installer
rem  Installs: Python 3.12, pywebview
rem  Does NOT install the RST extension itself - use pyRevit:
rem    pyRevit tab -> Extensions -> Add Extension -> paste repo URL
rem ============================================================

title RST - Dependency Installer

echo.
echo ============================================================
echo   RST Dependency Installer
echo ============================================================
echo.
echo This will install:
echo   1. Python 3.12   (if missing)
echo   2. pywebview     (always upgraded)
echo.
echo Runs as the current user. No admin required.
echo.
pause

set "STEP1=SKIP"
set "STEP2=SKIP"
set "PYREVIT=UNKNOWN"

rem ---------- Step 0: winget present? ----------
echo.
echo [0/2] Checking for winget...
where winget >nul 2>&1
if errorlevel 1 goto :no_winget
echo   OK: winget present.
goto :step1

:no_winget
echo   FAIL: winget not found.
echo   Install "App Installer" from the Microsoft Store, then re-run:
echo   https://apps.microsoft.com/detail/9NBLGGH4NNS1
goto :summary_fail

rem ---------- Step 1: Python 3.12 ----------
:step1
echo.
echo [1/2] Python 3.12...
py -3.12 -V >nul 2>&1
if not errorlevel 1 goto :step1_skip

echo   Installing Python 3.12 via winget...
winget install --id Python.Python.3.12 --scope user --accept-source-agreements --accept-package-agreements --silent
if errorlevel 1 goto :step1_fail

py -3.12 -V >nul 2>&1
if errorlevel 1 goto :step1_need_restart
set "STEP1=OK"
goto :step2

:step1_skip
for /f "tokens=*" %%v in ('py -3.12 -V 2^>^&1') do echo   Already installed: %%v. Skipping.
set "STEP1=SKIP"
goto :step2

:step1_fail
echo   FAIL: winget install returned an error.
set "STEP1=FAIL"
goto :summary

:step1_need_restart
echo.
echo ============================================================
echo   Python 3.12 installed successfully.
echo ============================================================
echo.
echo   PATH needs a fresh terminal to pick up the new install.
echo.
echo   1. Close this window.
echo   2. Open a fresh cmd or PowerShell window.
echo   3. Re-run install.bat from the same folder.
echo.
echo   The script will skip step 1 and continue with pywebview.
echo.
pause
endlocal
exit /b 0

rem ---------- Step 2: pywebview ----------
:step2
echo.
echo [2/2] pywebview...
py -3.12 -m pip install --user --no-cache-dir --upgrade pywebview
if errorlevel 1 goto :step2_fail
set "STEP2=OK"
goto :pyrevit_check

:step2_fail
echo   FAIL: pip install pywebview returned an error.
set "STEP2=FAIL"
goto :summary

rem ---------- Soft check: pyRevit ----------
:pyrevit_check
echo.
echo Checking for pyRevit...
if exist "%APPDATA%\pyRevit" goto :pyrevit_found
set "PYREVIT=MISSING"
echo   WARN: pyRevit not detected at %%APPDATA%%\pyRevit.
echo         Install pyRevit 4.8+ before adding the RST extension.
echo         https://github.com/pyrevitlabs/pyRevit
goto :summary

:pyrevit_found
set "PYREVIT=FOUND"
echo   OK: pyRevit appears to be installed.
goto :summary

rem ---------- Summary ----------
:summary
echo.
echo ============================================================
echo   Summary
echo ============================================================
echo   Python 3.12        : %STEP1%
echo   pywebview install  : %STEP2%
echo   pyRevit detected   : %PYREVIT%
echo ============================================================

if "%STEP1%"=="FAIL" goto :summary_fail
if "%STEP2%"=="FAIL" goto :summary_fail

echo.
echo SUCCESS. Dependencies are ready.
echo.
echo Next step - install the RST extension via pyRevit:
echo   1. Open Revit
echo   2. pyRevit tab -^> Extensions -^> Add Extension
echo   3. Paste: https://github.com/jedbjorn/RST
echo   4. Reload pyRevit
echo.
pause
endlocal
exit /b 0

:summary_fail
echo.
echo FAILED. Review the errors above and re-run this script.
echo.
pause
endlocal
exit /b 1
