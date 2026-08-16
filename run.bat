@echo off
title Twinclers Guard Launcher
cd /d "%~dp0"

:: Cek Python di PATH atau lokasi default instalasi pengguna
set PYTHON_EXE=python
where python >nul 2>&1
if %errorlevel% neq 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
        set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
        set PYTHON_EXE="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    ) else (
        echo [ERROR] Python tidak ditemukan di PATH atau AppData.
        pause
        exit /b 1
    )
)

start "" %PYTHON_EXE% main.py
