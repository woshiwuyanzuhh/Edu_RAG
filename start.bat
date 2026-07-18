@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================
echo      edu_rag v2.0 - Quick Start
echo ==========================================
echo.

REM -- Locate Python / Conda environment --
set "CONDA_BASE=F:\anaconda3"
set "CONDA_ENV=EduRAG"

if exist "%CONDA_BASE%\Scripts\activate.bat" (
    echo [OK] Conda found at %CONDA_BASE%
    call "%CONDA_BASE%\Scripts\activate.bat" "%CONDA_ENV%"
) else (
    echo [!] Conda not found, trying system PATH...
)

REM -- Verify uvicorn is now available --
where uvicorn >nul 2>&1
if %errorlevel% neq 0 (
    python -m uvicorn --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] uvicorn not found - is EduRAG conda env installed?
        pause
        exit /b 1
    )
    set "UVICORN_CMD=python -m uvicorn"
) else (
    set "UVICORN_CMD=uvicorn"
)

REM -- Verify node --
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] node not in PATH
    pause
    exit /b 1
)

echo [OK] uvicorn ready
echo [OK] node ready
echo.
echo Make sure these services are running:
echo   - MySQL  (edu_rag database)
echo   - Redis  (default port 6379)
echo   - Ollama (bge-m3 embedding + qwen3:4b LLM)
echo.

REM -- Install frontend deps if needed --
if not exist "frontend\node_modules\" (
    echo [!] Installing frontend dependencies...
    cd /d "%~dp0frontend"
    call npm install
    cd /d "%~dp0"
    echo [OK] Done
    echo.
)

REM -- Start Backend --
echo [1/2] Starting Backend on port 8000...
start "edu_rag_Backend" cmd /k "cd /d %~dp0 && %UVICORN_CMD% src.orchestration.app:app --reload --host 0.0.0.0 --port 8000"

REM -- Start Frontend --
echo [2/2] Starting Frontend on port 5173...
start "edu_rag_Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ------------------------------------------
echo   Backend  : http://localhost:8000
echo   API Docs : http://localhost:8000/docs
echo   Frontend : http://localhost:5173
echo ------------------------------------------
echo   Run stop.bat to shut down all services
echo ------------------------------------------
echo.

REM -- Open browser --
timeout /t 6 /nobreak >nul
start http://localhost:5173

endlocal
