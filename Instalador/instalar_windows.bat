@echo off
rem Instalador para Windows: ejecuta instalar_windows.ps1 (no necesita permisos de administrador).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar_windows.ps1"
pause
