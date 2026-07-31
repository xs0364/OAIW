@echo off
chcp 65001 >nul
cd /d D:\OAIW

echo ============================================
echo  OAIW 7 Agent Team Launcher
echo ============================================
echo.

:: 先关掉旧的 claude 窗口（保留当前窗口）
echo 正在清理旧Agent进程...
taskkill /f /fi "windowtitle eq OAIW-PM*" /t 2>nul
taskkill /f /fi "windowtitle eq OAIW-FE*" /t 2>nul
taskkill /f /fi "windowtitle eq OAIW-BE*" /t 2>nul
taskkill /f /fi "windowtitle eq OAIW-RPA*" /t 2>nul
taskkill /f /fi "windowtitle eq OAIW-Biz*" /t 2>nul
taskkill /f /fi "windowtitle eq OAIW-AI*" /t 2>nul
taskkill /f /fi "windowtitle eq OAIW-QA*" /t 2>nul
timeout /t 2 /nobreak >nul
echo  旧进程已清理
echo.

:: 用 Python 启动器
echo 正在启动 7 个 Agent 窗口...
D:\OAIW\.team\launch.bat
echo.
echo 启动完成！检查每个Agent窗口是否就绪。
echo 你是 PM，去每个窗口确认它们在线。
pause
