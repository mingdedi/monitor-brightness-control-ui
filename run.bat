@echo off
rem Switch to the bat's own folder so config.json / history.log paths are correct
cd /d "%~dp0"

rem One-time dependency install when .venv is missing (e.g. fresh clone)
if not exist ".venv\Scripts\pythonw.exe" uv sync

rem pythonw.exe is the windowless GUI interpreter; start returns immediately,
rem so this console closes at once and only the UI window remains
start "" ".venv\Scripts\pythonw.exe" main.py
