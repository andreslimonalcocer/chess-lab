@echo off
rem Abre el juego en Windows (sin ventana de consola).
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw -3 ajedrez.py %* & exit /b)
where pythonw >nul 2>nul && (start "" pythonw ajedrez.py %* & exit /b)
python ajedrez.py %*
