@echo off
REM Re-launch inside a window that never closes by itself
if not "%1"=="stay" (
  start "InsightFlow ML" cmd /k ""%~f0" stay"
  exit /b
)
cd /d "%~dp0"
echo ===== InsightFlow ML service =====
python --version
if errorlevel 1 ( echo ERROR: Python not found & goto :end )
if not exist .env ( copy .env.example .env >nul & notepad .env )
if not exist .venv\Scripts\python.exe ( python -m venv .venv )
echo Installing packages (first time takes a few minutes)...
.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 ( echo ERROR: pip install failed. Read the lines above. & goto :end )
if not exist artifacts\trained_here.txt (
  echo Training model on this computer, about 1 minute...
  .venv\Scripts\python.exe -m insightflow_ml.train --source synthetic
  if errorlevel 1 ( echo ERROR: training failed. Read the lines above. & goto :end )
  echo done> artifacts\trained_here.txt
)
echo.
echo Starting service. Keep this window OPEN. Open http://localhost:8001/health
.venv\Scripts\python.exe -m uvicorn insightflow_ml.api:app --port 8001
:end
echo.
echo Stopped. Read any error above.
