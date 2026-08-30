@echo off
REM Manual start with a visible console, for debugging.
REM In normal use Task Scheduler starts it through pythonw.exe.
cd /d "%~dp0"
where py >nul 2>&1 && (py run.pyw & goto :eof)
python run.pyw
pause
