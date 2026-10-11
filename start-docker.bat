@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

title JobParser — Docker only
set "NO_PROXY=localhost,127.0.0.1,::1,.local"
set "no_proxy=localhost,127.0.0.1,::1,.local"

echo ========================================
echo   JobParser — только backend (Docker)
echo ========================================
echo.

where docker >nul 2>&1
if errorlevel 1 (
  echo [X] Docker не найден. Запусти Docker Desktop и повтори.
  pause
  exit /b 1
)

echo [1/2] docker compose up -d ...
docker compose up -d
if errorlevel 1 (
  echo [X] docker compose up не удался
  echo     Проверь, что Docker Desktop запущен (иконка в трее).
  pause
  exit /b 1
)

echo [2/2] Жду http://localhost:8000/api/v1/health ...
set /a _tries=0
:wait_health
set /a _tries+=1
curl.exe -sf http://127.0.0.1:8000/api/v1/health >nul 2>&1
if not errorlevel 1 goto health_ok
if %_tries% GEQ 90 (
  echo [X] Backend не ответил. Последние логи:
  docker compose ps
  docker compose logs backend --tail 30
  pause
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto wait_health

:health_ok
echo.
echo OK — backend работает:
echo   API:  http://localhost:8000/api/v1/health
echo   Docs: http://localhost:8000/docs
echo.
echo UI (Flutter): start.bat или
echo   cd frontend ^&^& flutter run -d chrome --web-hostname=localhost --web-port=7357
echo.
pause
endlocal
