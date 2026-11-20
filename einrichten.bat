@echo off
REM Einmalig: Python-Umgebung anlegen, Pakete und den Playwright-Browser installieren.
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python -m playwright install chromium
python uebungsseite\erzeugen.py
echo.
echo Fertig eingerichtet. Weiter geht es mit seite_starten.bat
pause
