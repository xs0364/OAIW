@echo off
cd /d D:\OAIW
title OAIW-RPA
chcp 65001 >nul
cls
echo ========================================
echo   OAIW Agent Team - RPA(rpa)
echo ========================================
echo.
echo Tasks: .team\tasks\  Results: .team\results\
echo.
python .team\agent_rpa_runner.py
pause
