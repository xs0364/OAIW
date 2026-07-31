@echo off
cd /d D:\OAIW
title OAIW-PM
chcp 65001 >nul
cls
echo ========================================
echo   OAIW Agent Team - PM(pm)
echo ========================================
echo.
echo Tasks: .team\tasks\  Results: .team\results\
echo.
python .team\agent_pm_runner.py
pause
