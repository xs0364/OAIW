@echo off
cd /d D:\OAIW
title OAIW-FE
chcp 65001 >nul
cls
echo ========================================
echo   OAIW Agent Team - FE(fe)
echo ========================================
echo.
echo Tasks: .team\tasks\  Results: .team\results\
echo.
python .team\agent_fe_runner.py
pause
