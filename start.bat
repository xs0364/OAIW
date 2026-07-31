@echo off
cd /d D:\OAIW
echo ========================================
echo   OAIW 操作部AI工作台
echo ========================================
echo.
echo [1/2] Starting Backend (:7999)...
start "OAIW-Backend" cmd /c "python backend\main.py"
timeout /t 3 /nobreak >nul
echo.
echo [2/2] Starting Frontend (:5175)...
cd frontend && start "OAIW-Frontend" cmd /c "npm run dev"
echo.
echo ========================================
echo   Frontend: http://localhost:5175
echo   Backend:  http://localhost:7999
echo   API Docs: http://localhost:7999/docs
echo ========================================
pause
