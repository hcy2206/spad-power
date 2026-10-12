@echo off
cd /d "%~dp0"
uv sync --locked --group dev
if errorlevel 1 exit /b 1
uv run --locked python scripts/build_windows.py
if errorlevel 1 exit /b 1
pause
