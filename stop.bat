@echo off
echo Stopping edu_rag services...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo Backend stopped (PID: %%a)
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
    echo Frontend stopped (PID: %%a)
)

echo Done.
ping -n 5 127.0.0.1 >nul 2>&1
