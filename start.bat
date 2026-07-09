@echo off
echo === edu_rag v2.0 ===
echo.

echo [1/2] Starting Backend on port 8000...
start "" cmd /k "cd /d C:\Users\lenovo\Desktop\ml_dl_nlp\edu_rag && F:\anaconda3\envs\EduRAG\Scripts\uvicorn.exe src.orchestration.app:app --reload --host 0.0.0.0 --port 8000"

echo [2/2] Starting Frontend on port 5173...
start "" cmd /k "cd /d C:\Users\lenovo\Desktop\ml_dl_nlp\edu_rag\frontend && npm run dev"

echo.
echo Backend : http://localhost:8000
echo Frontend: http://localhost:5173
echo.

ping -n 8 127.0.0.1 >nul 2>&1
start http://localhost:5173
