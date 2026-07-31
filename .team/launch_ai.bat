@echo off
cd /d D:\OAIW
title OAIW-AI
chcp 65001 >nul
cls
echo ========================================
echo   OAIW Agent Team - AI(ai)
echo ========================================
echo.
echo Tasks: .team\tasks\  Results: .team\results\
echo.
python .team\agent_ai_runner.py
pause
