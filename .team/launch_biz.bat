@echo off
cd /d D:\OAIW
title OAIW-Biz
chcp 65001 >nul
cls
echo ========================================
echo   OAIW Agent Team - Biz(biz)
echo ========================================
echo.
echo Tasks: .team\tasks\  Results: .team\results\
echo.
python .team\agent_biz_runner.py
pause
