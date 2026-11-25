@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m uvicorn insightflow_ml.api:app --port 8001
pause