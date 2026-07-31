@echo off
cd /d D:\OAIW
title OAIW-QA
chcp 65001 >nul
cls
echo ========================================
echo   OAIW Agent Team - QA(qa)
echo ========================================
echo.
echo Tasks: .team\tasks\  Results: .team\results\
echo.
python .team\agent_qa_runner.py
pause
