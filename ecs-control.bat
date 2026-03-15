@echo off
REM ECS Service Control Script (Batch)
REM Stop/Start the voice-bot-mvp service to save costs
REM Usage: ecs-control.bat {start|stop|status|toggle}

setlocal enabledelayedexpansion

set CLUSTER=voice-bot-mvp-cluster
set SERVICE=voice-bot-mvp-svc
set REGION=ap-south-1

if "%1"=="" (
    call :show_status
    exit /b 0
)

if /i "%1"=="start" (
    call :start_service
    exit /b 0
)

if /i "%1"=="stop" (
    call :stop_service
    exit /b 0
)

if /i "%1"=="status" (
    call :show_status
    exit /b 0
)

if /i "%1"=="toggle" (
    call :toggle_service
    exit /b 0
)

echo Usage: %0 {start^|stop^|status^|toggle}
echo.
echo Examples:
echo   %0 stop    - Stop the service ^(save costs^)
echo   %0 start   - Start the service
echo   %0 status  - Check current status
echo   %0 toggle  - Toggle between start/stop
exit /b 1

:show_status
echo.
echo [INFO] Current service status:
echo Cluster: %CLUSTER%
echo Service: %SERVICE%
echo Region: %REGION%
echo.

REM Use Python to parse JSON properly
python -c "import json,subprocess; result=subprocess.run(['aws','ecs','describe-services','--cluster','%CLUSTER%','--services','%SERVICE%','--region','%REGION%','--output','json'],capture_output=True,text=True); data=json.loads(result.stdout); svc=data['services'][0]; print(f'Running Tasks: {svc[\"runningCount\"]}'); print(f'Desired Tasks: {svc[\"desiredCount\"]}'); print(f'Status: {svc[\"status\"]}')" 2>nul

if %errorlevel% neq 0 (
    echo [ERROR] Failed to get service status. Check AWS credentials.
    exit /b 1
)

echo.
exit /b 0

:stop_service
echo.
echo [INFO] Stopping ECS service...
echo.

aws ecs update-service --cluster %CLUSTER% --service %SERVICE% --desired-count 0 --region %REGION% >nul 2>&1

if %errorlevel% neq 0 (
    echo [ERROR] Failed to stop service. Check AWS credentials.
    exit /b 1
)

echo [SUCCESS] Service stopped!
echo Running Tasks: 0
echo Hourly Cost: $0.00
echo.
exit /b 0

:start_service
echo.
echo [INFO] Starting ECS service...
echo.

aws ecs update-service --cluster %CLUSTER% --service %SERVICE% --desired-count 1 --region %REGION% >nul 2>&1

if %errorlevel% neq 0 (
    echo [ERROR] Failed to start service. Check AWS credentials.
    exit /b 1
)

echo [SUCCESS] Service started!
echo Desired Tasks: 1
echo Note: It will take 30-60 seconds to fully start
echo.
exit /b 0

:toggle_service
echo.
echo [INFO] Checking current status...
echo.

for /f "tokens=*" %%A in ('aws ecs describe-services --cluster %CLUSTER% --services %SERVICE% --region %REGION% --query "services[0].runningCount" --output text 2^>nul') do (
    set running=%%A
)

if "!running!"=="0" (
    echo Service is stopped. Starting...
    call :start_service
) else (
    echo Service is running. Stopping...
    call :stop_service
)

exit /b 0
