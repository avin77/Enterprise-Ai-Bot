@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0\.."

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo [ERROR] Missing virtual environment: %PY%
  echo Create it first: python -m venv .venv
  exit /b 1
)

if not exist ".env.local" (
  echo [INFO] .env.local not found. Creating default .env.local
  > ".env.local" (
    echo API_TOKEN=dev-token
    echo RATE_LIMIT_REQUESTS=30
    echo RATE_LIMIT_WINDOW_SECONDS=60
    echo USE_AWS_MOCKS=true
  )
)

echo [INFO] Checking backend dependencies...
call "%PY%" -c "import fastapi,uvicorn" >nul 2>&1
if errorlevel 1 (
  echo [INFO] Installing backend requirements...
  call "%PY%" -m pip install -r backend\requirements.txt || exit /b 1
)

echo [INFO] Loading variables from .env.local
for /f "usebackq tokens=1,* delims==" %%A in (".env.local") do (
  if not "%%~A"=="" (
    if not "%%~A:~0,1%%"=="#" (
      set "%%~A=%%~B"
    )
  )
)

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8000"

echo [INFO] Starting backend on http://127.0.0.1:%PORT%
call "%PY%" -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port %PORT%

endlocal
