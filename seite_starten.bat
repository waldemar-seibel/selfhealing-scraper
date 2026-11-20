@echo off
REM Startet die Uebungs-Jobboerse auf http://localhost:8000/seite-1.html
REM Fenster offen lassen, solange du uebst. Schliessen = Seite aus.
cd /d "%~dp0"
call .venv\Scripts\activate.bat
start "" http://localhost:8000/seite-1.html
python -m http.server 8000 -d uebungsseite\site
