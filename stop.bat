@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================
echo      edu_rag v2.0 - Stop Services
echo ==========================================
echo.

REM -- Stop Backend (port 8000) --
echo [1/2] Stopping Backend (port 8000)...
set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000" ^| findstr "LISTENING"') do (
    set FOUND=1
    taskkill /F /PID %%a >nul 2>&1 && echo         Stopped - PID %%a
)
if !FOUND!==0 echo         No Backend process found

REM -- Stop Frontend (port 5173) --
echo [2/2] Stopping Frontend (port 5173)...
set FOUND=0
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173" ^| findstr "LISTENING"') do (
    set FOUND=1
    taskkill /F /PID %%a >nul 2>&1 && echo         Stopped - PID %%a
)
if !FOUND!==0 echo         No Frontend process found

REM -- Clean up leftover cmd windows --
taskkill /FI "WINDOWTITLE eq edu_rag_Backend*"  >nul 2>&1
taskkill /FI "WINDOWTITLE eq edu_rag_Frontend*" >nul 2>&1

echo.
echo All edu_rag services stopped.
echo MySQL / Redis / Ollama were not touched.
echo.

timeout /t 3 /nobreak >nul
endlocal
