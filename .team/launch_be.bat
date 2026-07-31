@echo off
cd /d D:\OAIW
title OAIW-BE
chcp 65001 >nul
cls
echo ========================================
echo   OAIW Agent Team - BE(be)
echo ========================================
echo.
echo Tasks: .team\tasks\  Results: .team\results\
echo.
python .team\agent_be_runner.py
pause
