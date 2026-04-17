@echo off
chcp 65001 >nul
title Job Search Dashboard

echo.
echo ========================================
echo    Job Search Dashboard - מתחיל...
echo ========================================
echo.

cd /d "%~dp0"

start http://localhost:5000

.venv\Scripts\python.exe web_app.py

pause
